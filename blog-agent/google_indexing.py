"""
Google Indexing API helper.

After a post goes live, notify Google of the new URL so it gets crawled sooner.
Uses a Google Cloud service account (see README for the one-time setup).

Note: Google officially scopes the Indexing API to JobPosting / BroadcastEvent
structured data. In practice a URL_UPDATED notification commonly nudges a crawl
for any page, but Google does not guarantee it. The sitemap remains the primary
indexing path. This is a best-effort nudge, never a hard requirement.
"""
import os
import logging

INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
SCOPES = ["https://www.googleapis.com/auth/indexing"]

log = logging.getLogger("blog-agent")


def _session(sa_file):
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    return AuthorizedSession(creds)


def submit_url(url, sa_file, notify_type="URL_UPDATED"):
    """Notify Google that a URL was published or updated.

    Returns (ok: bool, detail: str). Never raises, so a failed nudge never
    stops a post from staying published.
    """
    if not sa_file or not os.path.exists(sa_file):
        return False, f"service account file not found: {sa_file}"
    try:
        sess = _session(sa_file)
        r = sess.post(INDEXING_ENDPOINT,
                      json={"url": url, "type": notify_type}, timeout=30)
        if r.status_code == 200:
            return True, "submitted to Google Indexing API"
        return False, f"HTTP {r.status_code}: {r.text[:180]}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:180]
