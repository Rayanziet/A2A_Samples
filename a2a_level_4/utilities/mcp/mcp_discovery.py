import os  
import json 
import logging  
from typing import Dict, Any  

logger = logging.getLogger(__name__)


class MCPDiscovery:
    """
    Reads a JSON config file defining MCP servers and provides access
    to the server definitions under the "mcpServers" key.

    Attributes:
        config_file (str): Path to the JSON configuration file.
        config (Dict[str, Any]): Parsed JSON content, expected to contain "mcpServers".
    """

    def __init__(self, config_file: str = None):
        """
        Initialize the discovery client.

        Args:
            config_file (str, optional): Custom path to the MCP config JSON.
                                         If None, defaults to 'mcp_config.json'
                                         located in the same directory as this module.
        """
        if config_file:
            self.config_file = config_file  
        else:
            self.config_file = os.path.join(
                os.path.dirname(__file__), 
                "mcp_config.json"  
            )

        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Read and parse the JSON config file.

        Returns:
            Dict[str, Any]: The entire JSON object if valid;
                            otherwise, an empty dict on error.
        """
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)  # Parse JSON into Python object

            if not isinstance(data, dict):
                raise ValueError("MCP config must be a JSON object at the top level.")

            return data

        except FileNotFoundError:
            logger.warning(f"MCP config file not found: {self.config_file}")
            return {}

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing MCP config: {e}")
            return {}

    def list_servers(self) -> Dict[str, Any]:
        """
        Retrieve the mapping of server names to their configuration entries.

        The JSON should look like:

        {
            "mcpServers": {
                "server 1 name": { "command": "...", "args": [...] },
                "server 2 name":           { "command": "...", "args": [...] }
            }
        }

        Returns:
            Dict[str, Any]: The dictionary under "mcpServers", or empty dict if missing.
        """
        return self.config.get('mcpServers', {})