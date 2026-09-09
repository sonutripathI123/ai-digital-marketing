"""
Shared Google service-account credential loading for the GSC and GA4 agents.

Both agents authenticate with the same service account. Until now each one
looked for a single hardcoded file, ROOT_DIR/gsc-service-account.json, and on
failure logged a warning and silently returned hardcoded fallback numbers.

That file is gitignored — correctly, it holds a private key — which means it is
absent on any deployment built from the repository. The agents therefore always
took the fallback path in production while the dashboard presented the numbers
as real.

This module adds an environment-variable source so the credentials can be
supplied where no file is checked in, and returns the reason on failure so
callers can surface it instead of quietly substituting invented data.

Sources, in order:
  1. GOOGLE_SERVICE_ACCOUNT_JSON  - the whole JSON key as a string
  2. GOOGLE_SERVICE_ACCOUNT_FILE  - explicit path to the key file
  3. GOOGLE_APPLICATION_CREDENTIALS - Google's own standard variable
  4. ROOT_DIR/gsc-service-account.json - the original location

On Render, option 1 or a Secret File mounted at the repo root (which satisfies
option 4) both work without a code change.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List, Optional, Tuple

from config.settings import ROOT_DIR

DEFAULT_KEY_FILENAME = "gsc-service-account.json"


def credential_source() -> Tuple[str, Optional[str]]:
    """Which source will be used: ("env"|"file"|"none", detail)."""
    if (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip():
        return "env", "GOOGLE_SERVICE_ACCOUNT_JSON"

    for var in ("GOOGLE_SERVICE_ACCOUNT_FILE", "GOOGLE_APPLICATION_CREDENTIALS"):
        raw = (os.getenv(var) or "").strip()
        if raw and Path(raw).expanduser().exists():
            return "file", raw

    default_path = Path(ROOT_DIR) / DEFAULT_KEY_FILENAME
    if default_path.exists():
        return "file", str(default_path)

    return "none", None


def load_service_account_credentials(scopes: List[str]) -> Tuple[Optional[Any], Optional[str]]:
    """Build service-account credentials.

    Returns (credentials, None) on success, or (None, reason) describing why
    they could not be built. Never raises.
    """
    try:
        from google.oauth2 import service_account
    except ImportError:
        return None, "Python package 'google-auth' is not installed."

    raw_json = (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
    if raw_json:
        try:
            info = json.loads(raw_json)
        except ValueError as e:
            return None, f"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON: {e}"
        try:
            return service_account.Credentials.from_service_account_info(info, scopes=scopes), None
        except Exception as e:
            return None, f"GOOGLE_SERVICE_ACCOUNT_JSON was rejected: {e}"

    source, detail = credential_source()
    if source == "none":
        return None, (
            f"No service account credentials found. Set GOOGLE_SERVICE_ACCOUNT_JSON, "
            f"or provide {DEFAULT_KEY_FILENAME} at the project root "
            f"(on Render, add it as a Secret File)."
        )

    try:
        return service_account.Credentials.from_service_account_file(detail, scopes=scopes), None
    except Exception as e:
        return None, f"Could not load service account key from {detail}: {e}"
