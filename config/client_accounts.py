"""Login accounts for the people a website is handed to.

A client used to reach their dashboard by typing any email into a gate, which
authenticated nobody: the address was recorded, not checked. Anyone holding the
link — or guessing a site id — got in.

An account here is created once, from a single-use invite the admin issues with
the website, and is bound to exactly one site. After that the client signs in
with the email and password they chose.

Password hashes live in their own file rather than on the website profile: that
profile is serialized straight to the dashboard by /api/websites, and a hash
has no business travelling with it.
"""

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import LOGS_DIR
from core.logging.logger import get_agent_logger

logger = get_agent_logger("client-accounts")

ACCOUNTS_FILE = LOGS_DIR / "client_accounts.json"

# PBKDF2-HMAC-SHA256. No new dependency, and the iteration count is stored per
# record so it can be raised later without invalidating existing passwords.
HASH_ITERATIONS = 240_000
MIN_PASSWORD_LENGTH = 8


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password: str, salt: Optional[str] = None,
                  iterations: int = HASH_ITERATIONS) -> Dict[str, Any]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations
    )
    return {"salt": salt, "iterations": iterations, "hash": digest.hex()}


def verify_password(password: str, record: Dict[str, Any]) -> bool:
    """Constant-time check, so a wrong password cannot be found by timing."""
    try:
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(record["salt"]),
            int(record.get("iterations", HASH_ITERATIONS)),
        )
        return hmac.compare_digest(candidate.hex(), record.get("hash", ""))
    except Exception:
        return False


def password_problem(password: str) -> Optional[str]:
    """Why this password cannot be used, or None if it is fine.

    Deliberately short: a rule nobody can satisfy pushes people to write the
    password down, which is worse than a plain one they remember.
    """
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password.lower() in ("password", "12345678", "qwertyui", "changeme"):
        return "That password is too common. Please choose another."
    return None


class ClientAccountStore:
    """One account per email, each bound to one website."""

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or ACCOUNTS_FILE
        self._accounts: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ---------------------------------------------------------------- disk --
    def _load(self) -> None:
        if not self.storage_file.exists():
            return
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                self._accounts = json.load(f)
        except Exception as e:
            logger.warning("Could not read client accounts: %s", e)
            self._accounts = {}

    def _save(self) -> None:
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.storage_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._accounts, f, indent=2)
            os.replace(tmp, self.storage_file)
            try:
                os.chmod(self.storage_file, 0o600)
            except OSError:
                pass  # not all filesystems allow it; the hash is still a hash
        except Exception as e:
            logger.error("Could not save client accounts: %s", e)

    # -------------------------------------------------------------- lookup --
    @staticmethod
    def _key(email: str) -> str:
        return (email or "").strip().lower()

    def get(self, email: str) -> Optional[Dict[str, Any]]:
        return self._accounts.get(self._key(email))

    def exists(self, email: str) -> bool:
        return self._key(email) in self._accounts

    def accounts_for_site(self, site_id: str) -> List[Dict[str, Any]]:
        """Every account that can sign in to this site, without the hashes."""
        out = []
        for email, acc in self._accounts.items():
            if acc.get("site_id") == site_id:
                out.append({
                    "email": email,
                    "site_id": acc.get("site_id"),
                    "created_at": acc.get("created_at"),
                    "last_login_at": acc.get("last_login_at"),
                    "login_count": acc.get("login_count", 0),
                    "is_active": acc.get("is_active", True),
                })
        return out

    # -------------------------------------------------------------- writes --
    def create(self, email: str, password: str, site_id: str) -> Dict[str, Any]:
        key = self._key(email)
        if key in self._accounts:
            raise ValueError("An account already exists for this email address.")
        problem = password_problem(password)
        if problem:
            raise ValueError(problem)

        self._accounts[key] = {
            "site_id": site_id,
            "password": hash_password(password),
            "created_at": _now(),
            "last_login_at": None,
            "login_count": 0,
            "is_active": True,
        }
        self._save()
        logger.info("Client account created for %s on site %s", key, site_id)
        return {"email": key, "site_id": site_id}

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """The account if the password matches, else None.

        Returns None for a missing account and for a wrong password alike, so
        the caller cannot tell a valid address from an invalid one.
        """
        acc = self.get(email)
        if not acc or not acc.get("is_active", True):
            # Still spend the work of a hash, so a missing account does not
            # answer faster than a wrong password.
            hash_password(password)
            return None
        if not verify_password(password, acc.get("password") or {}):
            return None

        key = self._key(email)
        self._accounts[key]["last_login_at"] = _now()
        self._accounts[key]["login_count"] = acc.get("login_count", 0) + 1
        self._save()
        return {"email": key, "site_id": acc.get("site_id")}

    def set_password(self, email: str, current_password: str, new_password: str) -> bool:
        acc = self.get(email)
        if not acc or not verify_password(current_password, acc.get("password") or {}):
            return False
        problem = password_problem(new_password)
        if problem:
            raise ValueError(problem)
        self._accounts[self._key(email)]["password"] = hash_password(new_password)
        self._accounts[self._key(email)]["password_changed_at"] = _now()
        self._save()
        return True

    def deactivate(self, email: str) -> bool:
        key = self._key(email)
        if key not in self._accounts:
            return False
        self._accounts[key]["is_active"] = False
        self._save()
        return True

    def delete_for_site(self, site_id: str) -> int:
        """Remove every account for a site. Used when the site is deleted."""
        gone = [e for e, a in self._accounts.items() if a.get("site_id") == site_id]
        for email in gone:
            del self._accounts[email]
        if gone:
            self._save()
        return len(gone)


client_accounts = ClientAccountStore()
