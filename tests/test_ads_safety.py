"""
Unit tests to verify Ads Safety Guards remain active and zero budget mutations occur.
"""

import unittest
from integrations.ads.google_ads import GoogleAdsAdapter
from integrations.ads.meta_ads import MetaAdsAdapter


class TestAdsSafety(unittest.TestCase):
    def test_google_ads_safety_guard(self):
        adapter = GoogleAdsAdapter()
        result = adapter.execute_mutation("create_campaign", {"budget": 1000, "name": "Test Campaign"})

        self.assertEqual(result["status"], "SIMULATED")
        self.assertFalse(result["live_executed"])
        self.assertEqual(result["platform"], "google_ads")
        self.assertIn("Safety Guard Active", result["message"])

    def test_meta_ads_safety_guard(self):
        adapter = MetaAdsAdapter()
        result = adapter.execute_mutation("update_bid", {"ad_id": "12345", "bid": 5.0})

        self.assertEqual(result["status"], "SIMULATED")
        self.assertFalse(result["live_executed"])
        self.assertEqual(result["platform"], "meta_ads")
        self.assertIn("Safety Guard Active", result["message"])


if __name__ == "__main__":
    unittest.main()
