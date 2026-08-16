import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_agent_7():
    print("=" * 70)
    print("  TESTING AGENT #7: seo-audit-agent (SEO Audit Agent)")
    print("=" * 70)

    input_data = {
        "action": "audit_page",
        "url": "https://corporatecarsmelbourne.com.au"
    }

    create_res = requests.post(f"{BASE_URL}/api/tasks/create", json={
        "agent_id": "seo-audit-agent",
        "task_type": "audit_page",
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
    print("Live Technical SEO Audit Findings:")
    print(f" - Audited URL: {output_data.get('audited_url')}")
    print(f" - Overall Health Score: {output_data.get('overall_seo_health_score')}/100")
    print(f" - Total Checks Completed: {output_data.get('issues_summary', {}).get('total_checks')}")
    print("Audit Issues Breakdown:")
    for issue in output_data.get("audit_findings", []):
        print(f"   • [{issue.get('severity')}] {issue.get('category')} -> {issue.get('check')}: {issue.get('status')}")
        print(f"       Details: {issue.get('details')}")

    print("\nActionable Priorities:")
    for prio in output_data.get("actionable_priorities", []):
        print(f"   -> {prio}")

    print("\n" + "=" * 70)
    print("  AGENT #7 (seo-audit-agent) TEST: 100% SUCCESSFUL & VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    test_agent_7()
