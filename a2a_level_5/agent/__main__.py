import os
import sys

import click
import httpx
from dotenv import load_dotenv

from .agent import TellTimeAgent
from .agent_executor import TellTimeAgentExecutor

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotifier, InMemoryTaskStore
from a2a.types import AgentCard, AgentSkill, AgentCapabilities

load_dotenv()

@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10000)
def main(host: str, port: int):
    if not os.getenv('GOOGLE_API_KEY'):
        print("GOOGLE_API_KEY environment variable not set.")
        sys.exit(1)

    client = httpx.AsyncClient()

    handler = DefaultRequestHandler(
        agent_executor=TellTimeAgentExecutor(),
        task_store=InMemoryTaskStore(),
        push_notifier=InMemoryPushNotifier(client),
    )

    server = A2AStarletteApplication(
        agent_card=build_agent_card(host, port),
        http_handler=handler,
    )

    import uvicorn
    uvicorn.run(server.build(), host=host, port=port)

def build_agent_card(host: str, port: int) -> AgentCard:
    return AgentCard(
        name="TellTime Agent",
        description="Tells the current system time.",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, pushNotifications=True),
        defaultInputModes=TellTimeAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=TellTimeAgent.SUPPORTED_CONTENT_TYPES,
        skills=[
            AgentSkill(
                id="tell_time",
                name="Get Current Time",
                description="Tells the current system time in HH:MM:SS format.",
                tags=["time", "clock"],
                examples=["What time is it?", "Tell me the current time."],
            )
        ],
    )

if __name__ == '__main__':
    main()