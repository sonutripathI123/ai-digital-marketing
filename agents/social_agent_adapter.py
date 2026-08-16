"""
Adapter for Corporate Cars Melbourne Social Media Agent (`corporate-cars-social-agent`).

Wraps existing social agent functionality into the standard AgentInterface,
connecting it to the central Master Orchestrator and AI Abstraction Layer.
Preserves 100% standalone CLI & API compatibility.
"""

import sys
import subprocess
from pathlib import Path
from typing import Any, Dict

from config.settings import ROOT_DIR
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

SOCIAL_AGENT_DIR = ROOT_DIR / "corporate-cars-social-agent"
SOCIAL_AGENT_VENV_PYTHON = SOCIAL_AGENT_DIR / ".venv" / "Scripts" / "python.exe"

if str(SOCIAL_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(SOCIAL_AGENT_DIR))

logger = get_agent_logger("corporate-cars-social-agent")


def get_social_python_executable() -> str:
    if SOCIAL_AGENT_VENV_PYTHON.exists():
        return str(SOCIAL_AGENT_VENV_PYTHON)
    return sys.executable


class SocialAgentAdapter(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="corporate-cars-social-agent",
            name="Corporate Cars Social Media Agent",
            description="Generates, staggers, and posts platform-specific social media content across 6 channels.",
            category="Social Media",
            enabled=True,
            paused=False,
            supported_actions=["status", "generate", "schedule", "publish-due", "add-keywords"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        action = str(task.input_data.get("action", "status")).lower().strip()
        keywords = str(task.input_data.get("keywords", "")).strip()
        platform = str(task.input_data.get("platform", "all")).lower().strip()
        logger.info(f"Executing SocialAgent task: action={action}, platform={platform}")

        if action == "generate_caption":
            prompt = f"Write a social media caption for platform {platform} targeting keyword '{keywords}'."
            llm_req = LLMRequest(
                user_prompt=prompt,
                task_type=TaskComplexity.STANDARD,
                json_output=True
            )
            response = router.route_and_execute(llm_req)
            return {
                "output": {
                    "action": action,
                    "platform": platform,
                    "response": response.content,
                    "parsed": response.parsed_json,
                },
                "model_used": response.model_used,
                "tokens_used": response.tokens_in + response.tokens_out,
                "cost_usd": response.cost_usd
            }

        # Subprocess execution for CLI action using dedicated python executable
        python_bin = get_social_python_executable()
        cmd = [python_bin, "cli.py", action]
        if action == "generate":
            if keywords:
                cmd.extend(["--keywords", keywords])
            cmd.extend(["--platform", platform])
        elif action == "schedule":
            weeks = str(task.input_data.get("weeks", 1))
            cmd.extend(["--weeks", weeks])

        result = subprocess.run(
            cmd,
            cwd=SOCIAL_AGENT_DIR,
            text=True,
            capture_output=True,
            timeout=300
        )

        output_str = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode != 0:
            raise RuntimeError(f"Social Agent CLI execution failed: {output_str}")

        return {
            "output": {
                "action": action,
                "platform": platform,
                "details": output_str
            },
            "model_used": "subprocess-agent-flow",
            "tokens_used": 0,
            "cost_usd": 0.0
        }
