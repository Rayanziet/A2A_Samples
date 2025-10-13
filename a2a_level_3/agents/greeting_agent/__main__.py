
# Starts the GreetingAgent as an Agent-to-Agent (A2A) server.
# - Defines the agent’s metadata (AgentCard)
# - Wraps the GreetingAgent logic in a GreetingTaskManager
# - Listens for incoming tasks on a configurable host and port
# =============================================================================

import logging                       
import click                     
from server.server import A2AServer    
from models.agent import (
    AgentCard,                        
    AgentCapabilities,
    AgentSkill
)
from agents.greeting_agent.task_manager import GreetingTaskManager
from agents.greeting_agent.agent import GreetingAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



@click.command()                     # Decorator: makes `main` a CLI command
@click.option(
    "--host",                        # CLI flag name
    default="localhost",             # Default value if flag not provided
    help="Host to bind GreetingAgent server to"  # Help text for `--help`
)
@click.option(
    "--port",
    default=10001,
    help="Port for GreetingAgent server"
)
def main(host: str, port: int):
    """
    Launches the GreetingAgent A2A server.

    Args:
        host (str): Hostname or IP to bind to (default: localhost)
        port (int): TCP port to listen on (default: 10001)
    """
    print(f"\n🚀 Starting GreetingAgent on http://{host}:{port}/\n")


    capabilities = AgentCapabilities(streaming=False)

    skill = AgentSkill(
        id="greet",                                        # Unique skill ID
        name="Greeting Tool",                              # Friendly name
        description="Returns a greeting based on the current time of day",
        tags=["greeting", "time", "hello"],                # Searchable tags
        examples=["Greet me", "Say hello based on time"]   # Example prompts
    )

    agent_card = AgentCard(
        name="GreetingAgent",                              # Agent identifier
        description="Agent that greets you based on the current time",
        url=f"http://{host}:{port}/",                      # Base URL for discovery
        version="1.0.0",                                   # Semantic version
        defaultInputModes=["text"],                        # Accepts plain text
        defaultOutputModes=["text"],                       # Produces plain text
        capabilities=capabilities,                         # Streaming disabled
        skills=[skill]                                     # List of skills
    )

    greeting_agent = GreetingAgent()
    # GreetingTaskManager adapts that logic to the A2A JSON-RPC protocol.
    task_manager = GreetingTaskManager(agent=greeting_agent)


    server = A2AServer(
        host=host,
        port=port,
        agent_card=agent_card,
        task_manager=task_manager
    )
    server.start()  


if __name__ == "__main__":
    main()