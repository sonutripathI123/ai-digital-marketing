import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

APP_FOLDER = Path(__file__).resolve().parent
VALID_PLATFORMS = {
    "all", "instagram", "facebook", "linkedin", "x", "threads", "pinterest"
}

app = FastAPI(title="Corporate Cars Social Agent API")


class AgentRequest(BaseModel):
    taskId: str
    agentId: str
    input: dict = Field(default_factory=dict)
    requestedAt: str | None = None


def run_cli(arguments: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, "cli.py", *arguments],
        cwd=APP_FOLDER,
        text=True,
        capture_output=True,
        timeout=300,
    )

    output = (result.stdout + "\n" + result.stderr).strip()

    if result.returncode != 0:
        raise RuntimeError(output or "Social agent command failed.")

    return output


@app.get("/health")
def health():
    return {"status": "healthy", "agent": "corporate-cars-social-agent"}


@app.post("/run")
def run_agent(request: AgentRequest):
    task_input = request.input
    action = task_input.get("action", "generate")

    try:
        if action == "generate":
            keywords = str(task_input.get("keywords", "")).strip()
            platform = str(task_input.get("platform", "all")).lower().strip()
            category = str(task_input.get("category", "")).strip()

            if not keywords:
                raise HTTPException(
                    status_code=400,
                    detail="Please provide keywords."
                )

            if platform not in VALID_PLATFORMS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid platform. Use one of: {', '.join(sorted(VALID_PLATFORMS))}"
                )

            command = ["generate", "--keywords", keywords, "--platform", platform]

            if category:
                command.extend(["--category", category])

            output = run_cli(command)

            return {
                "status": "completed",
                "output": {
                    "action": "generate",
                    "message": "Draft posts generated successfully.",
                    "details": output,
                },
            }

        if action == "schedule":
            weeks = int(task_input.get("weeks", 1))

            if weeks < 1 or weeks > 12:
                raise HTTPException(
                    status_code=400,
                    detail="Weeks must be between 1 and 12."
                )

            output = run_cli(["schedule", "--weeks", str(weeks)])

            return {
                "status": "completed",
                "output": {
                    "action": "schedule",
                    "message": "Posts scheduled successfully.",
                    "details": output,
                },
            }

        if action == "status":
            output = run_cli(["status"])

            return {
                "status": "completed",
                "output": {
                    "action": "status",
                    "message": "Social agent status loaded.",
                    "details": output,
                },
            }

        raise HTTPException(
            status_code=400,
            detail="Invalid action. Use: generate, schedule, or status."
        )

    except HTTPException:
        raise
    except Exception as error:
        return {
            "status": "failed",
            "message": str(error),
        }