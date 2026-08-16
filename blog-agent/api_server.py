import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

APP_FOLDER = Path(__file__).resolve().parent
VENV_PYTHON = APP_FOLDER / ".venv" / "Scripts" / "python.exe"
os.environ["PYTHONUTF8"] = "1"

app = FastAPI(title="Chauffeur Blog Agent API")


class AgentRequest(BaseModel):
    taskId: str
    agentId: str
    input: dict = Field(default_factory=dict)
    requestedAt: str | None = None


def run_blog_agent(arguments: list[str]) -> str:
    # Always use this project's virtual environment.  The API server itself
    # may be started by Windows with a different Python installation.
    python_executable = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    result = subprocess.run(
        [python_executable, "blog_agent.py", *arguments],
        cwd=APP_FOLDER,
        text=True,
        capture_output=True,
        timeout=600,
        env={**os.environ, "PYTHONUTF8": "1"},
    )

    output = (result.stdout + "\n" + result.stderr).strip()

    if result.returncode != 0:
        raise RuntimeError(output or "Blog Agent command failed.")

    return output


@app.get("/health")
def health():
    return {"status": "healthy", "agent": "chauffeur-blog-agent"}


@app.post("/run")
def run_agent(request: AgentRequest):
    data = request.input
    action = str(data.get("action", "status")).lower().strip()

    try:
        if action == "status":
            output = run_blog_agent(["status"])

            return {
                "status": "completed",
                "output": {
                    "action": "status",
                    "message": "Blog queue status loaded.",
                    "details": output,
                },
            }

        if action == "write":
            site = str(data.get("site", "ccm")).strip()

            if not site:
                raise HTTPException(
                    status_code=400,
                    detail="Please provide a site, for example: ccm",
                )

            output = run_blog_agent(["write", "--site", site])

            return {
                "status": "completed",
                "output": {
                    "action": "write",
                    "site": site,
                    "message": "Approved topics were converted into WordPress drafts.",
                    "details": output,
                },
            }

        if action == "publish":
            output = run_blog_agent(["publish"])

            return {
                "status": "completed",
                "output": {
                    "action": "publish",
                    "message": "Eligible reviewed drafts were sent live.",
                    "details": output,
                },
            }

        raise HTTPException(
            status_code=400,
            detail="Invalid action. Use: status, write, or publish.",
        )

    except HTTPException:
        raise
    except Exception as error:
        return {
            "status": "failed",
            "message": str(error),
        }
