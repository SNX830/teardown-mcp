"""Command line entry point: ``buildup-mcp [--workspace PATH]``."""

import argparse
import logging
import os
from collections.abc import Sequence
from pathlib import Path

from buildup import __version__
from buildup.server.app import create_server

logger = logging.getLogger(__name__)

WORKSPACE_VARIABLE = "BUILDUP_WORKSPACE"


def resolve_workspace(argument: str | None, environ: dict[str, str] | None = None) -> Path:
    """Workspace folder: ``--workspace``, else ``$BUILDUP_WORKSPACE``, else ``./workspace``.

    The result is absolute, so every path the tools report can be opened as is.
    """
    env = os.environ if environ is None else environ
    chosen = argument or env.get(WORKSPACE_VARIABLE) or "workspace"
    return Path(chosen).expanduser().resolve()


def main(argv: Sequence[str] | None = None) -> None:
    """Run the server on stdio until the client disconnects.

    Logging goes to stderr: stdout carries the protocol (AGENTS.md rule 5).
    """
    parser = argparse.ArgumentParser(
        prog="buildup-mcp", description="Buildup MCP server for Teardown voxel models."
    )
    parser.add_argument(
        "--workspace",
        help=f"folder for projects and exported mods (default: ${WORKSPACE_VARIABLE} or "
        "./workspace)",
    )
    parser.add_argument("--version", action="version", version=f"buildup-mcp {__version__}")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    workspace = resolve_workspace(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    logger.info("buildup-mcp %s, workspace %s", __version__, workspace)
    create_server(workspace).run("stdio")
