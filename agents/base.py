"""
Standard AgentInterface for all Command Center sub-agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from core.ai_layer.router import ModelRouter
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata


class AgentInterface(ABC):
    """Abstract base class for all Command Center sub-agents."""

    @property
    @abstractmethod
    def metadata(self) -> AgentMetadata:
        """Returns the AgentMetadata structure."""
        pass

    @abstractmethod
    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        """
        Executes a task assigned by the Master Orchestrator.
        Returns a dictionary containing 'output', 'model_used', 'tokens_used', 'cost_usd'.
        """
        pass
