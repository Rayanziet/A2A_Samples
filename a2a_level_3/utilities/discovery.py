import os                         
import json                      
import logging                      
from typing import List             

import httpx                      
from models.agent import AgentCard  

logger = logging.getLogger(__name__)


class DiscoveryClient:
    """
    🔍 Discovers A2A agents by reading a registry file of URLs and querying
    each one's /.well-known/agent.json endpoint to retrieve an AgentCard.

    Attributes:
        registry_file (str): Path to the JSON file listing base URLs (strings).
        base_urls (List[str]): Loaded list of agent base URLs.
    """

    def __init__(self, registry_file: str = None):
        if registry_file:
            self.registry_file = registry_file
        else:
            self.registry_file = os.path.join(
                os.path.dirname(__file__), "agent_registry.json"
            )
        self.base_urls = self._load_registry()
    
    def _load_registry(self) -> List[str]:
        try:
            with open(self.registry_file, "r") as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                raise ValueError("Registry file must contain a list of URLs.")
            return data
        except FileNotFoundError:
            logger.error(f"Registry file not found: {self.registry_file}")
            return []
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing registry file: {e}")
            return []
        
    async def list_agent_card(self) -> List[AgentCard]:
        """
        Queries each base URL's /.well-known/agent.json endpoint to retrieve
        AgentCards.

        Returns:
            List[AgentCard]: List of successfully retrieved AgentCards.
        """
        agent_card = []
        async with httpx.AsyncClient() as client:
            for base_url in self.base_urls:
                url = base_url.rstrip("/") + "/.well-known/agent.json"
                try:
                    response = await client.get(url, timeout=5.0)
                    response.raise_for_status()
                    data = response.json()
                    agent = AgentCard(**data)
                    agent_card.append(agent)
                except Exception as e:
                    logger.warning(f"Failed to discover agent at {url}: {e}")
        return agent_card
