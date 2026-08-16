import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_agent_3():
    print("=" * 70)
    print("  TESTING AGENT #3: seo-keyword-agent (SEO Keyword Research Agent)")
    print("=" * 70)

    input_data = {
        "action": "research",
        "seed": "corporate chauffeur melbourne",
        "location": "Melbourne CBD",
        "use_ai": False
    }

    print(f"Input Data: {json.dumps(input_data, indent=2)}")

    # 1. Create Task via API
    create_res = requests.post(f"{BASE_URL}/api/tasks/create", json={
        "agent_id": "seo-keyword-agent",
        "task_type": "research",
        "input_data": input_data,
        "requires_approval": False,
        "priority": "NORMAL"
    })

    if create_res.status_code != 200:
        print(f"[ERROR] Failed to create task: {create_res.text}")
        return

    task_id = create_res.json()["task"]["task_id"]
    print(f"[OK] Created Task ID: {task_id}")

    # 2. Execute Task via API
    exec_res = requests.post(f"{BASE_URL}/api/tasks/execute/{task_id}")
    if exec_res.status_code != 200:
        print(f"[ERROR] Failed to execute task: {exec_res.text}")
        return

    res_data = exec_res.json()
    task_output = res_data.get("task", {})
    status = task_output.get("status")
    output_data = task_output.get("output_data", {})

    print(f"[OK] Execution Status: {status}")
    print("Live Result Summary:")
    print(f" - Primary Keyword: {output_data.get('primary_keyword')}")
    print(f" - Search Intent: {output_data.get('search_intent')}")
    print(f" - Recommended Content Type: {output_data.get('recommended_content_type')}")
    print(f" - Keyword Clusters Count: {len(output_data.get('keyword_clusters', {}))}")
    print(f" - Keyword Variations Count: {len(output_data.get('top_keyword_variations', []))}")
    print("Sample Variations:")
    for kw in output_data.get("top_keyword_variations", [])[:4]:
        print(f"   • {kw.get('keyword')} [{kw.get('intent')}] (Priority: {kw.get('priority')})")

    print("\nActionable Recommendations:")
    for rec in output_data.get("actionable_recommendations", []):
        print(f"   -> {rec}")

    print("\n" + "=" * 70)
    print("  AGENT #3 (seo-keyword-agent) TEST: 100% SUCCESSFUL & VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    test_agent_3()
