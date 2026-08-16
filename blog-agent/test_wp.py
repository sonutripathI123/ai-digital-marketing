#!/usr/bin/env python3
"""
Free WordPress connection test. Uses NO Anthropic credit.

It checks, for the ccm site:
  1. Login / application password work (auth)
  2. Category read/create works
  3. Media library is readable and a featured image can be picked
  4. A draft can be created with a featured image + Yoast meta fields
  5. The Yoast REST Meta plugin actually saved the focus keyword (reads it back)
Then it DELETES the test draft so nothing is left behind.

Run:  python test_wp.py
"""
import sys
import requests
import blog_agent as ba

SITE = "ccm"


def check(label, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" -> {detail}" if detail else ""))
    return ok


def main():
    cfg = ba.load_config()
    site_cfg = ba.get_site(cfg, SITE)
    try:
        api, auth = ba.wp_auth(SITE, site_cfg)
    except SystemExit as e:
        print("Config/.env problem:", e)
        sys.exit(1)

    print(f"\nTesting WordPress connection for: {site_cfg['name']}")
    print(f"Site: {site_cfg['base_url']}\n")
    all_ok = True
    test_post_id = None

    # 1. Auth
    try:
        r = requests.get(f"{api}/users/me", params={"context": "edit"}, auth=auth, timeout=30)
        if r.status_code == 200:
            all_ok &= check("Login / application password", True,
                            f"logged in as '{r.json().get('name', '?')}'")
        else:
            all_ok &= check("Login / application password", False,
                            f"HTTP {r.status_code}: {r.text[:120]}")
            print("\nStopping: fix the WP username / application password in .env first.")
            sys.exit(1)
    except requests.RequestException as e:
        check("Reaching the site", False, str(e)[:150])
        sys.exit(1)

    # 2. Category
    try:
        cat_id = ba.wp_term_id(api, auth, "categories", site_cfg["default_category"])
        all_ok &= check("Category read/create", True,
                        f"'{site_cfg['default_category']}' id={cat_id}")
    except Exception as e:  # noqa: BLE001
        all_ok &= check("Category read/create", False, str(e)[:150])

    # 3. Featured image from media library
    row = {"suburb": "Doncaster", "keyword": "doncaster airport transfers"}
    fid = None
    try:
        fid = ba.pick_featured_image(api, auth, cfg, SITE, row)
        all_ok &= check("Media library / featured image", bool(fid),
                        f"picked media id={fid}" if fid else "no images found in library")
    except Exception as e:  # noqa: BLE001
        all_ok &= check("Media library / featured image", False, str(e)[:150])

    # 4. Create a test draft (no AI)
    post = {
        "title": "[blog-agent connection test - safe to ignore]",
        "slug": "blog-agent-connection-test",
        "content_html": "<p>This is an automated connection test. It will be deleted.</p>",
        "meta_description": "blog-agent connection test",
        "focus_keyword": "blog agent connection test",
        "seo_title": "blog-agent connection test",
        "category": site_cfg["default_category"],
        "tags": [],
        "faq_jsonld": None,
    }
    try:
        test_post_id = ba.wp_create_draft(api, auth, post, featured_media_id=fid)
        all_ok &= check("Create draft", True, f"post_id={test_post_id}")
    except Exception as e:  # noqa: BLE001
        all_ok &= check("Create draft", False, str(e)[:150])

    # 5. Read back the Yoast focus keyword (confirms the mu-plugin works)
    if test_post_id:
        try:
            r = requests.get(f"{api}/posts/{test_post_id}", params={"context": "edit"},
                             auth=auth, timeout=30)
            meta = r.json().get("meta", {})
            saved = meta.get("_yoast_wpseo_focuskw", "")
            ok = saved == post["focus_keyword"]
            all_ok &= check("Yoast REST Meta plugin (focus keyword saved)", ok,
                            f"read back '{saved}'" if saved else "focus keyword NOT saved "
                            "(is the 'Yoast REST Meta' plugin active?)")
        except Exception as e:  # noqa: BLE001
            all_ok &= check("Yoast REST Meta plugin", False, str(e)[:150])

    # 6. Clean up: delete the test draft
    if test_post_id:
        try:
            requests.delete(f"{api}/posts/{test_post_id}", params={"force": "true"},
                            auth=auth, timeout=30)
            check("Cleanup (test draft deleted)", True, f"post_id={test_post_id}")
        except requests.RequestException as e:
            check("Cleanup (test draft deleted)", False,
                  f"could not delete post {test_post_id}: {e}")

    print("\n" + ("ALL GOOD — WordPress side is ready. Bas Anthropic credit daalna baaki hai."
                  if all_ok else
                  "Kuch check FAIL hue upar. Jo FAIL dikhe wo mujhe bata."))


if __name__ == "__main__":
    main()
