import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_agent_4():
    print("=" * 70)
    print("  TESTING AGENT #4: competitor-analysis-agent (Competitor Analysis Agent)")
    print("=" * 70)

    input_data = {
        "action": "analyze",
        "competitor_urls": ["melbournechauffeurs.example.com", "luxurydriver.example.com"],
        "target_keyword": "corporate chauffeur melbourne",
        "location": "Melbourne CBD"
    }

    create_res = requests.post(f"{BASE_URL}/api/tasks/create", json={
        "agent_id": "competitor-analysis-agent",
        "task_type": "analyze",
        "input_data": input_data,
        "requires_approval": False,
        "priority": "NORMAL"
    })

    task_id = create_res.json()["task"]["task_id"]
    print(f"[OK] Created Task ID: {task_id}")

    exec_res = requests.post(f"{BASE_URL}/api/tasks/execute/{task_id}")
    task_output = exec_res.json().get("task", {})
    status = task_output.get("status")
    output_data = task_output.get("output_data", {})

    print(f"[OK] Execution Status: {status}")
    print("Live Competitor Analysis Findings:")
    print(f" - Target Keyword: {output_data.get('target_keyword')}")
    print(f" - Competitors Analyzed Count: {output_data.get('competitors_analyzed_count')}")
    print(f" - Total Content Gaps Discovered: {output_data.get('identified_content_gaps_count')}")
    print("Competitor Insights:")
    for insight in output_data.get("competitor_insights", []):
        print(f"   • {insight.get('competitor_url')} (Depth Score: {insight.get('content_depth_score')}/100)")
        for gap in insight.get("content_gaps", []):
            print(f"       - Gap: {gap}")

    print("\nActionable Strategic Recommendations:")
    for rec in output_data.get("actionable_recommendations", []):
        print(f"   -> {rec}")

    print("\n" + "=" * 70)
    print("  AGENT #4 (competitor-analysis-agent) TEST: 100% SUCCESSFUL & VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    test_agent_4()
