import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def create_and_run(agent_id, task_type, input_data):
    r = requests.post(f"{BASE_URL}/api/tasks/create", json={
        "agent_id": agent_id,
        "task_type": task_type,
        "input_data": input_data,
        "requires_approval": False,
        "priority": "NORMAL"
    })
    task_id = r.json()["task"]["task_id"]
    requests.post(f"{BASE_URL}/api/tasks/execute/{task_id}")
    print(f"Recorded & executed task for {agent_id}: {task_id}")

if __name__ == '__main__':
    create_and_run("blog-agent", "status", {"site": "ccm"})
    create_and_run("corporate-cars-social-agent", "status", {})
    create_and_run("seo-keyword-agent", "research", {"seed": "corporate chauffeur melbourne", "location": "Melbourne CBD"})
