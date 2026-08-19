#!/usr/bin/env python3
"""
Blog posting agent for the chauffeur sites.

Workflow (hybrid approval + draft-then-auto-live):
  suggest  -> AI proposes topics, appended to topics.csv as status=suggested.
              You review and change status to "approved" for the ones you want.
  write    -> Takes approved topics, generates the post, creates a WordPress
              DRAFT, sets go_live_at = now + review_window_hours, status=drafted.
  publish  -> Flips any drafted post whose go_live_at has passed to LIVE,
              unless you set its status to "hold". status becomes published.
  status   -> Prints a summary of the queue.

Run write on a slow cron (daily/weekly). Run publish on a fast cron (hourly).
"""

import argparse
import csv
import datetime as dt
import json
import os
import sys
import tempfile
import logging
from zoneinfo import ZoneInfo

import requests
import yaml
from dotenv import load_dotenv
from anthropic import Anthropic
import google_indexing

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

try:
    from agents.seo_content_brief_agent import generate_brief_for_topic, optimize_and_refine_blog_post
except ImportError:
    generate_brief_for_topic = None
    optimize_and_refine_blog_post = None

TOPICS_FILE = os.path.join(BASE_DIR, "topics.csv")
RULES_FILE = os.path.join(BASE_DIR, "content_rules.md")
CONFIG_FILE = os.path.join(BASE_DIR, "config.yaml")
FIELDNAMES = ["id", "site", "keyword", "title_hint", "suburb",
              "status", "wp_post_id", "go_live_at", "notes"]

load_dotenv(os.path.join(BASE_DIR, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "logs", "agent.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("blog-agent")


# --------------------------------------------------------------------------- #
# Config + queue helpers
# --------------------------------------------------------------------------- #
def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_site(cfg, key):
    if key not in cfg["sites"]:
        raise SystemExit(f"Unknown site '{key}'. Known: {list(cfg['sites'])}")
    return cfg["sites"][key]


def local_now(cfg):
    return dt.datetime.now(ZoneInfo(cfg.get("timezone", "Australia/Melbourne")))


def is_sunday(cfg):
    return local_now(cfg).weekday() == 6  # Monday=0 ... Sunday=6


def read_topics():
    if not os.path.exists(TOPICS_FILE):
        return []
    with open(TOPICS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_topics(rows):
    """Atomic write so an overlapping cron never corrupts the queue."""
    fd, tmp = tempfile.mkstemp(dir=BASE_DIR, suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDNAMES})
    os.replace(tmp, TOPICS_FILE)


def next_id(rows):
    nums = [int(r["id"][1:]) for r in rows if r["id"].startswith("t") and r["id"][1:].isdigit()]
    return f"t{(max(nums) + 1 if nums else 1):04d}"


def anthropic_client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY missing. Copy .env.example to .env and fill it in.")
    return Anthropic(api_key=key)


def parse_json(text):
    """Strip accidental fences and parse the model's JSON reply robustly."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty response from AI model")

    # 1. Direct parse attempt
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code fence ```json ... ```
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            clean = part.strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()
            if (clean.startswith("{") and clean.endswith("}")) or (clean.startswith("[") and clean.endswith("]")):
                try:
                    return json.loads(clean)
                except json.JSONDecodeError:
                    pass

    # 3. Find outermost { ... } or [ ... ]
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")

    if first_brace != -1 and last_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    if first_bracket != -1 and last_bracket != -1:
        candidate = text[first_bracket:last_bracket + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from response: {text[:200]}...")


# --------------------------------------------------------------------------- #
# WordPress REST helpers (Application Passwords)
# --------------------------------------------------------------------------- #
def wp_auth(site_key, site_cfg):
    prefix = site_key.upper()
    user = os.environ.get(f"{prefix}_WP_USER")
    pw = os.environ.get(f"{prefix}_WP_APP_PASSWORD")
    if not user or not pw:
        raise SystemExit(f"Missing {prefix}_WP_USER / {prefix}_WP_APP_PASSWORD in .env")
    api = site_cfg["base_url"].rstrip("/") + "/wp-json/wp/v2"
    return api, (user, pw)


def wp_term_id(api, auth, taxonomy, name):
    """Find a category/tag by name, create it if missing, return its id."""
    r = requests.get(f"{api}/{taxonomy}", params={"search": name, "per_page": 100},
                     auth=auth, timeout=30)
    r.raise_for_status()
    for term in r.json():
        if term["name"].lower() == name.lower():
            return term["id"]
    r = requests.post(f"{api}/{taxonomy}", json={"name": name}, auth=auth, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def wp_create_draft(api, auth, post, featured_media_id=None):
    cat_id = wp_term_id(api, auth, "categories", post["category"])
    tag_ids = [wp_term_id(api, auth, "tags", t) for t in post.get("tags", [])]

    body_html = post["content_html"]
    faq = post.get("faq_jsonld")
    if faq:
        body_html += ('\n<!-- wp:html -->\n<script type="application/ld+json">'
                      + json.dumps(faq) + "</script>\n<!-- /wp:html -->")

    payload = {
        "title": post["title"],
        "slug": post["slug"],
        "content": body_html,
        "excerpt": post["meta_description"],
        "status": "draft",
        "categories": [cat_id],
        "tags": tag_ids,
        "meta": {
            "_yoast_wpseo_focuskw": post["focus_keyword"],
            "_yoast_wpseo_metadesc": post["meta_description"],
            "_yoast_wpseo_title": post.get("seo_title", post["title"]),
        },
    }
    if featured_media_id:
        payload["featured_media"] = featured_media_id
    r = requests.post(f"{api}/posts", json=payload, auth=auth, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


# ---- Featured image from the WordPress media library ----
def wp_list_media(api, auth, search="", per_page=30):
    params = {"media_type": "image", "per_page": per_page,
              "_fields": "id,title,alt_text,source_url"}
    if search:
        params["search"] = search
    r = requests.get(f"{api}/media", params=params, auth=auth, timeout=30)
    r.raise_for_status()
    return r.json()


def _used_images_path(site_key):
    return os.path.join(BASE_DIR, "logs", f"used_images_{site_key}.json")


def load_used_images(site_key):
    p = _used_images_path(site_key)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            return []
    return []


def save_used_images(site_key, ids):
    with open(_used_images_path(site_key), "w", encoding="utf-8") as f:
        json.dump(ids[-100:], f)


def pick_featured_image(api, auth, cfg, site_key, row):
    """Pick a relevant image from the media library, avoiding recent repeats."""
    fi = cfg.get("featured_image", {})
    if not fi.get("enabled", True):
        return None

    terms = []
    if row.get("suburb"):
        terms.append(row["suburb"])
    if row.get("keyword"):
        terms.append(row["keyword"])
    terms += fi.get("extra_search_terms", [])

    seen, candidates = set(), []
    for term in terms:
        try:
            for m in wp_list_media(api, auth, search=term):
                if m["id"] not in seen:
                    seen.add(m["id"])
                    candidates.append(m["id"])
        except requests.RequestException:
            continue
    if not candidates:  # fallback: any images in the library
        try:
            for m in wp_list_media(api, auth, per_page=50):
                if m["id"] not in seen:
                    seen.add(m["id"])
                    candidates.append(m["id"])
        except requests.RequestException:
            pass

    recent = load_used_images(site_key)
    avoid = set(recent[-fi.get("avoid_repeat_last", 12):])
    fresh = [c for c in candidates if c not in avoid]
    chosen = (fresh or candidates or [None])[0]
    if chosen:
        recent.append(chosen)
        save_used_images(site_key, recent)
    return chosen


def wp_publish(api, auth, post_id):
    r = requests.post(f"{api}/posts/{post_id}", json={"status": "publish"},
                      auth=auth, timeout=60)
    r.raise_for_status()
    return r.json().get("link", "")


# --------------------------------------------------------------------------- #
# Content generation
# --------------------------------------------------------------------------- #
def load_internal_links(site_cfg):
    path = os.path.join(BASE_DIR, site_cfg.get("internal_links_file", ""))
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_suburb_pages(site_cfg):
    """Map suburb name -> {url, keyword} for existing commercial landing pages."""
    path = os.path.join(BASE_DIR, site_cfg.get("suburb_pages_file", ""))
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["suburb"].strip().lower(): r
                for r in csv.DictReader(f) if r.get("suburb")}


def suburb_page_for(site_cfg, row):
    return load_suburb_pages(site_cfg).get(row.get("suburb", "").strip().lower())


# Informational modifiers that mark a blog query as distinct from a commercial one.
INFO_MODIFIERS = ("how", "why", "what", "when", "cost", "price", "time", "long",
                  "best", "tips", "guide", "vs", "compare", "checklist",
                  "things to", "worth", "avoid", "before")


def cannibalises(focus_kw, commercial_kw):
    """True if the blog keyword would compete with the suburb page keyword."""
    f = (focus_kw or "").strip().lower()
    c = (commercial_kw or "").strip().lower()
    if not c:
        return False
    if f == c:
        return True
    # Blog keyword just wraps the commercial keyword with no informational angle.
    if c in f and not any(m in f for m in INFO_MODIFIERS):
        return True
    return False


def generate_post(client, cfg, site_key, site_cfg, row, extra_instruction=""):
    with open(RULES_FILE, encoding="utf-8") as f:
        system = f.read()

    links = load_internal_links(site_cfg)
    sp = suburb_page_for(site_cfg, row)

    link_lines = [f"- {l['anchor']} -> {l['url']} (use for: {l['topic']})" for l in links]
    if sp:
        link_lines.insert(0, f"- {sp['keyword']} -> {sp['url']} (the suburb landing page, MANDATORY link)")
    links_block = "\n".join(link_lines) or "- (none provided, link to the homepage only)"

    if sp:
        anti_block = (
            f"\nEXISTING SUBURB PAGE (do not compete with it):\n"
            f"- URL: {sp['url']}\n"
            f"- It already ranks for the commercial keyword: \"{sp['keyword']}\".\n"
            f"- So this blog post MUST target a different informational long-tail query.\n"
            f"- Do NOT use \"{sp['keyword']}\" as the title, slug, or focus keyword.\n"
            f"- You MUST link to {sp['url']} once with anchor text \"{sp['keyword']}\".\n"
            f"- The 'keyword' given below is only a topic seed, reshape it into a "
            f"question or guide angle.\n"
        )
    else:
        anti_block = ""

    suburb_line = f"Suburb focus: {row['suburb']}.\n" if row.get("suburb") else ""
    hint_line = f"Working title idea: {row['title_hint']}.\n" if row.get("title_hint") else ""

    # Pre-generate SEO Content Brief from SEO Content Brief Agent
    brief = None
    brief_prompt = ""
    if generate_brief_for_topic:
        try:
            brief = generate_brief_for_topic(
                target_keyword=row["keyword"],
                suburb=row.get("suburb", ""),
                site_name=site_cfg["name"],
                site_domain=site_cfg["base_url"]
            )
            outlines_str = "\n".join([f"- {s['heading']} (Level: {s['level']}, Key points: {', '.join(s['key_points'])})" for s in brief.get("structured_outline", [])])
            brief_prompt = (
                f"\n--- MANDATORY SEO CONTENT BRIEF FROM SEO CONTENT BRIEF AGENT ---\n"
                f"H1 Title Options: {', '.join(brief.get('title_suggestions', []))}\n"
                f"Recommended Word Count: {brief.get('recommended_word_count', '1,200 - 1,500 words')}\n"
                f"LSI Secondary Keywords: {', '.join(brief.get('secondary_keywords', []))}\n"
                f"Target Audience: {brief.get('target_audience')} ({brief.get('search_intent')})\n"
                f"Required Section Outline:\n{outlines_str}\n"
                f"Conversion Call to Action: {brief.get('call_to_action')}\n"
                f"---------------------------------------------------------------\n"
            )
        except Exception as e:
            log.warning("Could not pre-generate SEO brief: %s", e)

    prompt = (
        f"Business: {site_cfg['name']} ({site_cfg['base_url']}).\n"
        f"Topic seed / keyword: {row['keyword']}.\n"
        f"{suburb_line}{hint_line}"
        f"Default category if unsure: {site_cfg['default_category']}.\n"
        f"{anti_block}\n"
        f"{brief_prompt}\n"
        f"Internal link targets you may use (pick 2 to 4):\n{links_block}\n\n"
        f"{extra_instruction}\n"
        f"Write the blog post now. Return ONLY the JSON object described in your "
        f"instructions."
    )

    msg = client.messages.create(
        model=cfg["default_model"],
        max_tokens=cfg["max_tokens"],
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return parse_json(text)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_suggest(args, cfg):
    site_cfg = get_site(cfg, args.site)
    client = anthropic_client()

    sub_pages = load_suburb_pages(site_cfg)
    if sub_pages:
        avoid = "; ".join(f'"{r["keyword"]}"' for r in sub_pages.values())
        avoid_block = (
            f"These commercial keywords are already owned by existing suburb "
            f"landing pages. Do NOT propose topics that target them: {avoid}. "
            f"For those suburbs, only propose informational angles (how long, "
            f"cost, best time, tips, vs) that support but never compete with the "
            f"landing page.\n"
        )
    else:
        avoid_block = ""

    prompt = (
        f"Business: {site_cfg['name']} ({site_cfg['base_url']}).\n"
        f"Propose {args.n} fresh, non-overlapping blog topic ideas for local SEO. "
        f"{'Theme: ' + args.theme + '. ' if args.theme else ''}"
        f"Avoid keyword cannibalisation: each topic must target a distinct query.\n"
        f"{avoid_block}"
        f'Return ONLY a JSON array of objects with keys "keyword", "title_hint", '
        f'"suburb" (empty string if none). No prose.'
    )
    msg = client.messages.create(
        model=cfg["default_model"], max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    ideas = parse_json("".join(b.text for b in msg.content if b.type == "text"))

    rows = read_topics()
    for idea in ideas:
        rows.append({
            "id": next_id(rows), "site": args.site,
            "keyword": idea.get("keyword", ""), "title_hint": idea.get("title_hint", ""),
            "suburb": idea.get("suburb", ""), "status": "suggested",
            "wp_post_id": "", "go_live_at": "", "notes": "",
        })
    write_topics(rows)
    log.info("Added %d suggested topics for %s. Edit topics.csv and set status "
             "to 'approved' for the ones you want.", len(ideas), args.site)


def cmd_write(args, cfg):
    if cfg.get("skip_sunday", True) and is_sunday(cfg):
        log.info("Sunday: skipping write run (no posting on Sunday).")
        return
    client = anthropic_client()
    rows = read_topics()
    done = 0
    for row in rows:
        if done >= cfg["posts_per_write_run"]:
            break
        if row["status"] != "approved":
            continue
        if args.site and row["site"] != args.site:
            continue
        site_cfg = get_site(cfg, row["site"])
        api, auth = wp_auth(row["site"], site_cfg)
        try:
            log.info("Writing: %s (%s)", row["keyword"], row["site"])
            post = generate_post(client, cfg, row["site"], site_cfg, row)
            sp = suburb_page_for(site_cfg, row)

            # Anti-cannibalisation guard: blog must not reuse the suburb page keyword.
            if sp and cannibalises(post.get("focus_keyword", ""), sp["keyword"]):
                log.warning("Focus keyword '%s' clashes with suburb page '%s'. Retrying.",
                            post.get("focus_keyword"), sp["keyword"])
                post = generate_post(
                    client, cfg, row["site"], site_cfg, row,
                    extra_instruction=(
                        f"Your previous attempt reused the commercial keyword. "
                        f"Pick a clearly informational, question-style focus keyword "
                        f"that does NOT contain the exact phrase '{sp['keyword']}'."),
                )
                if cannibalises(post.get("focus_keyword", ""), sp["keyword"]):
                    raise ValueError(
                        f"cannibalisation guard: focus keyword '{post.get('focus_keyword')}' "
                        f"still competes with suburb page '{sp['keyword']}'")

            # Post-Draft Auto-Optimization & SEO Quality Refinement via SEO Content Brief Agent
            if optimize_and_refine_blog_post:
                try:
                    brief = generate_brief_for_topic(
                        target_keyword=row["keyword"],
                        suburb=row.get("suburb", ""),
                        site_name=site_cfg["name"],
                        site_domain=site_cfg["base_url"]
                    ) if generate_brief_for_topic else None
                    post = optimize_and_refine_blog_post(
                        post=post,
                        brief=brief,
                        site_name=site_cfg["name"],
                        site_domain=site_cfg["base_url"]
                    )
                    log.info("SEO Content Brief Agent auto-optimized post: %s (Schema.org JSON-LD injected, LSI checked)", post.get("title"))
                except Exception as e:
                    log.warning("SEO Content Brief post-optimization warning: %s", e)

            post.setdefault("category", site_cfg["default_category"])
            featured_id = pick_featured_image(api, auth, cfg, row["site"], row)
            post_id = wp_create_draft(api, auth, post, featured_media_id=featured_id)
            go_live = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=cfg["review_window_hours"])
            row.update(status="drafted", wp_post_id=str(post_id),
                       go_live_at=go_live.isoformat(), notes="")
            log.info("Draft created. post_id=%s, featured_media=%s, auto-live at %s",
                     post_id, featured_id, go_live.isoformat())
            done += 1
        except Exception as e:  # noqa: BLE001
            row.update(status="error", notes=str(e)[:200])
            log.error("Failed on %s: %s", row["keyword"], e)
        write_topics(rows)
    log.info("write run complete. %d draft(s) created.", done)


def cmd_publish(args, cfg):
    if cfg.get("skip_sunday", True) and is_sunday(cfg):
        log.info("Sunday: skipping publish run (no posts go live on Sunday).")
        return
    rows = read_topics()
    now = dt.datetime.now(dt.timezone.utc)
    published = 0
    for row in rows:
        if row["status"] != "drafted" or not row["go_live_at"]:
            continue
        try:
            go_live = dt.datetime.fromisoformat(row["go_live_at"])
        except ValueError:
            continue
        if go_live > now:
            continue
        site_cfg = get_site(cfg, row["site"])
        api, auth = wp_auth(row["site"], site_cfg)
        try:
            link = wp_publish(api, auth, int(row["wp_post_id"]))
            row.update(status="published", notes=link)
            log.info("Published: %s -> %s", row["keyword"], link)
            published += 1

            gi = cfg.get("google_indexing", {})
            if gi.get("enabled") and link:
                sa = gi.get("service_account_file", "")
                sa = sa if os.path.isabs(sa) else os.path.join(BASE_DIR, sa)
                ok, detail = google_indexing.submit_url(link, sa)
                log.info("Google indexing: %s (%s)", "OK" if ok else "FAILED", detail)
                if not ok:
                    row["notes"] = f"{link} | index nudge failed: {detail}"
        except Exception as e:  # noqa: BLE001
            row.update(status="error", notes=str(e)[:200])
            log.error("Publish failed for post %s: %s", row["wp_post_id"], e)
        write_topics(rows)
    log.info("publish run complete. %d post(s) went live.", published)


def cmd_import(args, cfg):
    path = args.file if os.path.isabs(args.file) else os.path.join(BASE_DIR, args.file)
    if not os.path.exists(path):
        raise SystemExit(f"File not found: {path}")
    with open(path, newline="", encoding="utf-8") as f:
        incoming = list(csv.DictReader(f))

    rows = read_topics()
    added = 0
    for it in incoming:
        site = (it.get("site") or args.site or "").strip()
        if not site:
            raise SystemExit("A row has no 'site' column and no --site was given.")
        get_site(cfg, site)  # validate
        rows.append({
            "id": next_id(rows), "site": site,
            "keyword": (it.get("keyword") or "").strip(),
            "title_hint": (it.get("title") or it.get("title_hint") or "").strip(),
            "suburb": (it.get("suburb") or "").strip(),
            "status": "approved",  # you handed final titles, so ready to write
            "wp_post_id": "", "go_live_at": "", "notes": "",
        })
        added += 1
    write_topics(rows)
    log.info("Imported %d titles as approved. Run 'write' to draft them.", added)


def cmd_status(args, cfg):
    rows = read_topics()
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("\nQueue summary:")
    for status, n in sorted(counts.items()):
        print(f"  {status:12} {n}")
    print(f"  {'TOTAL':12} {len(rows)}\n")
    for r in rows:
        if r["status"] in ("drafted", "error"):
            print(f"  [{r['status']}] {r['site']} | {r['keyword']} "
                  f"| post={r['wp_post_id']} | live_at={r['go_live_at']} {r['notes']}")


# --------------------------------------------------------------------------- #
def main():
    cfg = load_config()
    p = argparse.ArgumentParser(description="Chauffeur blog posting agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("suggest", help="AI proposes topics into the queue")
    s.add_argument("--site", required=True)
    s.add_argument("--n", type=int, default=10)
    s.add_argument("--theme", default="")

    w = sub.add_parser("write", help="Turn approved topics into WordPress drafts")
    w.add_argument("--site", default="")

    i = sub.add_parser("import", help="Bulk-import titles CSV as approved topics")
    i.add_argument("--file", required=True, help="CSV with columns: site,suburb,keyword,title")
    i.add_argument("--site", default="", help="Default site if the CSV omits the site column")

    sub.add_parser("publish", help="Auto-publish drafts past their review window")
    sub.add_parser("status", help="Show queue summary")

    args = p.parse_args()
    {"suggest": cmd_suggest, "write": cmd_write, "import": cmd_import,
     "publish": cmd_publish, "status": cmd_status}[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
