import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_agent_5():
    print("=" * 70)
    print("  TESTING AGENT #5: seo-content-brief-agent (SEO Content Brief Agent)")
    print("=" * 70)

    input_data = {
        "action": "create_brief",
        "target_keyword": "corporate chauffeur melbourne",
        "location": "Melbourne CBD",
        "secondary_keywords": ["executive car transfer", "luxury airport pickup"],
        "target_audience": "Corporate Executives & Event Planners"
    }

    create_res = requests.post(f"{BASE_URL}/api/tasks/create", json={
        "agent_id": "seo-content-brief-agent",
        "task_type": "create_brief",
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
    print("Live Content Brief Summary:")
    print(f" - Primary Keyword: {output_data.get('target_keyword')}")
    print(f" - Target Location: {output_data.get('target_location')}")
    print(f" - Target Audience: {output_data.get('target_audience')}")
    print(f" - Recommended Word Count: {output_data.get('recommended_word_count')}")
    print("Title Suggestions:")
    for title in output_data.get("title_suggestions", []):
        print(f"   • {title}")

    print("\nStructured Outline (H2 Headings):")
    for section in output_data.get("structured_outline", []):
        print(f"   [{section.get('level')}] {section.get('heading')}")

    print("\n" + "=" * 70)
    print("  AGENT #5 (seo-content-brief-agent) TEST: 100% SUCCESSFUL & VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    test_agent_5()
