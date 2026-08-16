"""
Agent #3: SEO Content Brief Agent (`seo-content-brief-agent`).

Generates structured SEO content briefs, H1/H2/H3 outlines, target word counts,
internal linking suggestions, and CTAs for blog posts and landing pages.
"""

from typing import Any, Dict, List
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("seo-content-brief-agent")


class SEOContentBriefAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="seo-content-brief-agent",
            name="SEO Content Brief Agent",
            description="Generates structured content briefs, title options, H2/H3 outlines, and SEO requirements for writers.",
            category="SEO & Content",
            enabled=True,
            paused=False,
            supported_actions=["create_brief", "outline", "suggestions"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "create_brief")).lower().strip()
        target_keyword = str(input_data.get("target_keyword", "corporate chauffeur melbourne")).strip()
        location = str(input_data.get("location", "Melbourne")).strip()
        secondary_keywords = input_data.get("secondary_keywords") or [
            f"airport transfer {location}",
            "luxury private driver",
            "executive car hire"
        ]
        target_audience = str(input_data.get("target_audience", "Corporate Travelers & Event Planners")).strip()
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing SEOContentBriefAgent task: action={action}, target_kw='{target_keyword}', location='{location}'")

        # Deterministic Brief Generation Engine
        h1_titles = [
            f"Ultimate Guide to {target_keyword.title()} in {location}",
            f"Why Premium {target_keyword.title()} is Essential for Corporate Travel",
            f"Top Benefits of Hiring a {target_keyword.title()} in {location}"
        ]

        outline = [
            {"heading": f"1. Introduction to {target_keyword.title()}", "level": "H2", "key_points": ["Problem statement", "Why luxury transport matters"]},
            {"heading": "2. Key Benefits of Professional Corporate Chauffeurs", "level": "H2", "key_points": ["Punctuality", "Privacy & Comfort", "Flight Tracking"]},
            {"heading": f"3. Airport Transfers & Executive Routes in {location}", "level": "H2", "key_points": ["Tullamarine Airport pickups", "CBD hotel transfers"]},
            {"heading": "4. How to Book Your Dedicated Chauffeur Service", "level": "H2", "key_points": ["Online reservation", "Corporate account options"]},
            {"heading": "5. Conclusion & Call to Action", "level": "H2", "key_points": ["Summary", "Book Now CTA"]}
        ]

        result_payload = {
            "action": action,
            "target_keyword": target_keyword,
            "target_location": location,
            "target_audience": target_audience,
            "recommended_word_count": "1,200 - 1,500 words",
            "search_intent": "Transactional / Commercial",
            "title_suggestions": h1_titles,
            "secondary_keywords": secondary_keywords,
            "structured_outline": outline,
            "internal_linking_recommendations": [
                f"/services/airport-transfers (Anchor: 'airport transfer {location}')",
                f"/fleet/executive-sedans (Anchor: 'executive car hire')"
            ],
            "call_to_action": "Reserve your premium Melbourne chauffeur online today or contact our 24/7 corporate desk.",
            "seo_requirements": [
                "Include primary keyword in H1 and first 100 words.",
                "Maintain 1.5% keyword density for secondary terms.",
                "Add alt text for featured vehicle images."
            ]
        }

        # Optional AI Enrichment
        tokens_used = 0
        cost_usd = 0.0
        model_used = "rule-based-brief-engine"

        if use_ai:
            prompt = (
                f"Create a detailed SEO Content Brief for target keyword '{target_keyword}' in '{location}' "
                f"targeting audience '{target_audience}'. Include title options, H2/H3 outline, and CTA."
            )
            llm_req = LLMRequest(
                user_prompt=prompt,
                task_type=TaskComplexity.STANDARD,
                json_output=True
            )
            try:
                response = router.route_and_execute(llm_req)
                model_used = response.model_used
                tokens_used = response.tokens_in + response.tokens_out
                cost_usd = response.cost_usd
                if response.parsed_json:
                    result_payload["ai_insights"] = response.parsed_json
                else:
                    result_payload["ai_summary"] = response.content
            except Exception as e:
                logger.warning(f"AI content brief generation failed (fallback to rule engine): {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
