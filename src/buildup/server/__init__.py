"""The Buildup MCP server (stdio transport, for Claude Code and other MCP hosts)."""

from buildup.server.app import INSTRUCTIONS, create_server
from buildup.server.main import main, resolve_workspace

__all__ = ["INSTRUCTIONS", "create_server", "main", "resolve_workspace"]
