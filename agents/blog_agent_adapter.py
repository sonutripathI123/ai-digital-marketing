"""
Adapter for Chauffeur Blog Agent (`blog-agent`).

Wraps existing blog-agent functionality into the standard AgentInterface,
connecting it to the central Master Orchestrator and AI Abstraction Layer.
Preserves 100% standalone CLI & API compatibility.
"""

import sys
import subprocess
from pathlib import Path
from typing import Any, Dict

from config.settings import ROOT_DIR
from config.blog_credentials_bridge import connection_status, env_overrides
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

BLOG_AGENT_DIR = ROOT_DIR / "blog-agent"
BLOG_AGENT_VENV_PYTHON = BLOG_AGENT_DIR / ".venv" / "Scripts" / "python.exe"

if str(BLOG_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(BLOG_AGENT_DIR))

logger = get_agent_logger("blog-agent")


def get_blog_python_executable() -> str:
    if Path(r"C:\Python314\python.exe").exists():
        return r"C:\Python314\python.exe"
    if BLOG_AGENT_VENV_PYTHON.exists():
        return str(BLOG_AGENT_VENV_PYTHON)
    return sys.executable


class BlogAgentAdapter(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="blog-agent",
            name="Corporate Cars Blog Agent",
            description="Auto-posts SEO blog posts on WordPress chauffeur sites with hybrid approval model.",
            category="SEO & Content",
            enabled=True,
            paused=False,
            supported_actions=["status", "write", "publish", "suggest", "import"],
            version="1.0.0"
        )

    @staticmethod
    def _require_publishing_credentials(action: str, site: str, env: Dict[str, str]) -> None:
        """Fail early, and legibly, when a run cannot possibly publish.

        Without this the CLI exits with a bare "Missing CCM_WP_USER /
        CCM_WP_APP_PASSWORD in environment" that says nothing about where to put
        them, and the scheduler burns every retry on a condition no retry fixes.
        """
        if action not in ("write", "publish"):
            return

        status = connection_status(site, env)
        if not status["ready"]:
            raise RuntimeError(
                f"Blog Agent cannot publish for site '{site}': no WordPress credentials. "
                f"Missing {' and '.join(status['missing'])}. "
                f"Fix this in the dashboard under Integrations > WordPress Blog Agent "
                f"(username + application password), or set those variables in the "
                f"environment / blog-agent/.env on the server."
            )

        if action == "write" and not (env.get("ANTHROPIC_API_KEY") or "").strip():
            raise RuntimeError(
                "Blog Agent cannot write a post: ANTHROPIC_API_KEY is not set. "
                "The post generator calls Anthropic directly, so the key must be "
                "present in the server environment (or blog-agent/.env) — the "
                "dashboard's AI provider setting does not reach this subprocess."
            )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        action = str(task.input_data.get("action", "status")).lower().strip()
        site = str(task.input_data.get("site", "ccm")).strip()
        logger.info(f"Executing BlogAgent task: action={action}, site={site}")

        if action == "generate_topic" or action == "suggest":
            theme = task.input_data.get("theme", "")
            prompt = f"Propose 5 fresh blog topics for site {site}." + (f" Theme: {theme}" if theme else "")
            llm_req = LLMRequest(
                user_prompt=prompt,
                task_type=TaskComplexity.STANDARD,
                json_output=True,
            )
            response = router.route_and_execute(llm_req)
            return {
                "output": {
                    "action": action,
                    "site": site,
                    "response": response.content,
                    "parsed": response.parsed_json,
                },
                "model_used": response.model_used,
                "tokens_used": response.tokens_in + response.tokens_out,
                "cost_usd": response.cost_usd,
            }

        # Execute existing subprocess / command logic safely using dedicated Python executable
        python_bin = get_blog_python_executable()
        cmd = [python_bin, "blog_agent.py", action]
        if action == "write" and site:
            cmd.extend(["--site", site])
        if action == "publish" and task.input_data.get("force", True):
            cmd.append("--force")

        import os

        # The CLI resolves WordPress credentials from site-prefixed environment
        # variables kept in blog-agent/.env — a gitignored file that is absent
        # from any deployment built from the repository. Hand it whatever the
        # operator saved through the dashboard so scheduled runs keep publishing
        # there too. Real environment variables are never overwritten.
        child_env = dict(os.environ)
        child_env.update(env_overrides(child_env))

        self._require_publishing_credentials(action, site, child_env)

        result = subprocess.run(
            cmd,
            cwd=BLOG_AGENT_DIR,
            text=True,
            capture_output=True,
            timeout=300,
            env=child_env
        )

        output_str = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode != 0:
            raise RuntimeError(f"Blog Agent CLI execution failed: {output_str}")

        return {
            "output": {
                "action": action,
                "site": site,
                "details": output_str
            },
            "model_used": "subprocess-agent-flow",
            "tokens_used": 0,
            "cost_usd": 0.0
        }
