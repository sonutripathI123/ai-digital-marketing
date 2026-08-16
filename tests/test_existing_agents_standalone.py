"""
Unit tests verifying existing Blog Agent and Social Media Agent remain
100% operational in standalone mode without breaking changes.
"""

import subprocess
import sys
import unittest
from config.settings import ROOT_DIR

BLOG_AGENT_VENV_PYTHON = ROOT_DIR / "blog-agent" / ".venv" / "Scripts" / "python.exe"
SOCIAL_AGENT_VENV_PYTHON = ROOT_DIR / "corporate-cars-social-agent" / ".venv" / "Scripts" / "python.exe"


class TestExistingAgentsStandalone(unittest.TestCase):
    def test_blog_agent_standalone_status(self):
        blog_agent_dir = ROOT_DIR / "blog-agent"
        python_executable = str(BLOG_AGENT_VENV_PYTHON) if BLOG_AGENT_VENV_PYTHON.exists() else sys.executable

        result = subprocess.run(
            [python_executable, "blog_agent.py", "status"],
            cwd=blog_agent_dir,
            text=True,
            capture_output=True,
            timeout=60
        )

        self.assertEqual(result.returncode, 0)
        self.assertTrue("Queue summary:" in result.stdout or "TOTAL" in result.stdout)

    def test_social_agent_standalone_status(self):
        social_agent_dir = ROOT_DIR / "corporate-cars-social-agent"
        python_executable = str(SOCIAL_AGENT_VENV_PYTHON) if SOCIAL_AGENT_VENV_PYTHON.exists() else sys.executable

        result = subprocess.run(
            [python_executable, "cli.py", "status"],
            cwd=social_agent_dir,
            text=True,
            capture_output=True,
            timeout=60
        )

        self.assertEqual(result.returncode, 0)
        self.assertTrue("Posts by platform / status:" in result.stdout)


if __name__ == "__main__":
    unittest.main()
