import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_single_agent(agent_id, task_type, input_data, description):
    print("=" * 70)
    print(f"  TESTING AGENT: {agent_id} ({description})")
    print("=" * 70)
    print(f"Task Type: {task_type}")
    print(f"Input Data: {json.dumps(input_data)}")

    # 1. Create Task via API
    create_res = requests.post(f"{BASE_URL}/api/tasks/create", json={
        "agent_id": agent_id,
        "task_type": task_type,
        "input_data": input_data,
        "requires_approval": False,
        "priority": "NORMAL"
    })
    
    if create_res.status_code != 200:
        print(f"[ERROR] FAILED to create task. Status Code: {create_res.status_code}")
        print(create_res.text)
        return False

    task_id = create_res.json()["task"]["task_id"]
    print(f"[OK] Created Task ID: {task_id}")

    # 2. Execute Task via API
    exec_res = requests.post(f"{BASE_URL}/api/tasks/execute/{task_id}")
    if exec_res.status_code != 200:
        print(f"[ERROR] FAILED to execute task. Status Code: {exec_res.status_code}")
        print(exec_res.text)
        return False

    res_data = exec_res.json()
    task_output = res_data.get("task", {})
    status = task_output.get("status")
    output_data = task_output.get("output_data")

    print(f"[OK] Execution Status: {status}")
    print("Output Snippet:")
    print(json.dumps(output_data, indent=2))
    print("\n" + "-" * 70 + "\n")
    return status == "COMPLETED"

if __name__ == "__main__":
    # Test Agent #1
    success = test_single_agent(
        agent_id="blog-agent",
        task_type="status",
        input_data={"site": "ccm"},
        description="Blog Writing & Publishing Agent Adapter"
    )
    if success:
        print("[SUCCESS] AGENT #1 (blog-agent) TEST: 100% SUCCESSFUL & VERIFIED!")
    else:
        print("[FAILED] AGENT #1 (blog-agent) TEST FAILED!")
