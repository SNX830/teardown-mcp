"""validate_mod on a mod exported by Buildup, then broken in one way at a time."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from buildup.project import Axle, Project, WheelLayout, box_shape, export_project
from buildup.teardown.validate import Finding, manifests_in, validate_mod

INFO = "name = Red Car\nauthor = test\ndescription = A test car\ntags = Vehicle\n"
SPAWN = "prefab/red_car.xml : Buildup/Red Car\n"


@pytest.fixture
def mod(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """A complete, correct vehicle mod and its manifests."""
    p = Project("red_car", "vehicle")
    p.define_color("paint", "weak metal", (200, 30, 30))
    p.define_color("tire", "plastic", (20, 20, 20))
    p.add_part("body")
    p.draw("body", box_shape((-8, 3, -20), (8, 9, 20)), "add", "paint")
    p.add_wheels([Axle(-13, steer=True), Axle(13, drive=True)], WheelLayout(8, 2, 9), "tire")
    for name, point in {"player": (-4, 9, 2), "vital": (0, 6, -15), "exhaust": (5, 4, 20)}.items():
        p.set_anchor(name, point)
    projects = tmp_path / "projects"
    result = export_project(
        p, project_folder=projects / "red_car", mods_dir=tmp_path / "mods", mod_name="Red Car"
    )
    (result.mod_folder / "info.txt").write_text(INFO, encoding="utf-8")
    (result.mod_folder / "spawn.txt").write_text(SPAWN, encoding="utf-8")
    return result.mod_folder, manifests_in(projects.iterdir())


def prefab(folder: Path) -> Path:
    return folder / "prefab" / "red_car.xml"


def edit_prefab(folder: Path, old: str, new: str) -> None:
    path = prefab(folder)
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def messages(findings: list[Finding], level: str | None = None) -> list[str]:
    return [f"{f.file}: {f.message}" for f in findings if level is None or f.level == level]


def test_exported_mod_is_clean(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    assert list(manifests) == ["MOD/vox/red_car.vox"]
    assert validate_mod(folder, manifests) == []


def test_info_txt(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    info = folder / "info.txt"
    info.write_text("# a comment\nen_name = Red Car\nen_description = x\ntags = Vehicle, Car\n")
    found = messages(validate_mod(folder, manifests))
    assert found == [
        "info.txt: no 'author = ...' line",
        "info.txt: tag 'Car' is not a documented tag (Map, Gameplay, Asset, Vehicle, Tool, Spawn)",
    ]
    info.write_text("author = me\nthis line has no equal sign\n")
    found = messages(validate_mod(folder, manifests))
    assert "info.txt: no 'name = ...' line" in found
    assert "info.txt: line 2 is not 'key = value': 'this line has no equal sign'" in found
    assert any("no tags" in m for m in found)
    info.unlink()
    (error,) = validate_mod(folder, manifests)
    assert error.level == "error"
    assert "every mod needs an info.txt" in error.message


def test_spawn_txt(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    (folder / "spawn.txt").write_text(
        "# comment\n\nprefab/red_car.xml : Red Car\nprefab/none.xml : A/B\nno colon here\n"
        "vox/red_car.vox : A/B\n"
    )
    found = validate_mod(folder, manifests)
    assert messages(found, "error") == [
        "spawn.txt: line 4: 'prefab/none.xml' not found (paths start at the mod folder)",
        "spawn.txt: line 5: expected 'path/to/prefab.xml : Category/Name', got 'no colon here'",
        "spawn.txt: line 6: 'vox/red_car.vox' is not an .xml prefab",
    ]
    assert messages(found, "warning") == []
    assert messages(found, "info") == [
        "spawn.txt: line 3: the name 'Red Car' has no category ('Category/Name'); official spawn "
        "files mostly use one"
    ]
    (folder / "spawn.txt").unlink()
    (note,) = validate_mod(folder, manifests)
    assert note.level == "info"
    assert note.message.startswith("no spawn.txt entry, no main.xml and no main.lua")


def test_xml_references(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    edit_prefab(folder, 'object="wheel_fl"', 'object="wheel_front_left"')
    edit_prefab(
        folder,
        'file="MOD/vox/red_car.vox" object="wheel_fr"',
        'file="MOD/vox/gone.vox" object="wheel_fr"',
    )
    edit_prefab(
        folder,
        'file="MOD/vox/red_car.vox" object="wheel_bl"',
        'file="vox/red_car.vox" object="wheel_bl"',
    )
    found = validate_mod(folder, manifests)
    errors = messages(found, "error")
    assert len(errors) == 2
    assert re.search(r"has no object 'wheel_front_left'; its objects: body, wheel_bl", errors[0])
    assert "file MOD/vox/gone.vox not found in the mod folder" in errors[1]
    assert any("'vox/red_car.vox' not checked" in m for m in messages(found, "info"))


def test_xml_syntax_and_values(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    (folder / "prefab" / "broken.xml").write_text("<prefab><group></prefab>")
    edit_prefab(folder, 'travel="-0.1 0.1"', 'travel="-0.1 0.1" rot="0, 90, 0"')
    found = validate_mod(folder, manifests)
    assert any(
        f.level == "error" and f.file == "prefab/broken.xml" and "XML syntax error" in f.message
        for f in found
    )
    assert any("rot='0, 90, 0' is not 1 to 3 numbers" in m for m in messages(found, "warning"))


def test_short_vectors_are_accepted(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    edit_prefab(folder, '<body dynamic="true">', '<body dynamic="true" rot="0">')
    edit_prefab(
        folder,
        'travel="-0.1 0.1">',
        'travel="-0.1 0.1" rot="0 180">',
    )
    found = validate_mod(folder, manifests)
    assert messages(found, "error") == []
    assert messages(found, "warning") == []
    assert any("rotated, position not compared" in m for m in messages(found, "info"))


def test_vehicle_structure(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    text = prefab(folder).read_text(encoding="utf-8")
    text = re.sub(r'(<wheel name="br"[^>]*>)\s*<vox [^>]*/>', r"\1", text)
    text = re.sub(r'<location tags="(player|vital)" [^>]*/>', "", text)
    prefab(folder).write_text(text, encoding="utf-8")
    found = validate_mod(folder, manifests)
    assert any('<wheel name="br"> has no <vox>' in m for m in messages(found, "error"))
    assert any("no location tagged player" in m for m in messages(found, "warning"))
    assert any("no location tagged vital" in m for m in messages(found, "info"))
    prefab(folder).write_text(
        '<prefab version="2.0.0"><group><vehicle tags="boat nodrive"/></group></prefab>'
    )
    found = validate_mod(folder, manifests)
    assert messages(found, "warning") == []
    assert any("has no <body>" in m for m in messages(found, "error"))
    assert any("has no <wheel> (official boats have none)" in m for m in messages(found, "info"))


def test_positions_are_compared_with_the_manifest(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    edit_prefab(folder, '<vox pos="0 0.3 0"', '<vox pos="0 0.4 0"')
    edit_prefab(folder, '<wheel name="fl" pos="-1 0.4 -1.3"', '<wheel name="fl" pos="-1 0.5 -1.3"')
    edit_prefab(
        folder,
        '<location tags="exhaust" pos="0.5 0.1 2"',
        '<location tags="exhaust" pos="0.5 0.2 2"',
    )
    found = messages(validate_mod(folder, manifests), "warning")
    assert len(found) == 3, found
    assert any(
        '<vox object="body"' in m
        and "pos 0 0.4 0 differs from the manifest (project 'red_car': vox_pos_m = 0 0.3 0)" in m
        for m in found
    )
    wheel = (
        "<wheel name=\"fl\">: pos -1 0.5 -1.3 differs from the manifest (project 'red_car': axle_m"
    )
    assert any(wheel in m for m in found)
    # Locations are relative to the vox: only the edited exhaust is off, not those that moved
    # with the misplaced vox.
    (location,) = [m for m in found if "anchor minus vox" in m]
    assert '<location tags="exhaust">: pos 0.5 0.2 2 differs' in location
    # Without manifests nothing is compared.
    assert messages(validate_mod(folder, {}), "warning") == []


def test_positions_outside_body_or_wheel_are_not_compared(
    mod: tuple[Path, dict[str, Any]],
) -> None:
    folder, manifests = mod
    edit_prefab(folder, '<body dynamic="true">', '<body dynamic="true"><script file="MOD/x.lua">')
    edit_prefab(folder, '<wheel name="fl"', '</script><wheel name="fl"')
    (folder / "x.lua").write_text("#version 2\n")
    found = validate_mod(folder, manifests)
    assert messages(found, "warning") == []
    assert any("not inside a body or wheel" in m for m in messages(found, "info"))


def test_folder_level_checks(mod: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    folder, manifests = mod
    (folder / "preview.jpg").write_bytes(b"\0" * (1024 * 1024 + 1))
    (folder / "vox" / "bad.vox").write_bytes(b"not a vox")
    edit_prefab(
        folder,
        'file="MOD/vox/red_car.vox" object="wheel_br"',
        'file="MOD/vox/bad.vox" object="wheel_br"',
    )
    renamed = folder.rename(folder.parent / "Red_Car")
    found = messages(validate_mod(renamed, manifests), "warning")
    assert any("folder name 'Red_Car'" in m for m in found)
    assert "preview.jpg: larger than 1 MB, the Workshop limit" in found
    assert any(m.startswith("vox/bad.vox: cannot read this .vox file") for m in found)
    (missing,) = validate_mod(tmp_path / "nothing")
    assert missing.level == "error"
    assert "mod folder not found" in missing.message


def test_manifests_in_keeps_only_complete_current_manifests(
    mod: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    _, manifests = mod
    good = manifests["MOD/vox/red_car.vox"]
    folders = tmp_path / "manifests"
    variants: dict[str, object] = {
        "broken": "{broken",
        "good": good,
        "other_version": {**good, "vox_file": "MOD/vox/v.vox", "manifest_version": 2},
        "no_objects": {k: v for k, v in good.items() if k != "objects"},
        "null_objects": {**good, "objects": None},
        "short_vector": {
            **good,
            "objects": [{**good["objects"][0], "vox_pos_m": [0, 0.3]}],
        },
        "bad_anchor": {**good, "anchors": [{"name": "player"}]},
        "bad_wheel": {**good, "wheels": [{"object": 3}]},
        "not_a_dict": [1, 2],
    }
    for name, content in variants.items():
        (folders / name / "export").mkdir(parents=True)
        text = content if isinstance(content, str) else json.dumps(content)
        (folders / name / "export" / "manifest.json").write_text(text)
    (folders / "no_manifest").mkdir()
    assert list(manifests_in(sorted(folders.iterdir()))) == ["MOD/vox/red_car.vox"]


def test_unreadable_files_are_findings(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    (folder / "prefab" / "encoding.xml").write_text(
        '<?xml version="1.0" encoding="foo-bar"?><prefab/>'
    )
    (folder / "prefab" / "folder.xml").mkdir()
    edit_prefab(
        folder,
        'file="MOD/vox/red_car.vox" object="wheel_br"',
        'file="MOD/../outside.vox" object="wheel_br"',
    )
    found = validate_mod(folder, manifests)
    errors = messages(found, "error")
    assert any(m.startswith("prefab/encoding.xml: cannot read this XML file") for m in errors)
    assert not any("folder.xml" in m for m in messages(found))
    assert any("MOD/../outside.vox points outside the mod folder" in m for m in errors)
    (folder / "spawn.txt").write_text("../escape.xml : A/B\n")
    assert "spawn.txt: line 1: '../escape.xml' not found (paths start at the mod folder)" in (
        messages(validate_mod(folder, manifests), "error")
    )


def test_byte_order_marks(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    (folder / "info.txt").write_bytes(b"\xef\xbb\xbf" + INFO.encode())
    (folder / "spawn.txt").write_bytes(b"\xef\xbb\xbf" + SPAWN.encode())
    found = validate_mod(folder, manifests)
    assert messages(found, "error") == []
    assert [f.file for f in found] == ["info.txt", "spawn.txt"]
    assert all("byte order mark" in f.message for f in found)


def test_official_usages_are_notes(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    (folder / "info.txt").write_text("name = x\nauthor = a\ndescription = d\ntags = Map gameplay\n")
    assert validate_mod(folder, manifests) == []
    (folder / "info.txt").write_text("name = x\nauthor = a\ndescription = d\n")
    (folder / "spawn.txt").unlink()
    (folder / "main.lua").write_text("#version 2\n")
    found = validate_mod(folder, manifests)
    assert [f.level for f in found] == ["info"]
    assert found[0].message.startswith("no tags")
    edit_prefab(folder, "<body", '<instance file="MOD/x.xml" /><body')
    (folder / "x.xml").write_text("<prefab/>")
    notes = messages(validate_mod(folder, manifests), "info")
    assert any("built from <instance> elements" in m for m in notes)


def test_zero_rotation_is_compared(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    edit_prefab(folder, '<vox pos="0 0.3 0"', '<vox rot="0 0 0" pos="0 0.4 0"')
    found = messages(validate_mod(folder, manifests), "warning")
    assert any("pos 0 0.4 0 differs" in m for m in found)


def test_wheel_vox_and_body_locations_are_compared(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    edit_prefab(
        folder,
        '<vox pos="0 -0.4 0" file="MOD/vox/red_car.vox" object="wheel_fl"',
        '<vox pos="0 -0.3 0" file="MOD/vox/red_car.vox" object="wheel_fl"',
    )
    edit_prefab(
        folder,
        '<body dynamic="true">',
        '<body dynamic="true"><location tags="exhaust" pos="0.5 0.4 2" />'
        '<location tags="vital" pos="0 0 0" />',
    )
    found = messages(validate_mod(folder, manifests), "warning")
    assert len(found) == 2, found
    assert any('<vox object="wheel_fl"' in m and "wheel vox pos = 0 -0.4 0" in m for m in found)
    assert any('<location tags="vital">' in m and "anchor = 0 0.6 -1.5" in m for m in found)


def test_stale_vox_is_reported_once(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    stale = json.loads(json.dumps(manifests["MOD/vox/red_car.vox"]))
    stale["objects"][0]["size_vox"] = [16, 7, 40]
    found = messages(validate_mod(folder, {"MOD/vox/red_car.vox": stale}), "warning")
    assert len(found) == 1, found
    assert "does not match the manifest of project 'red_car'" in found[0]


def test_root_element_and_clean_report(mod: tuple[Path, dict[str, Any]]) -> None:
    folder, manifests = mod
    prefab(folder).write_text("<group><body/></group>")
    found = messages(validate_mod(folder, manifests), "warning")
    assert found == ["prefab/red_car.xml: root element is <group>, official prefabs use <prefab>"]
