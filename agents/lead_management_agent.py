"""
Agent #14: Lead Management Agent (`lead-management-agent`).

Captures, scores, categorizes, and routes marketing leads (corporate chauffeur, airport transfers, events).
Drafts personalized quote responses requiring human approval.
"""

from typing import Any, Dict, List
from agents.base import AgentInterface
from core.ai_layer.base import LLMRequest, TaskComplexity
from core.ai_layer.router import ModelRouter
from core.logging.logger import get_agent_logger
from core.models.task import AgentTask
from core.orchestrator.registry import AgentMetadata

logger = get_agent_logger("lead-management-agent")


class LeadManagementAgent(AgentInterface):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id="lead-management-agent",
            name="Lead Management Agent",
            description="Captures, qualifies, and scores inbound leads, drafting custom quotes requiring approval.",
            category="Sales & CRM",
            enabled=True,
            paused=False,
            supported_actions=["process_lead", "score_lead", "draft_followup", "lead_report"],
            version="1.0.0"
        )

    def run_task(self, task: AgentTask, router: ModelRouter) -> Dict[str, Any]:
        input_data = task.input_data or {}
        action = str(input_data.get("action", "process_lead")).lower().strip()
        lead_id = str(input_data.get("lead_id", "lead-1001")).strip()
        client_name = str(input_data.get("client_name", "Corporate Executive")).strip()
        service_type = str(input_data.get("service_type", "Airport Transfer")).strip()
        estimated_value_usd = float(input_data.get("estimated_value_usd", 250.0))
        use_ai = bool(input_data.get("use_ai", False))

        logger.info(f"Executing LeadManagementAgent task: action={action}, lead_id='{lead_id}', service='{service_type}'")

        # Deterministic Lead Scoring & Management Engine
        score = 85
        tier = "HIGH_PRIORITY_HOT_LEAD"
        if estimated_value_usd > 500:
            score = 95
            tier = "VIP_CORPORATE_ACCOUNT"
        elif estimated_value_usd < 100:
            score = 50
            tier = "STANDARD_INQUIRY"

        sample_leads = [
            {
                "lead_id": "lead-1001",
                "client_name": "James Thornton (BHP Group)",
                "email": "j.thornton@example.com",
                "phone": "+61 412 345 678",
                "service_type": "Corporate Account Booking",
                "route": "Melbourne CBD -> Tullamarine Airport (Weekly Recurring)",
                "estimated_value_usd": 1200.00,
                "lead_score": 95,
                "tier": "VIP_CORPORATE_ACCOUNT",
                "status": "DRAFT_QUOTE_READY"
            },
            {
                "lead_id": "lead-1002",
                "client_name": "Emma Watson",
                "email": "emma.w@example.com",
                "phone": "+61 498 765 432",
                "service_type": "Wedding Chauffeur",
                "route": "Yarra Valley Wineries",
                "estimated_value_usd": 650.00,
                "lead_score": 88,
                "tier": "HIGH_PRIORITY_HOT_LEAD",
                "status": "QUALIFIED"
            }
        ]

        if action == "draft_followup":
            draft_email = (
                f"Subject: Formal Quotation - {service_type} | Corporate Cars Melbourne\n\n"
                f"Dear {client_name},\n\n"
                f"Thank you for contacting Corporate Cars Melbourne regarding your upcoming {service_type}.\n"
                f"We are pleased to offer our executive Mercedes-Benz V-Class / S-Class service tailored to your itinerary.\n\n"
                f"Estimated Investment: ${estimated_value_usd:.2f} AUD (includes toll fees, flight tracking, and complimentary refreshments).\n\n"
                f"Please let us know if you would like us to finalize this reservation.\n\n"
                f"Kind regards,\nCorporate Cars Melbourne Reservations Team"
            )
            result_payload = {
                "action": action,
                "lead_id": lead_id,
                "client_name": client_name,
                "service_type": service_type,
                "lead_score": score,
                "tier": tier,
                "approval_required": True,
                "draft_email": draft_email,
                "recommendation": "Review draft quote email and click Approve to send to client."
            }
        else:
            result_payload = {
                "action": action,
                "processed_lead": {
                    "lead_id": lead_id,
                    "client_name": client_name,
                    "service_type": service_type,
                    "estimated_value_usd": estimated_value_usd,
                    "lead_score": score,
                    "tier": tier
                },
                "pipeline_summary": {
                    "active_leads": len(sample_leads),
                    "total_pipeline_value_usd": sum(l["estimated_value_usd"] for l in sample_leads),
                    "avg_lead_score": 91.5
                },
                "recent_leads": sample_leads,
                "actionable_recommendations": [
                    "1. Send custom corporate quote to James Thornton (BHP Group) - high-value account ($1,200/mo).",
                    "2. Follow up on weekend wedding car inquiry."
                ]
            }

        # Optional AI Enrichment
        tokens_used = 0
        cost_usd = 0.0
        model_used = "rule-based-lead-engine"

        if use_ai:
            prompt = (
                f"Draft a persuasive, executive follow-up email for lead '{client_name}' interested in '{service_type}' estimated ${estimated_value_usd}."
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
                    result_payload["ai_draft"] = response.content
            except Exception as e:
                logger.warning(f"AI lead follow-up drafting failed (fallback to rule engine): {e}")

        return {
            "output": result_payload,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
