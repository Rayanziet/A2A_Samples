import requests

import uuid #for generating unique IDs

base_url = "http://localhost:5000"

res = requests.get(f"{base_url}/.well_known/agent.json")

if res.status_code != 200:
    raise Exception("Failed to fetch agent card")

agent_info = res.json()

print(f"connected to the agent: {agent_info['name']}")

task_id = str(uuid.uuid4()) #generate a unique task ID

task_payload = {
    "id": task_id,
    "message": {
        "role": "user",
        "parts": [{"text": "What time is it?"}]
    }
}

res = requests.post(f"{base_url}/tasks/send", json=task_payload)

if res.status_code != 200:
    raise Exception("failed to send task")

reply = res.json()

if reply:
    time_reply = reply["messages"][-1]["parts"][0]['text']
    print(f"Agents says it's {time_reply}")
else:
    print("failed to get a response from agent")