import json
from pathlib import Path

import pytest

import write_mcp_config as config


def test_writes_a_project_scoped_server(tmp_path: Path) -> None:
    folder = tmp_path / "BuildupTest"
    path = config.write_config(folder)
    assert path == folder.resolve() / ".mcp.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data["mcpServers"]["buildup"]
    assert entry["command"] == "uv"
    assert entry["args"] == [
        "run",
        "--project",
        str(config.ROOT),
        "buildup-mcp",
        "--workspace",
        str(folder.resolve() / "workspace"),
    ]
    assert (config.ROOT / "pyproject.toml").is_file()


def test_keeps_other_servers(tmp_path: Path) -> None:
    path = tmp_path / ".mcp.json"
    path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    config.write_config(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data["mcpServers"]) == {"other", "buildup"}


def test_refuses_the_repository_and_bad_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="inside the Buildup repository"):
        config.write_config(config.ROOT / "workspace" / "test")
    (tmp_path / ".mcp.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="not contain a JSON object"):
        config.write_config(tmp_path)
    (tmp_path / ".mcp.json").write_text('{"mcpServers": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="'mcpServers' is not a JSON object"):
        config.write_config(tmp_path)
