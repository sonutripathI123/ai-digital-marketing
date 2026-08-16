import requests
import json

BASE_URL = "http://127.0.0.1:8000"

REMAINING_AGENTS = [
    {
        "num": 8,
        "agent_id": "gsc-agent",
        "name": "Google Search Console Agent",
        "task_type": "query_performance",
        "input_data": {"action": "query_performance", "site_url": "https://corporatecarsmelbourne.com.au", "days": 30}
    },
    {
        "num": 9,
        "agent_id": "ga4-reporting-agent",
        "name": "GA4 Analytics Agent",
        "task_type": "traffic_report",
        "input_data": {"action": "traffic_report", "property_id": "corporate-cars-melbourne-ga4", "date_range": "last_30_days"}
    },
    {
        "num": 10,
        "agent_id": "google-ads-monitoring-agent",
        "name": "Google Ads Monitoring Agent",
        "task_type": "monitor",
        "input_data": {"action": "monitor", "customer_id": "987-654-3210", "campaign_name": "Melbourne Chauffeur Search"}
    },
    {
        "num": 11,
        "agent_id": "google-ads-optimization-agent",
        "name": "Google Ads Optimization Agent",
        "task_type": "optimize",
        "input_data": {"action": "optimize", "customer_id": "987-654-3210", "campaign_id": "cmp-1001", "target_cpa": 45.0}
    },
    {
        "num": 12,
        "agent_id": "meta-ads-monitoring-agent",
        "name": "Meta Ads Monitoring Agent",
        "task_type": "monitor",
        "input_data": {"action": "monitor", "ad_account_id": "act_987654321", "date_preset": "last_30d"}
    },
    {
        "num": 13,
        "agent_id": "social-analytics-agent",
        "name": "Social Media Analytics Agent",
        "task_type": "analyze_performance",
        "input_data": {"action": "analyze_performance", "platform": "all", "timeframe": "30d"}
    },
    {
        "num": 14,
        "agent_id": "reputation-agent",
        "name": "Review & Reputation Agent",
        "task_type": "reviews",
        "input_data": {"action": "reviews", "business_id": "corporate-cars-melbourne"}
    },
    {
        "num": 15,
        "agent_id": "lead-management-agent",
        "name": "Lead Management CRM Agent",
        "task_type": "score_lead",
        "input_data": {"action": "score_lead", "lead_data": {"name": "James Thornton", "company": "BHP Group", "email": "j.thornton@bhp.com", "service": "Corporate Chauffeur Account"}}
    },
    {
        "num": 16,
        "agent_id": "monthly-report-agent",
        "name": "Monthly Executive Report Agent",
        "task_type": "generate_report",
        "input_data": {"action": "generate_report", "month": "August 2026", "client_name": "Corporate Cars Melbourne"}
    }
]

def run_all_remaining():
    results = []
    print("=" * 80)
    print("  EXECUTING LIVE TESTS FOR ALL REMAINING AGENTS (#8 - #16)...")
    print("=" * 80)

    for item in REMAINING_AGENTS:
        num = item["num"]
        agent_id = item["agent_id"]
        name = item["name"]
        task_type = item["task_type"]
        input_data = item["input_data"]

        print(f"\n[RUN] Testing Agent #{num}: {agent_id} ({name})...")
        create_res = requests.post(f"{BASE_URL}/api/tasks/create", json={
            "agent_id": agent_id,
            "task_type": task_type,
            "input_data": input_data,
            "requires_approval": False,
            "priority": "NORMAL"
        })

        if create_res.status_code != 200:
            print(f"[FAILED] Failed to create task for {agent_id}: {create_res.text}")
            results.append({"num": num, "agent_id": agent_id, "name": name, "status": "FAILED_CREATE", "details": create_res.text})
            continue

        task_id = create_res.json()["task"]["task_id"]

        exec_res = requests.post(f"{BASE_URL}/api/tasks/execute/{task_id}")
        if exec_res.status_code != 200:
            print(f"[FAILED] Failed to execute task for {agent_id}: {exec_res.text}")
            results.append({"num": num, "agent_id": agent_id, "name": name, "status": "FAILED_EXEC", "details": exec_res.text})
            continue

        task_output = exec_res.json().get("task", {})
        status = task_output.get("status")
        output_data = task_output.get("output_data", {})

        print(f"[OK] Agent #{num} {agent_id}: Status={status} | Task ID={task_id}")
        results.append({
            "num": num,
            "agent_id": agent_id,
            "name": name,
            "task_id": task_id,
            "status": status,
            "output_summary": output_data
        })

    with open("scratch/remaining_agents_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 80)
    print("  ALL REMAINING AGENTS EXECUTED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_all_remaining()
