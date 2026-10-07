"""The command line entry point, and the server running as a real stdio subprocess."""

import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from buildup import __version__
from buildup.server import main, resolve_workspace
from buildup.server.main import WORKSPACE_VARIABLE


def test_workspace_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_workspace(None, {}) == tmp_path.resolve() / "workspace"
    env = {WORKSPACE_VARIABLE: str(tmp_path / "from_env")}
    assert resolve_workspace(None, env) == (tmp_path / "from_env").resolve()
    assert resolve_workspace("arg", env) == (tmp_path / "arg").resolve()
    assert resolve_workspace(None).is_absolute()


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"buildup-mcp {__version__}"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_stdio_server_speaks_only_the_protocol_on_stdout(tmp_path: Path) -> None:
    """A stray print on stdout would break the protocol (AGENTS.md rule 5)."""
    workspace = tmp_path / "ws"
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "buildup.server", "--workspace", str(workspace)],
    )
    async with Client(server) as client:
        tools = await client.list_tools()
        assert len(tools.tools) == 25
        result = await client.call_tool("create_project", {"project": "car"})
        assert not result.is_error
    assert (workspace / "projects" / "car" / "project.json").is_file()
