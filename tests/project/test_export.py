import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from buildup import __version__
from buildup.project import (
    Axle,
    Project,
    ProjectError,
    WheelLayout,
    box_shape,
    build_assembly,
    export_project,
)
from buildup.teardown import AssemblyError
from buildup.voxio import objects_from_document, read_vox


@pytest.fixture
def car() -> Project:
    p = Project("red_car", "vehicle")
    p.define_color("paint", "weak metal", (200, 30, 30))
    p.define_color("window", "glass", (120, 170, 220))
    p.define_color("tire", "plastic", (20, 20, 20))
    p.add_part("body")
    p.draw("body", box_shape((-8, 3, -20), (8, 9, 20)), "add", "paint")
    p.draw("body", box_shape((-7, 9, -4), (7, 13, 8)), "add", "window")
    p.add_wheels([Axle(-13, steer=True), Axle(13, drive=True)], WheelLayout(8, 2, 8), "tire")
    for name, point in {"player": (-4, 9, 2), "vital": (0, 6, -15), "exhaust": (5, 4, 20)}.items():
        p.set_anchor(name, point)
    return p


def test_export_writes_a_mod_folder(car: Project, tmp_path: Path) -> None:
    result = export_project(
        car,
        project_folder=tmp_path / "projects" / "red_car",
        mods_dir=tmp_path / "mods",
        mod_name="Red Car",
    )
    mod = tmp_path / "mods" / "Red Car"
    assert result.mod_folder == mod
    assert result.vox_path == mod / "vox" / "red_car.vox"
    assert result.prefab_path == mod / "prefab" / "red_car.xml"
    assert result.prefab_written
    assert result.warnings == []
    assert result.prefab_path.read_text(encoding="utf-8") == result.skeleton
    assert result.skeleton_path.read_text(encoding="utf-8") == result.skeleton
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest == result.manifest
    assert manifest["generator"] == f"buildup-mcp {__version__}"
    assert [o["name"] for o in manifest["objects"]] == [
        "body",
        "wheel_fl",
        "wheel_fr",
        "wheel_bl",
        "wheel_br",
    ]
    root = ET.fromstring(result.skeleton)
    assert root.find(".//vehicle/body/vox[@object='body']") is not None


def test_vox_file_holds_the_parts_as_modelled(car: Project, tmp_path: Path) -> None:
    result = export_project(
        car, project_folder=tmp_path / "p", mods_dir=tmp_path / "mods", mod_name="Red Car"
    )
    document = read_vox(result.vox_path)
    objects = {o.name: o for o in objects_from_document(document)}
    assert list(objects) == ["body", "wheel_fl", "wheel_fr", "wheel_bl", "wheel_br"]
    for name, obj in objects.items():
        part = car.parts[name]
        assert obj.origin == part.origin
        assert part.grid is not None
        assert np.array_equal(obj.grid, part.grid)
    # Palette: the colors of the project at their indices.
    assert document.palette is not None
    assert tuple(document.palette[121][:3]) == (200, 30, 30)
    assert tuple(document.palette[1][:3]) == (120, 170, 220)


def test_existing_prefab_is_kept_unless_overwrite(car: Project, tmp_path: Path) -> None:
    first = export_project(
        car, project_folder=tmp_path / "p", mods_dir=tmp_path / "m", mod_name="Red Car"
    )
    first.prefab_path.write_text("<prefab>edited by the AI</prefab>", encoding="utf-8")
    second = export_project(
        car, project_folder=tmp_path / "p", mods_dir=tmp_path / "m", mod_name="Red Car"
    )
    assert not second.prefab_written
    assert second.warnings == []  # the skeleton did not change
    assert "edited" in second.prefab_path.read_text(encoding="utf-8")

    car.move("body", (0, 1, 0))
    third = export_project(
        car, project_folder=tmp_path / "p", mods_dir=tmp_path / "m", mod_name="Red Car"
    )
    assert any("the skeleton changed since the last export" in w for w in third.warnings)
    assert "edited" in third.prefab_path.read_text(encoding="utf-8")

    fourth = export_project(
        car,
        project_folder=tmp_path / "p",
        mods_dir=tmp_path / "m",
        mod_name="Red Car",
        skeleton="overwrite",
    )
    assert fourth.prefab_written
    assert fourth.prefab_path.read_text(encoding="utf-8") == fourth.skeleton


def test_skeleton_never(car: Project, tmp_path: Path) -> None:
    result = export_project(
        car,
        project_folder=tmp_path / "p",
        mods_dir=tmp_path / "m",
        mod_name="Red Car",
        skeleton="never",
    )
    assert not result.prefab_written
    assert not result.prefab_path.exists()
    assert result.skeleton_path.exists()


def test_export_errors_and_notes(car: Project, tmp_path: Path) -> None:
    folders = {"project_folder": tmp_path / "p", "mods_dir": tmp_path / "m"}
    with pytest.raises(ProjectError, match="invalid mod name"):
        export_project(car, mod_name="red_car", **folders)
    with pytest.raises(ProjectError, match="skeleton must be one of"):
        export_project(car, mod_name="Red Car", skeleton="sometimes", **folders)
    car.add_part("spare")
    result = export_project(car, mod_name="Red Car", **folders)
    assert "part 'spare' is empty and was left out" in result.warnings
    car.draw("wheel_fl", box_shape((-20, -20, -20), (20, 20, 20)), "carve", None)
    with pytest.raises(AssemblyError, match="wheel part 'wheel_fl' is empty"):
        export_project(car, mod_name="Red Car", **folders)


def test_build_assembly_splits_body_and_wheels(car: Project) -> None:
    assembly, notes = build_assembly(car)
    assert notes == []
    assert [o.name for o in assembly.body] == ["body"]
    assert [w.name for w in assembly.wheels] == ["fl", "fr", "bl", "br"]
    assert assembly.color_names == {121: "paint", 1: "window", 153: "tire"}
    assert assembly.anchors["player"] == (-4.0, 9.0, 2.0)
