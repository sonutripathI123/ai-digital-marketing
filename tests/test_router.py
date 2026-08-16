"""
Unit tests for Intelligent Model Router.
"""

import unittest
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter


class TestModelRouter(unittest.TestCase):
    def test_router_task_complexity_routing(self):
        router = ModelRouter(use_mock=True)

        req_routine = LLMRequest(user_prompt="Format json", task_type=TaskComplexity.ROUTINE)
        resp_routine = router.route_and_execute(req_routine)
        self.assertTrue(resp_routine.success)

        req_standard = LLMRequest(user_prompt="Write blog", task_type=TaskComplexity.STANDARD)
        resp_standard = router.route_and_execute(req_standard)
        self.assertTrue(resp_standard.success)

        req_complex = LLMRequest(user_prompt="Analyze SEO competition", task_type=TaskComplexity.COMPLEX)
        resp_complex = router.route_and_execute(req_complex)
        self.assertTrue(resp_complex.success)

    def test_router_fallback_mechanism(self):
        router = ModelRouter(use_mock=True)
        req = LLMRequest(user_prompt="Test fallback", task_type=TaskComplexity.COMPLEX)
        resp = router.route_and_execute(req)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "mock")


if __name__ == "__main__":
    unittest.main()
