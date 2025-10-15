#!/usr/bin/env python3
"""
Simple MCP Filesystem Server for Windows
Provides basic file operations through the Model Context Protocol
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the server instance
server = Server("filesystem-server")

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available filesystem tools."""
    return [
        Tool(
            name="read_file",
            description="Read the contents of a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write content to a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="list_directory",
            description="List contents of a directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to list"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="create_directory",
            description="Create a new directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the directory to create"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="delete_file",
            description="Delete a file or directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file or directory to delete"
                    }
                },
                "required": ["path"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    try:
        if name == "read_file":
            path = arguments["path"]
            if not os.path.exists(path):
                return [TextContent(type="text", text=f"Error: File '{path}' does not exist")]
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return [TextContent(type="text", text=content)]
        
        elif name == "write_file":
            path = arguments["path"]
            content = arguments["content"]
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return [TextContent(type="text", text=f"Successfully wrote to '{path}'")]
        
        elif name == "list_directory":
            path = arguments["path"]
            if not os.path.exists(path):
                return [TextContent(type="text", text=f"Error: Directory '{path}' does not exist")]
            
            if not os.path.isdir(path):
                return [TextContent(type="text", text=f"Error: '{path}' is not a directory")]
            
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    items.append(f"[DIR]  {item}")
                else:
                    size = os.path.getsize(item_path)
                    items.append(f"[FILE] {item} ({size} bytes)")
            
            return [TextContent(type="text", text="\n".join(items))]
        
        elif name == "create_directory":
            path = arguments["path"]
            os.makedirs(path, exist_ok=True)
            return [TextContent(type="text", text=f"Successfully created directory '{path}'")]
        
        elif name == "delete_file":
            path = arguments["path"]
            if not os.path.exists(path):
                return [TextContent(type="text", text=f"Error: Path '{path}' does not exist")]
            
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
                return [TextContent(type="text", text=f"Successfully deleted directory '{path}'")]
            else:
                os.remove(path)
                return [TextContent(type="text", text=f"Successfully deleted file '{path}'")]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    """Run the MCP server."""
    logger.info("Starting MCP Filesystem Server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
