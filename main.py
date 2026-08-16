"""
Production Entrypoint for AI Digital Marketing Command Center.

Starts the FastAPI server with production settings, binds to PORT, and initializes sub-agents.
"""

import os
import uvicorn
from dashboard.api import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    print(f"🚀 Starting AI Digital Marketing Command Center on http://{host}:{port}")
    uvicorn.run(
        "dashboard.api:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
