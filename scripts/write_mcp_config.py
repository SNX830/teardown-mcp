"""Register the Buildup MCP server for Claude Code sessions opened in a folder.

Usage:
    uv run python scripts/write_mcp_config.py FOLDER

Writes (or updates) ``FOLDER/.mcp.json``, the project-scoped MCP configuration of Claude Code,
with a ``buildup`` server that runs this repository's code through uv and keeps its workspace in
``FOLDER/workspace``. Claude Code asks once to approve the server when a session starts in FOLDER.

FOLDER must be outside this repository: a Claude Code session started inside it would also read
this repository's AGENTS.md / CLAUDE.md, which are instructions for Buildup's developers.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER_NAME = "buildup"


def server_entry(folder: Path) -> dict[str, Any]:
    """The ``mcpServers`` entry for a session folder."""
    return {
        "command": "uv",
        "args": [
            "run",
            "--project",
            str(ROOT),
            "buildup-mcp",
            "--workspace",
            str(folder / "workspace"),
        ],
    }


def write_config(folder: Path) -> Path:
    """Create or update ``folder/.mcp.json`` and return its path.

    Other servers already listed in the file are kept.

    Raises:
        ValueError: If ``folder`` is inside this repository, or the existing file (or its
            ``mcpServers`` entry) is not a JSON object.
    """
    folder = folder.resolve()
    if folder == ROOT or ROOT in folder.parents:
        raise ValueError(f"{folder} is inside the Buildup repository; choose a folder outside it")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ".mcp.json"
    config: Any = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(config, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"{path}: 'mcpServers' is not a JSON object")
    servers[SERVER_NAME] = server_entry(folder)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path, help="folder where Claude Code will be started")
    args = parser.parse_args()
    try:
        path = write_config(args.folder)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {path}")
    print(f"Open Claude Code in {path.parent} and approve the '{SERVER_NAME}' MCP server.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
