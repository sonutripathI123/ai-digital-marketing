"""
Agent #5: Internal Linking Agent (`internal-linking-agent`).

Scans website pages and blog drafts to discover contextual internal linking opportunities,
recommend optimal anchor text, and calculate relevance scores for SEO site structure.
"""

from typing import Any, Dict, List
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

from pathlib import Path
import csv
from config.settings import ROOT_DIR

logger = get_agent_logger("internal-linking-agent")

def load_real_indexed_pages():
    csv_file = Path(ROOT_DIR) / "blog-agent" / "all_pages_ccm.csv"
    pages = []
    if csv_file.exists():
        try:
            with open(csv_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    pages.append({
                        "url": r.get("url", ""),
                        "keyword": r.get("page_keyword", ""),
                        "suburb": r.get("suburb_guess", ""),
                        "category": r.get("category", "")
                    })
        except Exception:
            pass
    return pages


class InternalLinkingAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="internal-linking-agent",
            name="Internal Linking Agent",
            description="Finds internal linking opportunities, recommends anchor text, and audits link structure.",
            category="SEO & Content",
            enabled=True,
            paused=False,
            supported_actions=["scan_opportunities", "recommend_anchors", "audit_links"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "scan_opportunities")).lower().strip()
        source_url = str(input_data.get("source_url", "https://corporatecarsmelbourne.com.au/chauffeur-vs-rideshare-airport-fitzroy/")).strip()
        topic = str(input_data.get("topic", "Corporate Chauffeur Services")).strip()
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing InternalLinkingAgent task: action={action}, source_url='{source_url}', topic='{topic}'")

        indexed_pages = load_real_indexed_pages()
        total_indexed = len(indexed_pages)

        # Match relevant pages from the 315 indexed pages
        opportunities: List[Dict[str, Any]] = []
        for p in indexed_pages:
            if p["url"] and p["url"] != source_url:
                kw = p["keyword"] or p["suburb"] or "chauffeur service"
                if any(k in kw.lower() for k in ["airport", "corporate", "chauffeur", "transfer", "luxury"]):
                    opportunities.append({
                        "source_url": source_url,
                        "target_url": p["url"],
                        "recommended_anchor_text": kw.title(),
                        "target_suburb": p["suburb"].title() if p["suburb"] else "Melbourne",
                        "category": p["category"],
                        "relevance_score": 95 if "airport" in kw.lower() or "corporate" in kw.lower() else 82,
                        "reasoning": f"Links '{topic}' directly to indexed page targeting '{kw}'."
                    })
                    if len(opportunities) >= 6:
                        break

        result_payload = {
            "action": action,
            "source_url": source_url,
            "scanned_topic": topic,
            "total_indexed_pages_in_database": total_indexed,
            "mode": "Live Index Scan & Link Mapping",
            "total_opportunities_found": len(opportunities),
            "linking_opportunities": opportunities,
            "actionable_summary": [
                f"Scanned {total_indexed} indexed pages on corporatecarsmelbourne.com.au.",
                f"Add internal link from '{source_url}' to '{opportunities[0]['target_url'] if opportunities else '/services/'}' using anchor '{opportunities[0]['recommended_anchor_text'] if opportunities else 'Corporate Chauffeur'}'."
            ]
        }

        # Optional AI Enrichment
        tokens_used = 0
        cost_usd = 0.0
        model_used = "rule-based-linking-engine"

        if use_ai:
            prompt = (
                f"Analyze source page '{source_url}' covering topic '{topic}'. "
                f"Suggest top 3 internal link pairings to site pillars {DEFAULT_SITE_PILLARS} with anchor text."
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
                logger.warning(f"AI internal linking scan failed (fallback to rule engine): {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
