"""
Agent Registry for registering, managing, pausing, and inspecting sub-agents.
"""

import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("agent_registry")


class AgentMetadata(BaseModel):
    agent_id: str
    name: str
    description: str
    category: str
    enabled: bool = True
    paused: bool = False
    supported_actions: List[str] = Field(default_factory=list)
    version: str = "1.0.0"


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentMetadata] = {}

    def register(self, metadata: AgentMetadata) -> None:
        self._agents[metadata.agent_id] = metadata
        logger.info(f"Registered agent: {metadata.agent_id} ({metadata.name})")

    def get(self, agent_id: str) -> Optional[AgentMetadata]:
        return self._agents.get(agent_id)

    def list_all(self) -> List[AgentMetadata]:
        return list(self._agents.values())

    def set_paused(self, agent_id: str, paused: bool) -> bool:
        if agent_id in self._agents:
            self._agents[agent_id].paused = paused
            logger.info(f"Agent {agent_id} paused status set to {paused}")
            return True
        return False

    def set_enabled(self, agent_id: str, enabled: bool) -> bool:
        if agent_id in self._agents:
            self._agents[agent_id].enabled = enabled
            logger.info(f"Agent {agent_id} enabled status set to {enabled}")
            return True
        return False
