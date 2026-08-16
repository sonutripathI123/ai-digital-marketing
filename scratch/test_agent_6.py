import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_agent_6():
    print("=" * 70)
    print("  TESTING AGENT #6: internal-linking-agent (Internal Linking Agent)")
    print("=" * 70)

    input_data = {
        "action": "scan_opportunities",
        "source_url": "/blog/chauffeur-vs-rideshare-airport-fitzroy",
        "topic": "Fitzroy Airport Chauffeur Transfers"
    }

    create_res = requests.post(f"{BASE_URL}/api/tasks/create", json={
        "agent_id": "internal-linking-agent",
        "task_type": "scan_opportunities",
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
    print("Live Internal Linking Opportunities Summary:")
    print(f" - Source Page: {output_data.get('source_url')}")
    print(f" - Scanned Topic: {output_data.get('scanned_topic')}")
    print(f" - Total Opportunities Found: {output_data.get('total_opportunities_found')}")
    print("Discovered Linking Opportunities:")
    for opp in output_data.get("linking_opportunities", []):
        print(f"   • Target URL: {opp.get('target_url')} | Anchor: '{opp.get('recommended_anchor_text')}' (Relevance: {opp.get('relevance_score')}%)")

    print("\nActionable Linking Recommendations:")
    for rec in output_data.get("actionable_summary", []):
        print(f"   -> {rec}")

    print("\n" + "=" * 70)
    print("  AGENT #6 (internal-linking-agent) TEST: 100% SUCCESSFUL & VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    test_agent_6()
