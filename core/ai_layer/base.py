"""
Base interfaces and data structures for the Provider-Independent AI Abstraction Layer.
"""

from abc import ABC, abstractmethod
from enum import Enum
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class TaskComplexity(str, Enum):
    ROUTINE = "ROUTINE"        # Formatting, classification, extraction, validation
    STANDARD = "STANDARD"      # Social captions, routine SEO content, blog drafting, metadata
    COMPLEX = "COMPLEX"        # Strategy, competitor analysis, deep reasoning, debugging, architecture


class LLMRequest(BaseModel):
    user_prompt: str
    system_prompt: Optional[str] = None
    task_type: TaskComplexity = TaskComplexity.STANDARD
    temperature: float = 0.7
    max_tokens: int = 2000
    json_output: bool = False
    preferred_model: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str
    parsed_json: Optional[Any] = None
    model_used: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    retry_count: int = 0


class BaseAIProvider(ABC):
    """Abstract base class for all AI provider adapters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the provider name (e.g. 'anthropic', 'gemini', 'mock')."""
        pass

    @abstractmethod
    def generate(self, request: LLMRequest, model_override: Optional[str] = None) -> LLMResponse:
        """Executes a generation request against the provider."""
        pass
