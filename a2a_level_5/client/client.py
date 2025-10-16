import asyncio
import json
import traceback
from uuid import uuid4
from typing import Any

import click
import httpx
from rich import print as rprint
from rich.syntax import Syntax

from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    SendMessageRequest,
    SendStreamingMessageRequest,
    MessageSendParams,
    SendMessageSuccessResponse,
    Task,
    TaskState,
    GetTaskRequest,
    TaskQueryParams,
)

def build_message_payload(text: str, task_id: str | None = None, context_id: str | None = None) -> dict[str, Any]:
    return {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
            "messageId": uuid4().hex,
            **({"taskId": task_id} if task_id else {}),
            **({"contextId": context_id} if context_id else {}),
        }
    }

def print_json_response(response: Any, title: str) -> None:
    print(f"\n=== {title} ===")
    try:
        if hasattr(response, "root"):
            data = response.root.model_dump(mode="json", exclude_none=True)
        else:
            data = response.model_dump(mode="json", exclude_none=True)
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        rprint(syntax)
    except Exception as e:
        rprint(f"Error printing JSON: {e}")
        rprint(repr(response))

async def handle_non_streaming(client: A2AClient, text: str):
    request = SendMessageRequest(params=MessageSendParams(**build_message_payload(text)))
    result = await client.send_message(request)
    print_json_response(result, "Agent Reply")
    if isinstance(result.root, SendMessageSuccessResponse):
        task = result.root.result
        if task.status.state == TaskState.input_required:
            follow_up = input("Agent needs more input. Your reply: ")
            follow_up_req = SendMessageRequest(
                params=MessageSendParams(**build_message_payload(follow_up, task.id, task.contextId))
            )
            follow_up_resp = await client.send_message(follow_up_req)
            print_json_response(follow_up_resp, "Follow-up Response")

async def handle_streaming(client: A2AClient, text: str, task_id: str | None = None, context_id: str | None = None):
    request = SendStreamingMessageRequest(params=MessageSendParams(**build_message_payload(text, task_id, context_id)))
    latest_task_id = None
    latest_context_id = None
    input_required = False
    async for update in client.send_message_streaming(request):
        print_json_response(update, "Streaming Update")
        if hasattr(update.root, "result"):
            result = update.root.result
            if hasattr(result, "contextId"):
                latest_context_id = result.contextId
            if hasattr(result, "status") and result.status.state == TaskState.input_required:
                latest_task_id = result.taskId
                input_required = True
    if input_required and latest_task_id and latest_context_id:
        follow_up = input("Agent needs more input. Your reply: ")
        await handle_streaming(client, follow_up, latest_task_id, latest_context_id)

async def interactive_loop(client: A2AClient, supports_streaming: bool):
    print("\nEnter your query below. Type 'exit' to quit.")
    while True:
        query = input("\nYour query: ").strip()
        if query.lower() in {"exit", "quit"}:
            print("Exiting...")
            break
        if supports_streaming:
            await handle_streaming(client, query)
        else:
            await handle_non_streaming(client, query)

@click.command()
@click.option("--agent-url", default="http://localhost:10000", help="URL of the A2A agent to connect to")
def main(agent_url: str):
    asyncio.run(run_main(agent_url))

async def run_main(agent_url: str):
    print(f"Connecting to agent at {agent_url}...")
    try:
        async with httpx.AsyncClient() as session:
            client = await A2AClient.get_client_from_agent_card_url(session, agent_url)
            client.httpx_client.timeout = 60
            res = await session.get(f"{agent_url}/.well-known/agent.json")
            agent_card = AgentCard.model_validate(res.json())
            supports_streaming = agent_card.capabilities.streaming
            rprint(f"Connected. Streaming supported: {supports_streaming}")
            await interactive_loop(client, supports_streaming)
    except Exception:
        traceback.print_exc()
        print("Failed to connect or run. Ensure the agent is live and reachable.")

if __name__ == "__main__":
    main()