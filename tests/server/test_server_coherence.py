"""validate_mod, read_game_log and lookup_api through the MCP client, with invented game files."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from mcp import Client
from mcp.types import CallToolResult

from buildup.server import create_server
from buildup.teardown.install import GamePaths

DEFINITIONS = """\
--- Return the answer to a made-up question
---@param seed number A seed value
---@return number answer The answer
function ComputeAnswer(seed) return 0 end

--- Make a made-up thing glow
function ThingGlow(handle) end

function ThingDim(handle) end
"""

LOG = """\
0000 00:00:00.010000 INFO a1b2 [NoTag|Init] Platform available: 1
0001 00:00:05.000000 INFO a1b2 [NoTag] Spawning: local-car:prefab/car.xml (mod path: x)
0002 00:00:06.000000 ERROR c3d4 [NoTag] File not found C:/mods/Car/vox/a.vox
0003 00:00:06.500000 ERROR c3d4 [NoTag] File not found C:/mods/Car/vox/a.vox
0004 00:00:07.000000 WARNING c3d4 [NoTag] Something about another mod
"""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def game(tmp_path: Path) -> GamePaths:
    install = tmp_path / "Teardown"
    (install / "data").mkdir(parents=True)
    (install / "data" / "script_defs.lua").write_text(DEFINITIONS, encoding="utf-8")
    log = tmp_path / "log.txt"
    log.write_text(LOG, encoding="utf-8")
    return GamePaths(install, log)


@pytest.fixture
async def client(tmp_path: Path, game: GamePaths) -> AsyncIterator[Client]:
    async with Client(create_server(tmp_path / "ws", game), raise_exceptions=True) as c:
        yield c


def text_of(result: CallToolResult) -> str:
    return "\n".join(block.text for block in result.content if block.type == "text")


async def call(client: Client, tool: str, **arguments: Any) -> tuple[bool, str]:
    result = await client.call_tool(tool, arguments)
    return result.is_error, text_of(result)


async def export_car(client: Client) -> None:
    steps: list[tuple[str, dict[str, Any]]] = [
        ("create_project", {}),
        ("define_color", {"name": "paint", "material": "weak metal", "rgb": [200, 0, 0]}),
        ("define_color", {"name": "tire", "material": "plastic", "rgb": [20, 20, 20]}),
        ("add_part", {"name": "body"}),
        ("draw_box", {"part": "body", "start": [-8, 3, -20], "end": [8, 9, 20], "color": "paint"}),
        (
            "add_wheels",
            {
                "axles": [{"z": -13, "steer": True}, {"z": 13, "drive": True}],
                "diameter": 8,
                "width": 2,
                "inner_x": 9,
                "tire_color": "tire",
            },
        ),
        ("set_anchor", {"name": "player", "position": [-4, 9, 2]}),
        ("export_model", {}),
    ]
    for tool, arguments in steps:
        failed, text = await call(client, tool, project="car", **arguments)
        assert not failed, text


@pytest.mark.anyio
async def test_validate_mod(client: Client, tmp_path: Path) -> None:
    await export_car(client)
    mod = tmp_path / "ws" / "mods" / "Car"
    failed, text = await call(client, "validate_mod", mod_name="Car")
    assert not failed
    assert "1 error(s)" in text
    assert "ERROR info.txt: missing" in text
    assert "Fix the errors before testing in game" in text
    (mod / "info.txt").write_text("name = Car\nauthor = a\ndescription = d\ntags = Vehicle\n")
    (mod / "spawn.txt").write_text("prefab/car.xml : Test/Car\n")
    failed, text = await call(client, "validate_mod", path=str(mod))
    assert not failed
    assert "0 error(s), 0 warning(s), 1 note(s)" in text  # no vital/exhaust: a note only
    for arguments, message in (
        ({}, "either mod_name"),
        ({"mod_name": "Car", "path": str(mod)}, "not both"),
        ({"mod_name": "../Car"}, "folder name of workspace/mods"),
    ):
        failed, text = await call(client, "validate_mod", **arguments)
        assert failed
        assert message in text
    failed, text = await call(client, "validate_mod", mod_name="Nothing")
    assert "mod folder not found" in text


@pytest.mark.anyio
async def test_findings_are_capped(client: Client, tmp_path: Path) -> None:
    mod = tmp_path / "ws" / "mods" / "Many"
    mod.mkdir(parents=True)
    (mod / "info.txt").write_text("name = Many\nauthor = a\ndescription = d\ntags = Vehicle\n")
    lines = "".join(f"prefab/p{i}.xml : A/B\n" for i in range(100))
    (mod / "spawn.txt").write_text(lines)
    _, text = await call(client, "validate_mod", mod_name="Many")
    assert "100 error(s)" in text
    assert "... and 21 more" in text  # 100 errors and 1 warning


@pytest.mark.anyio
async def test_read_game_log(client: Client, game: GamePaths) -> None:
    _, text = await call(client, "read_game_log")
    assert "5 messages, 2 distinct shown for levels error, warning" in text
    assert "- line 3, 00:00:06.000000 ERROR (x2): File not found C:/mods/Car/vox/a.vox" in text
    _, text = await call(client, "read_game_log", mod="Car", levels=["error"])
    assert "concerning 'Car' (log id 'local-car')" in text
    assert "Spawning: local-car:prefab/car.xml" in text
    assert "another mod" not in text
    _, text = await call(client, "read_game_log", mod="Other Mod")
    assert "No message concerns this mod. The mod folder was not found" in text
    assert "run read_game_log without mod to see every error" in text
    _, text = await call(client, "read_game_log", levels=["info"], max_entries=1)
    assert "... and 1 more" in text
    assert game.log is not None
    game.log.write_text("0 00:00:01.0 ERROR ab [NoTag] " + "x" * 700 + "\n")
    _, text = await call(client, "read_game_log")
    assert text.endswith(" [...]")
    game.log.unlink()
    failed, text = await call(client, "read_game_log")
    assert failed
    assert "no game log found" in text


@pytest.mark.anyio
async def test_lookup_api(client: Client) -> None:
    _, text = await call(client, "lookup_api", query="computeanswer")
    assert text.startswith("ComputeAnswer(seed) -> number answer\n(from script_defs.lua:4)")
    assert "seed (number): A seed value" in text
    _, text = await call(client, "lookup_api", query="thing")
    assert text.splitlines()[0] == "2 functions match 'thing':"
    assert "- ThingDim(handle)" in text
    assert "- ThingGlow(handle): Make a made-up thing glow" in text
    _, text = await call(client, "lookup_api", query="thing", max_results=1)
    assert "... and 1 more; refine the query" in text
    _, text = await call(client, "lookup_api", query="ThingGlow")
    assert "Also matching" not in text
    _, text = await call(client, "lookup_api", query="glow")
    assert text.startswith("ThingGlow(handle)")  # a single match gives the details
    _, text = await call(client, "lookup_api", query="question")
    assert text == "No API function matches 'question'. Try full_text=true."
    _, text = await call(client, "lookup_api", query="question", full_text=True)
    assert text.startswith("ComputeAnswer")
    _, text = await call(client, "lookup_api", query="seed answer", full_text=True)
    assert text.startswith("ComputeAnswer")


@pytest.mark.anyio
async def test_lookup_api_without_install(tmp_path: Path) -> None:
    server = create_server(tmp_path / "ws", GamePaths(install=None, log=None))
    async with Client(server, raise_exceptions=True) as client:
        failed, text = await call(client, "lookup_api", query="x")
    assert failed
    assert "TEARDOWN_DIR" in text


@pytest.mark.anyio
async def test_lua_errors_of_the_mod_are_found_by_script_path(
    client: Client, tmp_path: Path, game: GamePaths
) -> None:
    mod = tmp_path / "ws" / "mods" / "Police Interceptor"
    (mod / "scripts").mkdir(parents=True)
    (mod / "scripts" / "siren.lua").write_text("#version 2\n")
    assert game.log is not None
    game.log.write_text(
        '0001 00:00:02.0 ERROR ab [NoTag] [string "...Interceptor/scripts/siren.lua"]:12: '
        "attempt to index a nil value\n"
        '0002 00:00:03.0 ERROR ab [NoTag] [string "...8736/TABS/scripts/ballistics.lua"]:1: x\n'
    )
    _, text = await call(client, "read_game_log", mod="Police Interceptor")
    assert 'siren.lua"]:12: attempt to index a nil value' in text
    assert "ballistics" not in text
    assert "Lua runtime errors are not written to log.txt" in text
    failed, text = await call(client, "read_game_log", mod="")
    assert failed  # an empty name would match path fragments


@pytest.mark.anyio
async def test_validate_mod_paths_and_labels(client: Client, tmp_path: Path) -> None:
    failed, text = await call(client, "validate_mod", path="relative/folder")
    assert failed
    assert "absolute folder path" in text
    failed, text = await call(client, "validate_mod", path=" ")
    assert failed
    mod = tmp_path / "ws" / "mods" / "Note"
    mod.mkdir(parents=True)
    (mod / "info.txt").write_text("name = n\nauthor = a\ndescription = d\n")
    (mod / "main.lua").write_text("#version 2\n")
    _, text = await call(client, "validate_mod", mod_name="Note")
    assert "- NOTE info.txt: no tags" in text
    (mod / "info.txt").write_text("name = n\nauthor = a\ndescription = d\ntags = Gameplay\n")
    _, text = await call(client, "validate_mod", mod_name="Note")
    assert text.endswith("No problem found.")


@pytest.mark.anyio
async def test_lookup_api_shows_every_file_with_the_name(tmp_path: Path, game: GamePaths) -> None:
    assert game.install is not None
    (game.install / "data" / "voxscript_defs.lua").write_text(
        "--- Voxel script version\nfunction ComputeAnswer(a, b) return 0 end\n"
    )
    async with Client(create_server(tmp_path / "ws2", game), raise_exceptions=True) as client:
        _, text = await call(client, "lookup_api", query="ComputeAnswer()")
        _, listing = await call(client, "lookup_api", query="compute")
    assert "(from script_defs.lua:4)" in text
    assert "ComputeAnswer(a, b)\n(from voxscript_defs.lua:2)" in text
    assert "[voxscript_defs.lua]" in listing
