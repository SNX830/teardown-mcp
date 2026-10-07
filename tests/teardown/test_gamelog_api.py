"""Game log reader, Lua API search and install detection.

Fixtures are invented text in the formats described in docs/TEARDOWN_REFERENCE.md §7; tests
marked ``game`` read the user's real files (never copied).
"""

from pathlib import Path

import pytest

from buildup.teardown.api import ApiError, load_api, parse_definitions, search
from buildup.teardown.gamelog import (
    ModMatcher,
    local_mod_id,
    parse_log,
    read_log,
    select,
    summarize,
)
from buildup.teardown.install import (
    GamePaths,
    default_log_path,
    find_install,
    steam_libraries,
)

LOG = """\
header line before any entry
0000 00:00:00.010000 INFO a1b2 [NoTag|Init] Platform available: 1
0000 00:00:00.020000 INFO a1b2 [NoTag|Init] CPU: Example CPU
Hardware threads: 4

0001 00:00:05.000000 INFO a1b2 [NoTag] Spawning: local-red-pickup:prefab/car.xml (mod path: x)
0002 00:00:06.000000 ERROR c3d4 [NoTag] File not found C:/mods/Red Pickup/vox/a.vox
0003 00:00:07.000000 WARNING c3d4 [NoTag] [string "x.lua"]:3: Called before init
0004 00:00:08.000000 ERROR c3d4 [NoTag] File not found C:/mods/Red Pickup/vox/a.vox
0005 00:00:09.000000 ERROR c3d4 [NoTag|Loading] Something else broke
"""


def test_parse_log_joins_continuation_lines() -> None:
    entries = parse_log(LOG)
    assert len(entries) == 7
    cpu = entries[1]
    assert (cpu.line, cpu.time, cpu.level, cpu.tags) == (3, "00:00:00.020000", "INFO", "NoTag|Init")
    assert cpu.message == "CPU: Example CPU\nHardware threads: 4"
    assert entries[3].level == "ERROR"
    assert entries[3].line == 7


def test_select_by_level_and_mod() -> None:
    entries = parse_log(LOG)
    errors = select(entries, ["error"])
    assert [e.line for e in errors] == [7, 9, 10]
    mine = select(entries, ["ERROR", "WARNING"], ModMatcher("Red Pickup"))
    assert [e.line for e in mine] == [6, 7, 9]  # the spawn line is kept, the other mod is not
    by_id = select(entries, ["ERROR"], ModMatcher("red pickup"))
    assert [e.line for e in by_id] == [6, 7, 9]  # case-insensitive; spawns kept for any level
    grouped = summarize(mine)
    assert [(e.line, n) for e, n in grouped] == [(6, 1), (7, 2)]


def test_mod_matcher() -> None:
    other = ModMatcher("Other Mod")
    assert not other.matches("Something about another mod")
    assert not other.matches("Something about Other Mod")  # not a path segment
    assert other.matches("File not found C:/mods/Other Mod/a.vox")
    assert other.matches(r"File not found C:\mods\other mod\a.vox")
    assert other.matches('Spawning: <script file="x.lua"/> (mod path: C:/mods/Other Mod)')
    assert other.matches("Spawning: local-other-mod:prefab/p.xml (mod path: x)")
    assert not other.matches("Spawning: local-other-mod-2:prefab/p.xml")
    assert not other.matches("File not found C:/mods/Other Mod 2/a.vox")
    car = ModMatcher("Car")
    assert not car.matches('Spawning: <script file="MOD/car.lua"/> (mod path: C:/content/123)')
    assert not car.matches("File not found C:/content/123/vox/car.vox")


def test_lua_chunk_names_are_matched_by_the_end_of_a_mod_script() -> None:
    police = ModMatcher("Police Interceptor", ("main.lua", "scripts/siren.lua"))
    assert police.matches('[string "...Interceptor/scripts/siren.lua"]:12: attempt to index nil')
    assert police.matches('[string "...ceptor/scripts/siren.lua"]:12: error')
    assert not police.matches('[string "...ripts/siren.lua"]:12: error')  # not the whole path
    assert police.matches('[string ".../mods/Police Interceptor/main.lua"]:1: error')
    assert not police.matches('[string "...siren.lua"]:12: error')  # too short to be sure
    assert not police.matches('[string "...tent/1167630/2415643616/main.lua"]:26: error')
    assert not police.matches('[string "...8736/TABS/scripts/siren.lua"]:3: error')
    assert not ModMatcher("Police Interceptor").matches('[string "...ceptor/scripts/siren.lua"]: x')
    # A relative path longer than the kept end matches by its last characters (24 or more).
    deep = ModMatcher("Tanks", ("scripts/weapons/main_cannon_controller.lua",))
    assert deep.matches('[string "...apons/main_cannon_controller.lua"]:5: error')
    assert not deep.matches('[string "...n_controller.lua"]:5: error')


def test_local_mod_id() -> None:
    assert local_mod_id("Petite Rouge") == "local-petite-rouge"
    assert local_mod_id("Car  2") == "local-car--2"  # each space becomes a dash (not verified)


def test_entries_with_upper_case_ids_and_no_tags() -> None:
    entries = parse_log("0001 00:00:01.0 ERROR AB12 message without tags\n")
    assert [(e.level, e.tags, e.message) for e in entries] == [
        ("ERROR", "", "message without tags")
    ]


def test_read_log_tolerates_bad_bytes(tmp_path: Path) -> None:
    path = tmp_path / "log.txt"
    path.write_bytes(LOG.encode() + b"0006 00:00:10.000000 ERROR c3d4 [NoTag] bad \xff byte\n")
    assert read_log(path)[-1].message == "bad \ufffd byte"


DEFINITIONS = """\
---@meta _

---@class TExample
---@field [0] number

--- Return the answer to a made-up question
---
--- Example:
--- ```lua
--- local a = ComputeAnswer(1, "x")
--- 	DebugPrint(a)
--- ```
---@param seed number A seed value
---@param label string Label shown
---@return number answer The answer
---@return boolean ok
function ComputeAnswer(seed, label) return 0, true end

local helper = 1

---@param handle number Thing handle
function client.thing.Touch(handle) end

function Undocumented() end
"""


def test_parse_definitions() -> None:
    functions = parse_definitions(DEFINITIONS, "made_up.lua")
    assert [f.name for f in functions] == ["ComputeAnswer", "client.thing.Touch", "Undocumented"]
    answer = functions[0]
    assert answer.arguments == ("seed", "label")
    assert answer.description == "Return the answer to a made-up question"
    assert answer.example == 'local a = ComputeAnswer(1, "x")\n\tDebugPrint(a)'
    assert answer.params == (("seed", "number", "A seed value"), ("label", "string", "Label shown"))
    assert answer.returns == (("number", "answer", "The answer"), ("boolean", "ok", ""))
    assert answer.source == "made_up.lua:17"
    assert answer.signature() == "ComputeAnswer(seed, label) -> number answer, boolean ok"
    details = answer.details()
    assert "Parameters:\n  seed (number): A seed value" in details
    assert "  ok (boolean)" in details
    assert details.endswith('Example:\nlocal a = ComputeAnswer(1, "x")\n\tDebugPrint(a)')
    touch = functions[1]
    assert touch.description == ""
    assert touch.summary() == "client.thing.Touch(handle)"
    assert functions[2].details() == "Undocumented()\n(from made_up.lua:24)"


def test_search() -> None:
    functions = parse_definitions(DEFINITIONS, "made_up.lua")
    assert [f.name for f in search(functions, "answer")] == ["ComputeAnswer"]
    assert [f.name for f in search(functions, "thing touch")] == ["client.thing.Touch"]
    assert search(functions, "seed") == []
    assert [f.name for f in search(functions, "seed", full_text=True)] == ["ComputeAnswer"]
    assert search(functions, "  ") == []
    # An exact name comes first.
    more = parse_definitions("function AB() end\nfunction A() end\nfunction ABC() end\n", "x")
    assert [f.name for f in search(more, "a")] == ["A", "AB", "ABC"]
    assert [f.name for f in search(more, "ab")] == ["AB", "ABC"]


def test_load_api(tmp_path: Path) -> None:
    with pytest.raises(ApiError, match="TEARDOWN_DIR"):
        load_api(None)
    (tmp_path / "data").mkdir()
    with pytest.raises(ApiError, match="no API definitions"):
        load_api(tmp_path)
    (tmp_path / "data" / "script_defs.lua").write_text(DEFINITIONS, encoding="utf-8")
    (tmp_path / "data" / "voxscript_defs.lua").write_text("function Vox() end\n", encoding="utf-8")
    assert [f.name for f in load_api(tmp_path)][-1] == "Vox"


def test_install_detection(tmp_path: Path) -> None:
    game = tmp_path / "Library" / "steamapps" / "common" / "Teardown"
    (game / "data").mkdir(parents=True)
    steam = tmp_path / "Steam"
    (steam / "steamapps").mkdir(parents=True)
    library = str(tmp_path / "Library").replace("\\", "\\\\")
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"0"\n\t{{\n\t\t"path"\t\t"{library}"\n\t}}\n}}\n',
        encoding="utf-8",
    )
    assert steam_libraries((steam,)) == [steam, tmp_path / "Library"]
    assert find_install({}, (steam,)) == game
    assert find_install({}, (tmp_path / "nothing",)) is None
    assert find_install({"TEARDOWN_DIR": str(game)}, ()) == game
    assert find_install({"TEARDOWN_DIR": str(tmp_path)}, (steam,)) == game  # wrong: fallback
    assert find_install({"TEARDOWN_DIR": str(tmp_path)}, ()) is None
    assert default_log_path({"LOCALAPPDATA": "C:/AppData"}) == Path("C:/AppData/Teardown/log.txt")
    assert default_log_path({"TEARDOWN_LOG": "x.txt", "LOCALAPPDATA": "y"}) == Path("x.txt")
    assert default_log_path({}) is None
    paths = GamePaths.detect({"TEARDOWN_DIR": str(game), "LOCALAPPDATA": str(tmp_path)})
    assert (paths.install, paths.log) == (game, tmp_path / "Teardown" / "log.txt")
    assert paths.local_mods is None or paths.local_mods.name == "mods"


@pytest.mark.game
def test_real_api_definitions(teardown_dir: Path) -> None:
    functions = load_api(teardown_dir)
    assert len(functions) > 700
    (size,) = [f for f in functions if f.name == "GetShapeSize"]
    # docs/TEARDOWN_REFERENCE.md §7b: voxels on three axes and the voxel scale.
    assert [r[1] for r in size.returns] == ["xsize", "ysize", "zsize", "scale"]
    assert size.example
    assert search(functions, "GetVehicleDriverPos")[0].name == "GetVehicleDriverPos"


@pytest.mark.game
def test_real_game_log() -> None:
    path = default_log_path()
    if path is None or not path.is_file():
        pytest.skip("no Teardown log on this machine")
    entries = read_log(path)
    assert entries
    assert {e.level for e in entries} <= {"INFO", "WARNING", "ERROR", "DEBUG"}


def test_loaded_scripts_of_the_mod_are_kept() -> None:
    entries = parse_log(
        "0001 00:00:31.0 INFO a3bd [NoTag|LocalMod] C:/U/Documents/Teardown/mods/Car/script/t.lua\n"
        "0002 00:00:31.1 INFO a3bd [NoTag|LocalMod] C:/U/Documents/Teardown/mods/Bus/script/t.lua\n"
    )
    assert [e.line for e in select(entries, ["ERROR"], ModMatcher("Car"))] == [1]
    assert select(entries, ["ERROR"]) == []
