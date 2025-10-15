#   Connect to each MCP server defined in mcp_config.json,
#   open ephemeral sessions to list available tools, and
#   provide an easy interface to call those tools on demand.

import os 
import asyncio 
import logging 
from dotenv import load_dotenv 

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from utilities.mcp.mcp_discovery import MCPDiscovery

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MCPTool:
    """
    Wraps a single MCP-exposed tool so we can call it easily.

    Attributes:
        name (str): Identifier for the tool (e.g., "run_command").
        description (str): Human-readable description of the tool.
        input_schema (dict): JSON schema defining the tool's expected arguments.
        _params (StdioServerParameters): Command/args to start the MCP server.
    """
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict,
        server_cmd: str,
        server_args: list[str]
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self._params = StdioServerParameters(
            command=server_cmd,
            args=server_args
        )

    async def run(self, args: dict) -> str:
        """
        Invoke the tool by:
          1. Spawning the MCP server via stdio
          2. Initializing an MCP ClientSession
          3. Calling the named tool with provided arguments
          4. Closing the session automatically on exit

        Returns:
            The `content` from the tool's response, or the raw response if no content.
        """
        async with stdio_client(self._params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as sess:
                await sess.initialize()
                resp = await sess.call_tool(self.name, args)
                return getattr(resp, "content", str(resp))


class MCPConnector:
    """
    Discovers MCP servers from config, lists each server's tools,
    and caches them as MCPTool instances for easy lookup.

    Usage:
        connector = MCPConnector()
        tools = connector.get_tools()
        result = await tools[0].run({"arg1": "value"})
    """
    def __init__(self, config_file: str = None):
        # Initialize MCPDiscovery to load server definitions from JSON
        self.discovery = MCPDiscovery(config_file=config_file)
        # Prepare an empty list to hold MCPTool objects
        self.tools: list[MCPTool] = []
        # Load tools from all configured MCP servers immediately
        self._load_all_tools()

    def _load_all_tools(self):
        """
        Internal helper: runs an async routine synchronously to fetch
        and cache tool definitions from every MCP server.
        """
        async def _fetch():
            servers = self.discovery.list_servers()
            for name, info in servers.items():
                cmd = info.get("command")
                args = info.get("args", [])
                logger.info(f"[MCPConnector] Fetching tools from MCP server: {name}")
                params = StdioServerParameters(command=cmd, args=args)
                try:
                    async with stdio_client(params) as (r, w):
                        # Wrap in a client session to talk MCP
                        async with ClientSession(r, w) as sess:
                            # Initialize the session (handshake)
                            await sess.initialize()
                            # Ask the server for its list of tools
                            tool_list = (await sess.list_tools()).tools
                            # For each declared tool, wrap it in MCPTool
                            for t in tool_list:
                                self.tools.append(
                                    MCPTool(
                                        name=t.name,
                                        description=t.description,
                                        input_schema=t.inputSchema,
                                        server_cmd=cmd,
                                        server_args=args
                                    )
                                )
                            logger.info(
                                f"[MCPConnector] Loaded {len(tool_list)} tools from {name}"
                            )
                except Exception as e:
                    logger.warning(
                        f"[MCPConnector] Failed to list tools from {name}: {e}"
                    )

        asyncio.run(_fetch())

    def get_tools(self) -> list[MCPTool]:
        """
        Return a shallow copy of the list of MCPTool instances.
        Ensures external code cannot modify our internal cache.
        """
        return self.tools.copy()