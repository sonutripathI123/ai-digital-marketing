"""
Real Google Ads API Live Client.

This module performs ACTUAL live calls to the Google Ads API (read-only GAQL
queries) using OAuth credentials. It is intentionally defensive: if the
`google-ads` library is not installed, or credentials are missing/incomplete,
it degrades gracefully and reports *why* it could not go live — instead of
silently returning fake data.

Required credentials (all five) to go live:
  - developer_token
  - client_id
  - client_secret
  - refresh_token
  - customer_id            (the 10-digit account id, dashes allowed)
Optional:
  - login_customer_id      (MCC / manager account id, if the account sits
                            under a manager account)

Credentials are resolved, in priority order:
  1. An explicit dict passed to the constructor.
  2. Per-site saved credentials (config.websites) for the given site_id.
  3. Environment variables:
       GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CLIENT_ID,
       GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_REFRESH_TOKEN,
       GOOGLE_ADS_CUSTOMER_ID, GOOGLE_ADS_LOGIN_CUSTOMER_ID
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("google_ads_live_client")

# Credential keys we treat as mandatory for a live connection.
REQUIRED_KEYS = ("developer_token", "client_id", "client_secret", "refresh_token", "customer_id")

# Map of env-var name -> credential key.
_ENV_MAP = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "developer_token",
    "GOOGLE_ADS_CLIENT_ID": "client_id",
    "GOOGLE_ADS_CLIENT_SECRET": "client_secret",
    "GOOGLE_ADS_REFRESH_TOKEN": "refresh_token",
    "GOOGLE_ADS_CUSTOMER_ID": "customer_id",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "login_customer_id",
}

# GAQL date-range presets we accept from callers, mapped to Google's tokens.
_DATE_PRESETS = {
    "today": "TODAY",
    "current_day": "TODAY",
    "yesterday": "YESTERDAY",
    "last_7_days": "LAST_7_DAYS",
    "last_14_days": "LAST_14_DAYS",
    "last_30_days": "LAST_30_DAYS",
    "last_month": "LAST_MONTH",
    "this_month": "THIS_MONTH",
    "all_time": "LAST_30_DAYS",  # Google has no ALL_TIME preset; default sensibly.
}


def _digits_only(value: Optional[str]) -> str:
    """Strip everything but digits (Google Ads ids must be digits, no dashes)."""
    if not value:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def _date_token(date_range: str) -> str:
    return _DATE_PRESETS.get(str(date_range or "").lower().strip(), "LAST_30_DAYS")


def resolve_credentials(
    explicit: Optional[Dict[str, Any]] = None,
    site_id: Optional[str] = None,
) -> Dict[str, str]:
    """Merge credentials from explicit dict, per-site store, and environment.

    Later sources only fill gaps left by earlier ones.
    """
    creds: Dict[str, str] = {}

    # 1. Explicit dict (highest priority).
    if explicit:
        for k, v in explicit.items():
            if v is not None and str(v).strip() and not str(v).startswith("•"):
                creds[k] = str(v).strip()

    # 2. Per-site saved credentials.
    if site_id:
        try:
            from config.websites import websites_manager  # local import to avoid cycles

            for agent_id in ("google-ads-monitoring-agent", "google-ads-optimization-agent"):
                saved = websites_manager.get_agent_credentials(site_id, agent_id) or {}
                for k, v in saved.items():
                    if k not in creds and v is not None and str(v).strip():
                        creds[k] = str(v).strip()
        except Exception as e:  # pragma: no cover - defensive
            logger.debug(f"Could not load per-site Google Ads credentials for '{site_id}': {e}")

    # 3. Environment variables (lowest priority).
    for env_name, key in _ENV_MAP.items():
        if key not in creds:
            val = os.getenv(env_name)
            if val and val.strip():
                creds[key] = val.strip()

    return creds


class GoogleAdsLiveClient:
    """Thin, read-only wrapper over the official Google Ads API client."""

    def __init__(
        self,
        credentials: Optional[Dict[str, Any]] = None,
        site_id: Optional[str] = None,
    ):
        self.site_id = site_id
        self.credentials = resolve_credentials(credentials, site_id)
        self.customer_id = _digits_only(self.credentials.get("customer_id"))
        self.login_customer_id = _digits_only(self.credentials.get("login_customer_id"))
        self._client = None  # lazily built GoogleAdsClient

    # ------------------------------------------------------------------ #
    # Readiness / diagnostics
    # ------------------------------------------------------------------ #
    def missing_keys(self) -> List[str]:
        """Which required credential keys are still absent."""
        return [k for k in REQUIRED_KEYS if not self.credentials.get(k)]

    def library_available(self) -> bool:
        try:
            import google.ads.googleads.client  # noqa: F401

            return True
        except Exception:
            return False

    def is_configured(self) -> bool:
        """True only if the library is importable AND all required creds exist."""
        return self.library_available() and not self.missing_keys()

    def status(self) -> Dict[str, Any]:
        """Human-readable readiness report (never raises)."""
        missing = self.missing_keys()
        lib = self.library_available()
        if lib and not missing:
            reason = "READY — all credentials present and library installed."
            code = "READY"
        elif not lib and missing:
            reason = "Library 'google-ads' not installed AND credentials incomplete."
            code = "NOT_READY"
        elif not lib:
            reason = "Python package 'google-ads' is not installed (pip install google-ads)."
            code = "LIBRARY_MISSING"
        else:
            reason = f"Missing credentials: {', '.join(missing)}."
            code = "CREDENTIALS_MISSING"
        return {
            "code": code,
            "ready": bool(lib and not missing),
            "library_installed": lib,
            "missing_credentials": missing,
            "customer_id": self.customer_id or None,
            "login_customer_id": self.login_customer_id or None,
            "reason": reason,
        }

    # ------------------------------------------------------------------ #
    # Client construction
    # ------------------------------------------------------------------ #
    def _build_client(self):
        if self._client is not None:
            return self._client
        from google.ads.googleads.client import GoogleAdsClient  # type: ignore

        config: Dict[str, Any] = {
            "developer_token": self.credentials["developer_token"],
            "client_id": self.credentials["client_id"],
            "client_secret": self.credentials["client_secret"],
            "refresh_token": self.credentials["refresh_token"],
            "use_proto_plus": True,
        }
        if self.login_customer_id:
            config["login_customer_id"] = self.login_customer_id
        self._client = GoogleAdsClient.load_from_dict(config)
        return self._client

    def _search(self, query: str) -> List[Any]:
        """Run a GAQL query and return the streamed rows."""
        client = self._build_client()
        service = client.get_service("GoogleAdsService")
        rows: List[Any] = []
        stream = service.search_stream(customer_id=self.customer_id, query=query)
        for batch in stream:
            for row in batch.results:
                rows.append(row)
        return rows

    # ------------------------------------------------------------------ #
    # Live reads
    # ------------------------------------------------------------------ #
    def test_connection(self) -> Dict[str, Any]:
        """Lightweight live check: fetch the account descriptive name & currency."""
        if not self.is_configured():
            st = self.status()
            return {"success": False, "live": False, **st}
        try:
            rows = self._search(
                "SELECT customer.id, customer.descriptive_name, customer.currency_code, "
                "customer.time_zone FROM customer LIMIT 1"
            )
            if not rows:
                return {"success": True, "live": True, "account": None,
                        "message": "Connected, but no customer row returned."}
            c = rows[0].customer
            return {
                "success": True,
                "live": True,
                "account": {
                    "customer_id": str(c.id),
                    "name": c.descriptive_name,
                    "currency": c.currency_code,
                    "time_zone": c.time_zone,
                },
                "message": f"✅ Live connection verified for account {c.id} ({c.descriptive_name}).",
            }
        except Exception as e:
            return {
                "success": False,
                "live": False,
                "code": "API_ERROR",
                "error": str(e),
                "message": f"❌ Google Ads API rejected the request: {e}",
            }

    def get_campaign_performance(self, date_range: str = "last_30_days") -> Dict[str, Any]:
        """Live campaign-level metrics for the given date range."""
        token = _date_token(date_range)
        query = f"""
            SELECT
              campaign.id,
              campaign.name,
              campaign.status,
              campaign.advertising_channel_type,
              campaign_budget.amount_micros,
              customer.currency_code,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions,
              metrics.conversions_value,
              metrics.ctr,
              metrics.average_cpc
            FROM campaign
            WHERE segments.date DURING {token}
              AND campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
        """
        rows = self._search(query)
        campaigns: List[Dict[str, Any]] = []
        currency = "USD"
        tot_cost = tot_clicks = tot_impr = 0.0
        tot_conv = tot_conv_val = 0.0
        for r in rows:
            currency = r.customer.currency_code or currency
            cost = r.metrics.cost_micros / 1_000_000
            conv = float(r.metrics.conversions)
            conv_val = float(r.metrics.conversions_value)
            clicks = int(r.metrics.clicks)
            impr = int(r.metrics.impressions)
            campaigns.append({
                "campaign_id": str(r.campaign.id),
                "campaign_name": r.campaign.name,
                "status": r.campaign.status.name,
                "channel": r.campaign.advertising_channel_type.name,
                "daily_budget": round(r.campaign_budget.amount_micros / 1_000_000, 2),
                "spend": round(cost, 2),
                "impressions": impr,
                "clicks": clicks,
                "ctr_percent": round(r.metrics.ctr * 100, 2),
                "avg_cpc": round(r.metrics.average_cpc / 1_000_000, 2),
                "conversions": round(conv, 2),
                "conv_value": round(conv_val, 2),
                "cpa": round(cost / conv, 2) if conv else 0.0,
                "roas": round(conv_val / cost, 2) if cost else 0.0,
            })
            tot_cost += cost
            tot_clicks += clicks
            tot_impr += impr
            tot_conv += conv
            tot_conv_val += conv_val
        summary = {
            "total_spend": round(tot_cost, 2),
            "total_clicks": int(tot_clicks),
            "total_impressions": int(tot_impr),
            "total_conversions": round(tot_conv, 2),
            "avg_ctr_percent": round((tot_clicks / tot_impr * 100), 2) if tot_impr else 0.0,
            "avg_cpc": round(tot_cost / tot_clicks, 2) if tot_clicks else 0.0,
            "avg_cpa": round(tot_cost / tot_conv, 2) if tot_conv else 0.0,
            "overall_roas": round(tot_conv_val / tot_cost, 2) if tot_cost else 0.0,
            "currency": currency,
        }
        return {"campaigns": campaigns, "summary": summary,
                "currency": currency, "date_range": token}

    def get_keyword_performance(self, date_range: str = "last_30_days",
                                limit: int = 200) -> List[Dict[str, Any]]:
        """Live keyword-level metrics (with quality score & match type)."""
        token = _date_token(date_range)
        query = f"""
            SELECT
              ad_group_criterion.keyword.text,
              ad_group_criterion.keyword.match_type,
              ad_group_criterion.quality_info.quality_score,
              campaign.name,
              ad_group.name,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions,
              metrics.ctr,
              metrics.average_cpc
            FROM keyword_view
            WHERE segments.date DURING {token}
              AND ad_group_criterion.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
            LIMIT {int(limit)}
        """
        rows = self._search(query)
        keywords: List[Dict[str, Any]] = []
        for r in rows:
            cost = r.metrics.cost_micros / 1_000_000
            conv = float(r.metrics.conversions)
            keywords.append({
                "keyword": r.ad_group_criterion.keyword.text,
                "match_type": r.ad_group_criterion.keyword.match_type.name,
                "quality_score": (r.ad_group_criterion.quality_info.quality_score
                                  if r.ad_group_criterion.quality_info.quality_score else None),
                "campaign": r.campaign.name,
                "ad_group": r.ad_group.name,
                "impressions": int(r.metrics.impressions),
                "clicks": int(r.metrics.clicks),
                "spend": round(cost, 2),
                "ctr_percent": round(r.metrics.ctr * 100, 2),
                "avg_cpc": round(r.metrics.average_cpc / 1_000_000, 2),
                "conversions": round(conv, 2),
                "cpa": round(cost / conv, 2) if conv else 0.0,
            })
        return keywords

    def get_search_terms(self, date_range: str = "last_30_days",
                         limit: int = 200) -> List[Dict[str, Any]]:
        """Live search-term report (what users actually typed)."""
        token = _date_token(date_range)
        query = f"""
            SELECT
              search_term_view.search_term,
              campaign.name,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions,
              metrics.ctr
            FROM search_term_view
            WHERE segments.date DURING {token}
            ORDER BY metrics.cost_micros DESC
            LIMIT {int(limit)}
        """
        rows = self._search(query)
        terms: List[Dict[str, Any]] = []
        for r in rows:
            cost = r.metrics.cost_micros / 1_000_000
            conv = float(r.metrics.conversions)
            terms.append({
                "search_term": r.search_term_view.search_term,
                "campaign": r.campaign.name,
                "impressions": int(r.metrics.impressions),
                "clicks": int(r.metrics.clicks),
                "spend": round(cost, 2),
                "ctr_percent": round(r.metrics.ctr * 100, 2),
                "conversions": round(conv, 2),
                "cpa": round(cost / conv, 2) if conv else 0.0,
            })
        return terms
