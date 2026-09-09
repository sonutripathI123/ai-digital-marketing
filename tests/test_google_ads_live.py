"""Self-test for the Google Ads live integration (no real API calls)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.ads.google_ads_client import GoogleAdsLiveClient, resolve_credentials
from agents.google_ads_monitoring_agent import GoogleAdsMonitoringAgent, _build_live_payload
from agents.google_ads_optimization_agent import GoogleAdsOptimizationAgent, _build_live_optimization
from core.models.task import AgentTask

ok = True
def check(name, cond):
    global ok
    print(("  PASS " if cond else "  FAIL ") + name)
    ok = ok and cond

print("1) Client status with NO credentials")
c = GoogleAdsLiveClient(credentials={})
st = c.status()
check("is_configured() is False", c.is_configured() is False)
check("status has reason", bool(st.get("reason")))
check("missing_credentials lists all 5", len(st["missing_credentials"]) == 5)
print("   ->", st["code"], "|", st["reason"])

print("2) Client status with partial credentials (only customer_id)")
c2 = GoogleAdsLiveClient(credentials={"customer_id": "194-940-8641"})
check("customer_id digits stripped", c2.customer_id == "1949408641")
check("still not configured", c2.is_configured() is False)
check("developer_token in missing", "developer_token" in c2.status()["missing_credentials"])

print("3) Monitoring agent falls back to DEMO (labelled) when not live")
mon = GoogleAdsMonitoringAgent()
res = mon.run_task(AgentTask(task_id="t", agent_id="google-ads-monitoring-agent",
                             task_type="monitor_performance",
                             input_data={"action": "monitor_performance", "account_id": "1949408641"}),
                   router=None)
out = res["output"]
check("data_source is DEMO", "DEMO" in out.get("data_source", ""))
check("notice present", "notice" in out)
check("live_status present", "live_status" in out)

print("4) Optimization agent falls back to DEMO (labelled) when not live")
opt = GoogleAdsOptimizationAgent()
res2 = opt.run_task(AgentTask(task_id="t2", agent_id="google-ads-optimization-agent",
                              task_type="recommend_optimizations",
                              input_data={"action": "recommend_optimizations", "account_id": "1949408641"}),
                    router=None)
out2 = res2["output"]
check("data_source is DEMO", "DEMO" in out2.get("data_source", ""))
check("notice present", "notice" in out2)

print("5) Live payload builders shape mock live data correctly")
mock_perf = {
    "summary": {"total_spend": 500.0, "total_clicks": 200, "total_impressions": 2000,
                "total_conversions": 5, "avg_ctr_percent": 10.0, "avg_cpc": 2.5,
                "avg_cpa": 100.0, "overall_roas": 4.0, "currency": "AUD"},
    "campaigns": [
        {"campaign_id": "1", "campaign_name": "Chauffeur", "status": "ENABLED", "channel": "SEARCH",
         "daily_budget": 55, "spend": 400, "impressions": 1800, "clicks": 180, "ctr_percent": 10,
         "avg_cpc": 2.2, "conversions": 5, "cpa": 80, "roas": 4.5},
        {"campaign_id": "2", "campaign_name": "Airport", "status": "ENABLED", "channel": "SEARCH",
         "daily_budget": 55, "spend": 100, "impressions": 200, "clicks": 20, "ctr_percent": 10,
         "avg_cpc": 5, "conversions": 0, "cpa": 0, "roas": 0},
    ],
    "date_range": "LAST_30_DAYS",
}
lp = _build_live_payload("monitor_performance", "1949408641", mock_perf, {"code": "LIVE"})
check("live data_source", lp["data_source"] == "LIVE (Google Ads API)")
check("winner recommendation present", any("Top converter" in r for r in lp["actionable_recommendations"]))
check("leak recommendation present", any("leak" in r.lower() for r in lp["actionable_recommendations"]))

mock_opt = {
    "keywords": [
        {"keyword": "vip chauffeur hire", "match_type": "PHRASE", "quality_score": 8, "campaign": "C",
         "ad_group": "A", "impressions": 500, "clicks": 106, "spend": 250, "ctr_percent": 21,
         "avg_cpc": 2.3, "conversions": 2, "cpa": 120},
        {"keyword": "cheap taxi", "match_type": "BROAD", "quality_score": 3, "campaign": "C",
         "ad_group": "A", "impressions": 400, "clicks": 40, "spend": 60, "ctr_percent": 10,
         "avg_cpc": 1.5, "conversions": 0, "cpa": 0},
    ],
    "search_terms": [
        {"search_term": "executive chauffeur melbourne", "campaign": "C", "impressions": 100,
         "clicks": 12, "spend": 30, "ctr_percent": 12, "conversions": 1, "cpa": 30},
        {"search_term": "bus timetable", "campaign": "C", "impressions": 200, "clicks": 15,
         "spend": 25, "ctr_percent": 7.5, "conversions": 0, "cpa": 0},
    ],
}
lo = _build_live_optimization("recommend_optimizations", "1949408641", "reduce_cpa", mock_opt, {"code": "LIVE"})
check("winners include converting keyword", lo["winning_keywords"][0]["keyword"] == "vip chauffeur hire")
check("wasteful includes zero-conv keyword", any(k["keyword"] == "cheap taxi" for k in lo["wasteful_keywords"]))
check("new keyword idea from search term", any(k["keyword"] == "executive chauffeur melbourne"
                                               for k in lo["recommended_new_keywords"]))
check("negative includes wasteful search term", "bus timetable" in lo["recommended_negative_keywords"])

print("\nRESULT:", "ALL PASS ✅" if ok else "SOME FAILED ❌")
sys.exit(0 if ok else 1)
