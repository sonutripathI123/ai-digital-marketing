"""
Agent #1: SEO Keyword Research Agent (`seo-keyword-agent`).

Finds, expands, classifies search intent, and clusters keyword opportunities
for luxury chauffeur, corporate transport, and local suburb landing pages.
"""

from typing import Any, Dict, List
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("seo-keyword-agent")

SUBURB_MODIFIERS = [
    "Melbourne CBD", "South Yarra", "Tullamarine Airport", "St Kilda",
    "Brighton", "Toorak", "Frankston", "Richmond", "Docklands", "Crown Casino"
]

SERVICE_MODIFIERS = [
    "chauffeur service", "corporate car hire", "airport transfer",
    "luxury private driver", "wedding car service", "event transport"
]


class SEOKeywordAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="seo-keyword-agent",
            name="SEO Keyword Research Agent",
            description="Finds, expands, classifies search intent, and clusters high-opportunity SEO keywords for chauffeur and travel landing pages.",
            category="SEO & Content",
            enabled=True,
            paused=False,
            supported_actions=["research", "expand", "cluster", "analyze"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "research")).lower().strip()
        seed_keyword = str(input_data.get("seed_keyword") or input_data.get("keyword") or "corporate chauffeur melbourne").strip()
        location = str(input_data.get("location", "Melbourne")).strip()
        business = str(input_data.get("business_or_service", "Chauffeur Service")).strip()
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing SEOKeywordAgent task: action={action}, seed='{seed_keyword}', location='{location}', use_ai={use_ai}")

        # Deterministic Base Keyword Expansion & Clustering
        expanded_keywords: List[Dict[str, Any]] = []
        for sub in SUBURB_MODIFIERS[:5]:
            for srv in SERVICE_MODIFIERS[:3]:
                kw = f"{srv} {sub}"
                intent = "Transactional" if "hire" in srv or "service" in srv else "Commercial"
                expanded_keywords.append({
                    "keyword": kw,
                    "location": sub,
                    "intent": intent,
                    "cluster": srv.replace(" ", "_").title(),
                    "priority": "HIGH" if sub in ["Melbourne CBD", "Tullamarine Airport"] else "MEDIUM"
                })

        primary_keyword = f"{seed_keyword} {location}".strip()
        clusters = {
            "Airport Transfers": [f"airport transfer {sub}" for sub in ["Tullamarine", "Avalon", "Melbourne CBD"]],
            "Corporate Travel": [f"corporate chauffeur {sub}" for sub in ["Melbourne CBD", "South Yarra", "Docklands"]],
            "Event & Wedding": [f"wedding car hire {sub}" for sub in ["Toorak", "St Kilda", "Yarra Valley"]]
        }

        result_payload = {
            "action": action,
            "business_or_service": business,
            "seed_keyword": seed_keyword,
            "target_location": location,
            "primary_keyword": primary_keyword,
            "search_intent": "Transactional / Commercial",
            "recommended_content_type": "Suburb Landing Page / Service Pillar Post",
            "keyword_clusters": clusters,
            "expanded_opportunities_count": len(expanded_keywords),
            "top_keyword_variations": expanded_keywords[:10],
            "actionable_recommendations": [
                f"Target '{primary_keyword}' as the primary H1 title for core landing page.",
                "Create dedicated suburb-level landing pages for Tullamarine Airport and Melbourne CBD.",
                "Include 'luxury private driver' in meta descriptions to capture transactional intent."
            ]
        }

        # Optional LLM Enhancement via ModelRouter
        tokens_used = 0
        cost_usd = 0.0
        model_used = "rule-based-seo-engine"

        if use_ai:
            prompt = (
                f"Perform keyword research for business: '{business}', location: '{location}', seed: '{seed_keyword}'. "
                "Provide primary keyword, 5 secondary keywords, 3 long-tail keywords, search intent, and priority."
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
                logger.warning(f"AI enrichment failed (fallback to rule engine): {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
