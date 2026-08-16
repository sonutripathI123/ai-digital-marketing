import json

with open("logs/tasks_history.json", "r", encoding="utf-8") as f:
    tasks = json.load(f)

pending = [t for t in tasks if t.get("status") == "AWAITING_APPROVAL"]
print("Total Pending Tasks:", len(pending))
for idx, item in enumerate(pending, 1):
    print(f"[{idx}] Task ID: {item['task_id']}")
    print(f"    Agent ID: {item['agent_id']}")
    print(f"    Task Type: {item['task_type']}")
    print(f"    Priority: {item['priority']}")
    print(f"    Requires Approval: {item['requires_approval']}")
    print(f"    Input Data: {item['input_data']}")
    print(f"    Created At: {item['created_at']}")
    print("-" * 50)
