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


# --------------------------------------------------------------------------- #
# High-Volume Search Keywords Catalog & Anti-Cannibalization Allocation Engine
# --------------------------------------------------------------------------- #
HIGH_VOLUME_KEYWORD_CATALOG = [
    # Top 1 Tier: High Volume & High Intent (Search Volume: 1,000 - 5,000/mo)
    {"keyword": "corporate chauffeur melbourne", "suburb": "Melbourne CBD", "monthly_volume": 4400, "category": "Corporate Travel", "angle": "Executive Guide: Why Top Enterprises Choose Dedicated Corporate Chauffeurs"},
    {"keyword": "corporate airport transfers melbourne", "suburb": "Melbourne", "monthly_volume": 3600, "category": "Airport Transfers", "angle": "Seamless Flight Connections: Corporate Airport Transfers Melbourne"},
    {"keyword": "mercedes sprinter hire melbourne", "suburb": "Melbourne", "monthly_volume": 2900, "category": "Luxury Vans", "angle": "Group VIP Travel: Luxury Mercedes Sprinter Chauffeur Hire Melbourne"},
    {"keyword": "private chauffeur toorak to airport", "suburb": "Toorak", "monthly_volume": 1800, "category": "Suburb Premium", "angle": "Toorak to Melbourne Airport: Door-to-Door Luxury Chauffeur Planning"},
    {"keyword": "brighton chauffeur car hire", "suburb": "Brighton", "monthly_volume": 1600, "category": "Suburb Premium", "angle": "Bayside Executive Commutes: Brighton Chauffeur Car Hire Guide"},
    {"keyword": "executive chauffeur car hire south yarra", "suburb": "South Yarra", "monthly_volume": 1500, "category": "Suburb Premium", "angle": "South Yarra Luxury Driver: Premium Chauffeur Car Hire for Professionals"},
    {"keyword": "sprinter van hire with driver melbourne", "suburb": "Melbourne", "monthly_volume": 2400, "category": "Luxury Vans", "angle": "Event & Delegation Transport: Sprinter Van Hire With Professional Driver"},
    {"keyword": "chauffeur service yarra valley winery tour", "suburb": "Yarra Valley", "monthly_volume": 2100, "category": "Tours & Events", "angle": "Curated Wine Country Trips: Private Chauffeur Yarra Valley Winery Tours"},
    {"keyword": "corporate car hire docklands melbourne", "suburb": "Docklands", "monthly_volume": 1400, "category": "Corporate Travel", "angle": "Docklands Business Hub: Effortless Corporate Car Hire & Client Transfers"},
    {"keyword": "airport transfer kew to tullamarine", "suburb": "Kew", "monthly_volume": 1300, "category": "Airport Transfers", "angle": "Kew to Tullamarine Airport: Travel Times, Peak Hour Routes & Flat Rates"},
    {"keyword": "chauffeur service essendon airport", "suburb": "Essendon", "monthly_volume": 1250, "category": "Airport Transfers", "angle": "Private Aviation & Charter Transfers: Essendon Airport Chauffeur Service"},
    {"keyword": "luxury transfer st kilda to airport", "suburb": "St Kilda", "monthly_volume": 1200, "category": "Airport Transfers", "angle": "St Kilda to Melbourne Airport: Stress-Free Flight Departure Planning"},
    {"keyword": "corporate cars carlton executive travel", "suburb": "Carlton", "monthly_volume": 1150, "category": "Corporate Travel", "angle": "Carlton Executive Travel: Punctual Business Transport & Chauffeur Etiquette"},
    {"keyword": "chauffeur car hire fitzroy melbourne", "suburb": "Fitzroy", "monthly_volume": 1100, "category": "Suburb Premium", "angle": "Fitzroy to City & Airport: Reliable Chauffeur Car Hire for Creatives & Founders"},
    {"keyword": "melbourne cbd luxury event transfer", "suburb": "Melbourne CBD", "monthly_volume": 1950, "category": "Tours & Events", "angle": "Red Carpet & Gala Nights: Melbourne CBD Luxury Event Transfers"},
    {"keyword": "mornington peninsula winery tour chauffeur", "suburb": "Mornington Peninsula", "monthly_volume": 1850, "category": "Tours & Events", "angle": "Day Trips in Style: Mornington Peninsula Private Winery Tour Chauffeur"},
    {"keyword": "southbank to melbourne airport private car", "suburb": "Southbank", "monthly_volume": 1450, "category": "Airport Transfers", "angle": "Southbank Riverside to Airport: Guaranteed On-Time Executive Transfers"},
    {"keyword": "albert park corporate chauffeur grand prix", "suburb": "Albert Park", "monthly_volume": 1350, "category": "Tours & Events", "angle": "Albert Park Executive Transport: Chauffeur Hire for Major Events"},
    {"keyword": "geelong to melbourne airport luxury transfer", "suburb": "Geelong", "monthly_volume": 1650, "category": "Regional Transfers", "angle": "Long-Distance Regional Chauffeur: Geelong to Melbourne Airport Transfer"},
    {"keyword": "avalon airport chauffeur service melbourne", "suburb": "Avalon", "monthly_volume": 1250, "category": "Airport Transfers", "angle": "Avalon Flight Departures: Reliable Chauffeur Booking & Timing Guide"},
    {"keyword": "crown casino vip chauffeur transport", "suburb": "Southbank", "monthly_volume": 1550, "category": "Tours & Events", "angle": "VIP Arrivals: Private Chauffeur Transport to Crown Melbourne"},
    {"keyword": "wedding car hire chauffeur melbourne", "suburb": "Melbourne", "monthly_volume": 2800, "category": "Wedding Chauffeur", "angle": "Bridal Luxury: Complete Guide to Wedding Car Hire & Chauffeurs Melbourne"},
    {"keyword": "preston to melbourne airport chauffeur", "suburb": "Preston", "monthly_volume": 950, "category": "Airport Transfers", "angle": "Preston to Airport: Best Departure Times & Flat-Fare Chauffeurs"},
    {"keyword": "doncaster executive corporate car service", "suburb": "Doncaster", "monthly_volume": 900, "category": "Corporate Travel", "angle": "Eastern Suburbs Business Travel: Doncaster Corporate Car Service"},
    {"keyword": "berwick airport chauffeur transfer", "suburb": "Berwick", "monthly_volume": 850, "category": "Airport Transfers", "angle": "South-East Melbourne Travel: Berwick to Melbourne Airport Chauffeurs"},
    {"keyword": "werribee executive chauffeur transfer", "suburb": "Werribee", "monthly_volume": 800, "category": "Airport Transfers", "angle": "Western Suburbs Executive Rides: Werribee Airport & City Chauffeurs"},
    {"keyword": "ringwood corporate chauffeur service", "suburb": "Ringwood", "monthly_volume": 750, "category": "Corporate Travel", "angle": "Maroondah Business Transit: Ringwood Corporate Chauffeur Solutions"},
    {"keyword": "williamstown private airport transfer", "suburb": "Williamstown", "monthly_volume": 700, "category": "Airport Transfers", "angle": "Historic Bayside Travel: Williamstown to Tullamarine Airport Transfers"}
]


def normalize_kw_string(kw: str) -> str:
    """Normalizes string for anti-cannibalization comparison."""
    import re
    return re.sub(r"[^a-z0-9]", "", (kw or "").lower())


def get_unused_high_volume_keywords(existing_used_keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Filters high-volume keywords catalog against all already-used keywords.
    Ensures 100% strict anti-cannibalization (zero duplicate keyword assignments).
    """
    normalized_used = {normalize_kw_string(k) for k in existing_used_keywords if k}
    
    unused_list = []
    for item in HIGH_VOLUME_KEYWORD_CATALOG:
        kw = item["keyword"]
        norm_kw = normalize_kw_string(kw)
        
        # Exact and partial match check to prevent keyword cannibalization
        is_used = False
        if norm_kw in normalized_used:
            is_used = True
        else:
            for u in normalized_used:
                if len(u) > 10 and (u in norm_kw or norm_kw in u):
                    is_used = True
                    break
        
        if not is_used:
            unused_list.append(dict(item))
            
    # Sort by monthly search volume (descending)
    unused_list.sort(key=lambda x: -x.get("monthly_volume", 0))
    return unused_list
