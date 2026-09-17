"""No agent may answer for a site it was not asked about.

Eight agents carried Corporate Cars Melbourne as their default target: its
domain, its GA4 property, its brand name, its Facebook page, one of its
campaign names. A task for any other site -- including a brand-new one added
from the admin panel -- got CCM's data under that site's heading, so onboarding
a second client would have shown them another business's traffic and spend.

This test adds a site, runs every registered agent for it, and fails if CCM
appears anywhere in the answer.
"""
import json
import os
import unittest

os.environ.setdefault("SCHEDULER_ENABLED", "false")

# Markers that can only come from Corporate Cars Melbourne.
CCM_MARKERS = {
    "corporatecarsmelbourne": "CCM's domain",
    "550393874": "CCM's GA4 property",
    "1949408641": "CCM's Google Ads account",
    "16Aug_Ads_Campaign": "CCM's campaign name",
    "Corporate Cars": "CCM's brand name",
}

# These two shell out to a CLI that has no "audit" action; they fail the same
# way for every site and never reach a data source, so there is nothing here
# for them to leak.
SHELLS_OUT = {"blog-agent", "corporate-cars-social-agent"}


class _Task:
    def __init__(self, site_id, action="audit"):
        self.task_id = f"leak-check-{site_id}"
        self.agent_id = ""
        self.task_type = action
        self.site_id = site_id
        self.input_data = {"action": action, "site_id": site_id}


class TestNoDefaultSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from config.websites import WebsiteManager, WebsiteProfile
        from dashboard.api import orchestrator, router

        cls.orchestrator = orchestrator
        cls.router = router
        cls.manager = WebsiteManager()
        cls.site_id = "leakcheck-site"
        cls.manager.add_website(WebsiteProfile(
            site_id=cls.site_id,
            name="Leak Check Pty Ltd",
            domain="https://leakcheck.example.com",
            location="Sydney, NSW",
            niche="Test",
            default_category="Test",
            is_active=True,
        ))

    @classmethod
    def tearDownClass(cls):
        try:
            cls.manager.delete_website(cls.site_id)
        except Exception:
            pass

    def test_no_agent_answers_with_another_sites_data(self):
        offenders = {}
        for agent_id, agent in self.orchestrator._agent_instances.items():
            if agent_id in SHELLS_OUT:
                continue
            try:
                out = agent.run_task(_Task(self.site_id), self.router)
            except Exception:
                # A failure is not a leak; it reports nothing at all.
                continue
            blob = json.dumps(out, default=str)
            found = [why for marker, why in CCM_MARKERS.items() if marker in blob]
            if found:
                offenders[agent_id] = found

        self.assertEqual(
            offenders, {},
            "These agents answered a task for another website with Corporate "
            f"Cars Melbourne's data: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
