"""Vehicle templates must build complete, coherent vehicles at every allowed size."""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from buildup.project import Project, ProjectError, build_assembly, export_project
from buildup.project.templates import DESIGNS, MAX_SCALE_CHANGE, apply_template, template_names
from buildup.teardown import check_assembly
from buildup.teardown.anchors import rig_points
from buildup.teardown.validate import manifests_in, validate_mod
from buildup.voxcore import components

SEATED_ANCHORS = {
    "player",
    "vital",
    "exhaust",
    "driver_seat",
    "passenger_seat",
    "headlight_l",
    "headlight_r",
    "taillight_l",
    "taillight_r",
}


def _build(name: str, length_m: float | None = None, width_m: float | None = None) -> Project:
    project = Project(name, "vehicle")
    apply_template(project, name, length_m=length_m, width_m=width_m)
    return project


def _problems(project: Project) -> list[str]:
    """Export warnings, loose pieces, and rig feet inside a seat (legs through the seats)."""
    assembly, notes = build_assembly(project)
    problems = notes + check_assembly(assembly)
    body = project.parts["body"]
    assert body.grid is not None
    if len(components(body.grid)) != 1:
        problems.append("body in several pieces")
    seat = project.colors["seat"].index
    for name, point in project.anchors.items():
        if "seat" not in name:
            continue
        for foot in ("ik_foot_l", "ik_foot_r"):
            x, y, z = (math.floor(v) for v in rig_points(point, driver=True)[foot])
            local = (x - body.origin[0], y - body.origin[1], z - body.origin[2])
            inside = all(0 <= local[i] < body.grid.shape[i] for i in range(3))
            if inside and body.grid[local] == seat:
                problems.append(f"{name}: {foot} inside a seat")
    return problems


@pytest.mark.parametrize("name", template_names())
def test_template_is_a_complete_vehicle_without_warnings(name: str) -> None:
    project = _build(name)
    assert _problems(project) == []
    body = project.parts["body"]
    assert body.grid is not None
    assert len(components(body.grid)) == 1
    assert set(project.anchors) >= SEATED_ANCHORS
    wheels = [p for p in project.parts.values() if p.role == "wheel"]
    assert len(wheels) == 2 * len(DESIGNS[name].axles)
    used = {int(i) for i in set(body.grid.flatten()) if i}
    assert {project.colors[c].index for c in ("paint", "glass", "headlight", "taillight")} <= used
    glass, lamp = project.colors["glass"].index, project.colors["headlight"].index
    assert glass in project.palette().see_through()
    assert lamp not in project.palette().see_through()


def _even_sizes(design_size: int) -> list[int]:
    low = 2 * math.ceil(design_size * (1 - MAX_SCALE_CHANGE) / 2)
    high = 2 * math.floor(design_size * (1 + MAX_SCALE_CHANGE) / 2)
    return list(range(low, high + 1, 2))


@pytest.mark.parametrize("name", template_names())
def test_every_allowed_length_stays_coherent(name: str) -> None:
    design = DESIGNS[name]
    widths = _even_sizes(design.width)
    for length in _even_sizes(design.length):
        for width in (widths[0], design.width, widths[-1]):
            project = _build(name, length_m=length / 10, width_m=width / 10)
            assert _problems(project) == [], (length, width)


@pytest.mark.parametrize("name", template_names())
def test_every_allowed_width_stays_coherent(name: str) -> None:
    design = DESIGNS[name]
    for width in _even_sizes(design.width):
        assert _problems(_build(name, width_m=width / 10)) == [], width


def test_requested_size_and_paint() -> None:
    project = Project("car", "vehicle")
    lines = apply_template(project, "sedan", length_m=4.0, width_m=1.8, paint_rgb=(10, 20, 30))
    bounds = project.parts["body"].bounds()
    assert bounds is not None
    (x0, _, z0), (x1, _, z1) = bounds
    assert (x1 - x0, z1 - z0) == (18, 40 + 1)  # the exhaust pipe sticks out 1 voxel at the back
    assert project.colors["paint"].rgb == (10, 20, 30)
    assert lines[0].startswith("Built template 'sedan'")
    assert any("driver_seat" in line for line in lines)


@pytest.mark.parametrize("name", template_names())
def test_exported_template_passes_validation(name: str, tmp_path: Path) -> None:
    project = _build(name)
    folder = tmp_path / "projects" / name
    result = export_project(
        project, project_folder=folder, mods_dir=tmp_path / "mods", mod_name="Test Car"
    )
    assert result.warnings == []
    root = ET.fromstring(result.skeleton)
    rigs = root.findall("./group/vehicle/body/rig")
    assert rigs[0].get("tags") == "driver sort=0"
    assert len(root.findall(".//light")) == 4
    mod = result.mod_folder
    info = "name = Test Car\nauthor = Buildup tests\ndescription = test\ntags = Vehicle\n"
    (mod / "info.txt").write_text(info)
    (mod / "spawn.txt").write_text(f"prefab/{name}.xml : Vehicle/Test Car\n")
    findings = validate_mod(mod, manifests_in([folder]))
    assert [f for f in findings if f.level != "info"] == []


def test_template_errors() -> None:
    prop = Project("crate", "prop")
    with pytest.raises(ProjectError, match="kind 'vehicle'"):
        apply_template(prop, "sedan")
    used = Project("car", "vehicle")
    used.add_part("body")
    with pytest.raises(ProjectError, match="empty project"):
        apply_template(used, "sedan")
    with pytest.raises(ProjectError, match="unknown template 'tank'"):
        apply_template(Project("car", "vehicle"), "tank")
    with pytest.raises(ProjectError, match="length_m must be within 20%"):
        apply_template(Project("car", "vehicle"), "sedan", length_m=6.0)
    with pytest.raises(ProjectError, match="width_m"):
        apply_template(Project("car", "vehicle"), "sedan", width_m=1.0)
    clash = Project("car", "vehicle")
    clash.define_color("trim", "wood", (1, 2, 3))
    with pytest.raises(ProjectError, match="color 'trim' is wood"):
        apply_template(clash, "sedan")
