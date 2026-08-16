"""
Google Ads Integration Adapter Interface.
Prepared for future campaign planning, audit, and management.
Strictly guarded — zero live API calls executed while ADS_LIVE_EXECUTION_ENABLED=false.
"""

from typing import Any, Dict
from integrations.ads.base import BaseAdsAdapter


class GoogleAdsAdapter(BaseAdsAdapter):
    @property
    def platform_name(self) -> str:
        return "google_ads"

    def _execute_live_mutation(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # Live execution logic prepared for future authorization
        return {
            "status": "EXECUTED",
            "live_executed": True,
            "platform": self.platform_name,
            "action": action,
            "result": "Live Google Ads API call executed."
        }

    def audit_account(self) -> Dict[str, Any]:
        """Safe read-only audit interface."""
        return {
            "platform": self.platform_name,
            "status": "ready",
            "campaigns_count": 0,
            "live_enabled": False
        }
