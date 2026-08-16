import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def run_agent_test(agent_id, task_type, input_data):
    print(f"\n--- Creating Task for {agent_id} ({task_type}) ---")
    c_res = requests.post(f"{BASE_URL}/api/tasks/create", json={
        "agent_id": agent_id,
        "task_type": task_type,
        "input_data": input_data,
        "requires_approval": False,
        "priority": "NORMAL"
    })
    task_id = c_res.json()["task"]["task_id"]
    print(f"Created Task ID: {task_id}")

    exec_res = requests.post(f"{BASE_URL}/api/tasks/execute/{task_id}")
    task_data = exec_res.json()["task"]
    print(f"Status: {task_data['status']}")
    print("Output Data:")
    print(json.dumps(task_data.get("output_data"), indent=2))
    return task_id

if __name__ == '__main__':
    # Test Agent #1
    run_agent_test("blog-agent", "status", {"site": "ccm"})
    # Test Agent #2
    run_agent_test("corporate-cars-social-agent", "status", {})
