"""Buildup: an MCP server that lets an AI build Teardown-ready voxel models."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("buildup-mcp")
except PackageNotFoundError:  # pragma: no cover - source tree imported without being installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
