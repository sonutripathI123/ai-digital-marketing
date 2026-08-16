"""
Base Ads Integration Adapter.

Strictly enforces safety guards: ADS_LIVE_EXECUTION_ENABLED is false by default.
No live API campaign creation, budget changes, bidding changes, or account mutations
can execute unless ADS_LIVE_EXECUTION_ENABLED is true AND explicit human approval is provided.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict
from config.settings import ADS_LIVE_EXECUTION_ENABLED

logger = logging.getLogger("ads_integration")


class BaseAdsAdapter(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        pass

    def execute_mutation(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Guarded execution interface for ad platform mutations.
        Returns simulation response if ADS_LIVE_EXECUTION_ENABLED is false.
        """
        if not ADS_LIVE_EXECUTION_ENABLED:
            logger.warning(
                f"[ADS SAFETY GUARD ACTIVE] Blocked live {self.platform_name} mutation '{action}'. "
                f"Params: {parameters}. Returning simulation object."
            )
            return {
                "status": "SIMULATED",
                "live_executed": False,
                "platform": self.platform_name,
                "action": action,
                "parameters": parameters,
                "message": f"Safety Guard Active: {self.platform_name} mutation '{action}' simulated safely with 0 budget impact.",
            }

        return self._execute_live_mutation(action, parameters)

    @abstractmethod
    def _execute_live_mutation(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        pass
