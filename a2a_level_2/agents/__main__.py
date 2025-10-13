from server.server import A2ASrever
from models.agent import AgentCard, AgentCapabilities, AgentSkill
# from a2a.types import AgentCard, AgentCapabilities, AgentSkill

from task_manager import AgentTaskManager
from adk_agent import TellTimeAgent

import click #for crearing a clear command-line interface
import logging

@click.command()
@click.option("--host", default="localhost", help="Host to bind the server to")
@click.option("--port", default=1002, help="Port number for the server")
def main(host, port):
    """
    This funtions sets up everything needed to start the agent server.
    """
    capabilities = AgentCapabilities(streaming=False)
    skill = AgentSkill(
        id="tell_time",
        name="Tell time tool",
        description="Replies with the current time",
        tags=["time"],
        examples=["What time is it?", "Tell me the current time"]
    )
    agent_card = AgentCard(
        name="TellTimeAgent",
        desciption="This agent replies with the current system time",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes= TellTimeAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes= TellTimeAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill]
    )

    server = A2ASrever(
        host=host,
        port=port,
        agent_card=agent_card,
        task_manager=AgentTaskManager(TellTimeAgent())
    )

    server.start()
