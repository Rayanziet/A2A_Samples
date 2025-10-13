from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__) #creates a new flask app

@app.route("/.well_known/agent.json", methods=["GET"])
def agent_card():
    return jsonify({
        "name": "TellTimeAgent",
        "description": "An agent that tells the current time.",
        "url": "http://localhost:5000",
        "version": "1.0",
        "capabilities": {
            "pushNotifications": False,
            "streaming": False,
        }
    })

#defining the endpoint that the agents will use to send tasks to this agent
@app.route("/tasks/send", methods=["POST"])
def handle_task():
    try:
        task = request.get_json()
        task_id = task.get("id")
        user_message = task["message"]["parts"][0]["text"]

    except (KeyError, TypeError, IndexError):
        return jsonify({"error": "Invalid task format"}), 400
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response_message = f"The current time is: {current_time}"
    return jsonify({
        "task_id": task_id,
        "status": {"state": "completed"},
        "messages": [
            task["message"],
            {
                "role": "agent",
                "parts": [{"text": response_message}]
            }
        ]
    })

if __name__ == "__main__":
    app.run(port=5000)