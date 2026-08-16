# Corporate Cars Melbourne — Social Media Agent

Local automation agent that turns your SEO keywords into platform-specific social
posts (via the Claude API), pairs each post with a rotating image from a local
library, schedules **2 posts per week per platform**, and publishes to
Instagram, Facebook, LinkedIn, X, Threads and Pinterest. All state lives in a
local SQLite database (`social_agent.db`).

## Setup

```powershell
cd corporate-cars-social-agent
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # then fill in your keys (see below)
.venv\Scripts\python cli.py init
```

> All commands below assume `.venv\Scripts\python` (or activate the venv first
> with `.venv\Scripts\activate`).

## Image library

Drop photos into `images\<category>\<filename>.jpg`. Category folders should
match vehicle or service types, and hyphen-separated words in filenames become
searchable tags:

```
images\sedan\sedan-01.jpg                    (Mercedes S-Class)
images\people-mover\people-mover-01.jpg      (Mercedes V-Class)
images\minibus\minibus-01.jpg                (Mercedes Sprinter)
images\suv\suv-01.jpg                        (Audi Q7)
images\wedding-cars\wedding-cars-01.jpg
```

Run `python cli.py sync-images` after adding/removing files. The selector picks
the **least-recently-used** matching image, so the same photo is never reused
back-to-back. Keyword→category matching lives in `TOKEN_SYNONYMS` in
`image_selector.py` — extend it when you add new category folders.

### IMAGE_BASE_URL (required for Instagram / Threads / Pinterest / Facebook photos)

Meta's and Pinterest's APIs **fetch images from a public URL** — they don't accept
file uploads from this tool. Mirror the `images/` folder to your website (e.g.
upload it to `corporatecarsmelbourne.com.au/social-images/`) and set:

```
IMAGE_BASE_URL=https://corporatecarsmelbourne.com.au/social-images
```

Local path `images\wedding-cars\wedding-cars-02.jpg` then maps to
`https://.../social-images/wedding-cars/wedding-cars-02.jpg`.
X and LinkedIn upload the local file directly and don't need this.

## Commands

| Command | What it does |
|---|---|
| `python cli.py init` | Create DB + sync image library |
| `python cli.py add-keywords "airport transfer, corporate travel" --category "airport transfer"` | Seed the keyword pool |
| `python cli.py generate --keywords "airport transfer" --platform instagram` | Generate a draft post (Claude API) |
| `python cli.py generate --keywords "..." --platform all --no-ai` | Offline template drafts (no API key needed) |
| `python cli.py schedule --weeks 2` | Queue drafts: 2/week/platform at staggered Melbourne-time slots |
| `python cli.py publish-due` | Dry run — show what *would* publish |
| `python cli.py publish-due --live` | Actually publish everything due |
| `python cli.py status` | Post counts + upcoming schedule |
| `python cli.py list-posts --status draft` | Inspect posts |
| `python run_scheduler.py` | Daemon: checks every 5 min, publishes due posts (dry-run unless `--live`) |

`DRY_RUN=true` in `.env` keeps everything safe by default; pass `--live` (or set
`DRY_RUN=false`) when you're ready to post for real.

### Typical weekly workflow

```powershell
python cli.py generate --keywords "airport transfer, corporate travel, wedding cars, winery tours" --platform all
python cli.py list-posts --status draft      # review / sanity-check the copy
python cli.py schedule --weeks 2
python run_scheduler.py --live               # leave running (or run as a Windows service / Task Scheduler job)
```

## Getting API keys

### Anthropic (content generation)
1. <https://console.anthropic.com> → API Keys → create key → `ANTHROPIC_API_KEY`.
2. Model is `CLAUDE_MODEL` in `.env` (default `claude-sonnet-4-6`).

### Meta — Instagram + Facebook
1. Instagram account must be a **Business/Creator account linked to a Facebook Page**.
2. <https://developers.facebook.com> → create an app (Business type).
3. Add the **Instagram Graph API** and **Facebook Login for Business** products.
4. Use the Graph API Explorer to generate a token with scopes:
   `instagram_basic, instagram_content_publish, pages_manage_posts, pages_read_engagement, business_management` — then exchange for a **long-lived token** (60 days) → `META_ACCESS_TOKEN`.
5. `META_PAGE_ID` = your Facebook Page ID; `INSTAGRAM_BUSINESS_ACCOUNT_ID` = from
   `GET /{page-id}?fields=instagram_business_account`.

### Threads
1. Same Meta developer app → add the **Threads API** product.
2. Generate a token with `threads_basic, threads_content_publish` → `THREADS_ACCESS_TOKEN`.
3. `THREADS_USER_ID` = from `GET https://graph.threads.net/v1.0/me`.

### LinkedIn
1. <https://developer.linkedin.com> → create an app tied to your **company page**.
2. Request **Community Management API** (org posting) access; scope `w_organization_social`.
3. OAuth 2.0 flow → `LINKEDIN_ACCESS_TOKEN`;
   `LINKEDIN_ORGANIZATION_URN` = `urn:li:organization:<your-page-id>`.

### X (Twitter)
1. <https://developer.x.com> → create a project + app (Free tier can post).
2. App permissions: **Read and Write**. Generate consumer keys + access token/secret →
   `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`.

### Pinterest
1. <https://developers.pinterest.com> → create an app (trial access is fine to start).
2. OAuth with scopes `pins:write, boards:read` → `PINTEREST_ACCESS_TOKEN`.
3. `PINTEREST_BOARD_ID` = from `GET https://api.pinterest.com/v5/boards`.

## Reliability & ops

- **Retries**: failed publishes retry with exponential backoff
  (`RETRY_BASE_DELAY_SECONDS` × 2ⁿ, up to `MAX_PUBLISH_ATTEMPTS`); the Anthropic
  SDK retries rate limits automatically. Non-retryable failures (missing keys)
  fail fast with the error stored on the post row.
- **Logs**: rotating file at `logs\agent.log` (5 × 1 MB) + console.
- **Alerting**: MVP logs errors to console + file. To add email/Slack, plug a
  handler into the marked hook in `app_logging.py`.
- **Prompt maintenance**: platform algorithm guidance lives in `prompts.py`
  (`PLATFORM_RULES[...]["algorithm_notes"]`) — reflects best practice as of
  early-mid 2026; review quarterly.

## Token expiry notes

- Meta long-lived tokens last ~60 days — refresh before expiry.
- LinkedIn tokens last ~60 days (refresh tokens available with approved apps).
- Pinterest tokens include a refresh token; X OAuth 1.0a tokens don't expire.
