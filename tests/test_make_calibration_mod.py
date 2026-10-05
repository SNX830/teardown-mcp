"""Tests of scripts/make_calibration_mod.py (the 0.2.0 calibration mod)."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

import make_calibration_mod as cal
from buildup.palette import Material, material_of_index
from buildup.voxio import VoxObject, objects_from_document, read_vox

VOXEL_M = 0.1


@pytest.fixture(scope="module")
def mod_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("mod") / "BuildupCalibration"
    cal.build_mod(output)
    return output


@pytest.fixture(scope="module")
def objects(mod_dir: Path) -> dict[str, VoxObject]:
    read = objects_from_document(read_vox(mod_dir / cal.VOX_PATH))
    return {obj.name: obj for obj in read}


def _vec(text: str) -> tuple[float, ...]:
    return tuple(float(v) for v in text.split())


def test_files_written(mod_dir: Path) -> None:
    expected = {
        "info.txt",
        "spawn.txt",
        "prefab/prop.xml",
        "prefab/car.xml",
        "script/prop.lua",
        "script/car.lua",
        "vox/calibration.vox",
    }
    found = {p.relative_to(mod_dir).as_posix() for p in mod_dir.rglob("*") if p.is_file()}
    assert found == expected


def test_info_txt_uses_documented_keys(mod_dir: Path) -> None:
    keys = {
        line.split("=")[0].strip()
        for line in (mod_dir / "info.txt").read_text(encoding="utf-8").splitlines()
    }
    assert keys == {"name", "author", "description", "tags"}


def test_spawn_txt_points_to_existing_prefabs(mod_dir: Path) -> None:
    lines = (mod_dir / "spawn.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        path, name = (part.strip() for part in line.split(":"))
        assert (mod_dir / path).is_file()
        assert re.fullmatch(r"[A-Za-z0-9 ]+/[A-Za-z0-9 ]+", name)


@pytest.mark.parametrize("prefab", ["prefab/prop.xml", "prefab/car.xml"])
def test_xml_references_exist(mod_dir: Path, objects: dict[str, VoxObject], prefab: str) -> None:
    root = ET.parse(mod_dir / prefab).getroot()
    assert root.tag == "prefab"
    vox_elements = list(root.iter("vox"))
    assert vox_elements
    for element in vox_elements:
        assert element.get("file") == "MOD/vox/calibration.vox"
        assert element.get("object") in objects
    for script in root.iter("script"):
        file = script.get("file")
        assert file is not None
        assert file.startswith("MOD/")
        assert (mod_dir / file.removeprefix("MOD/")).is_file()


def test_tags_in_xml_match_probe_scripts(mod_dir: Path) -> None:
    prop = ET.parse(mod_dir / "prefab/prop.xml").getroot()
    car = ET.parse(mod_dir / "prefab/car.xml").getroot()
    prop_lua = (mod_dir / "script/prop.lua").read_text(encoding="utf-8")
    car_lua = (mod_dir / "script/car.lua").read_text(encoding="utf-8")
    for element in prop.iter("vox"):
        assert f'tag = "{element.get("tags")}"' in prop_lua
    for element in car.iter("vox"):
        assert f'"{element.get("tags")}"' in car_lua
    vehicle = car.find(".//vehicle")
    assert vehicle is not None
    assert f'"{vehicle.get("tags")}"' in car_lua


def test_lua_templates_fully_substituted(mod_dir: Path) -> None:
    for name in ("prop.lua", "car.lua"):
        text = (mod_dir / "script" / name).read_text(encoding="utf-8")
        assert text.startswith("#version 2\n")
        code = "\n".join(line.split("--")[0] for line in text.splitlines())
        assert "$" not in code
        assert cal.CALIBRATION_VERSION in text


def test_prop_markers(objects: dict[str, VoxObject]) -> None:
    _, colors = cal.make_palette()
    marker_entries = set(colors.marker.values())
    assert len(marker_entries) == 4
    assert colors.prop_base not in marker_entries
    for name, size in (("cal_odd", cal.ODD_SIZE), ("cal_even", cal.EVEN_SIZE)):
        grid = objects[name].grid
        assert grid.shape == size
        for marker, cell in cal.marker_cells(size).items():
            assert grid[cell] == colors.marker[marker]
        # Each marker appears exactly once: a probe hit is unambiguous.
        for entry in marker_entries:
            assert np.count_nonzero(grid == entry) == 1


def test_prop_sizes_distinguish_axes_and_parity() -> None:
    assert len(set(cal.ODD_SIZE)) == 3
    assert len(set(cal.EVEN_SIZE)) == 3
    assert all(s % 2 == 1 for s in cal.ODD_SIZE)
    assert all(s % 2 == 0 for s in cal.EVEN_SIZE)


def _rotation(axis: int, degrees: float) -> np.ndarray:
    """Right-handed rotation matrix about X (0), Y (1) or Z (2)."""
    c, s = round(np.cos(np.radians(degrees))), round(np.sin(np.radians(degrees)))
    i, j = [a for a in range(3) if a != axis]
    matrix = np.eye(3)
    matrix[i, i], matrix[i, j], matrix[j, i], matrix[j, j] = c, -s, s, c
    if axis == 1:  # about Y the right-handed signs are swapped (z x x = y)
        matrix[i, j], matrix[j, i] = s, -s
    return matrix


# XML rot "x y z" in degrees: the order of the three turns is under test, so check both orders.
EULER_ORDERS = {
    "x, then z, then y": lambda r: _rotation(1, r[1]) @ _rotation(2, r[2]) @ _rotation(0, r[0]),
    "z, then y, then x": lambda r: _rotation(0, r[0]) @ _rotation(1, r[1]) @ _rotation(2, r[2]),
}


def _boxes_m(mod_dir: Path, order: str) -> list[tuple[np.ndarray, np.ndarray]]:
    """Body-frame boxes of the prop blocks, assuming bottom-center origins (under test)."""
    sizes = {"cal_odd": cal.ODD_SIZE, "cal_even": cal.EVEN_SIZE}
    boxes = []
    for element in ET.parse(mod_dir / "prefab/prop.xml").getroot().iter("vox"):
        sx, sy, sz = np.array(sizes[element.get("object", "")]) * VOXEL_M
        corners = np.array(
            [[x, y, z] for x in (-sx / 2, sx / 2) for y in (0, sy) for z in (-sz / 2, sz / 2)]
        )
        rotation = EULER_ORDERS[order](_vec(element.get("rot", "")))
        placed = corners @ rotation.T + np.array(_vec(element.get("pos", "")))
        boxes.append((placed.min(axis=0), placed.max(axis=0)))
    return boxes


def test_rotation_helper() -> None:
    assert _rotation(1, 90) @ np.array([1, 0, 0]) == pytest.approx([0, 0, -1])
    assert _rotation(0, 90) @ np.array([0, 1, 0]) == pytest.approx([0, 0, 1])
    assert _rotation(2, 90) @ np.array([1, 0, 0]) == pytest.approx([0, 1, 0])


@pytest.mark.parametrize("order", list(EULER_ORDERS))
def test_prop_blocks_do_not_overlap(mod_dir: Path, order: str) -> None:
    boxes = _boxes_m(mod_dir, order)
    assert len(boxes) == len(cal.PROP_ELEMENTS)
    margin = VOXEL_M  # stays apart even if the half-voxel rule differs from our guess
    for i, (low_a, high_a) in enumerate(boxes):
        assert low_a[1] >= 0  # nothing below the body origin
        for low_b, high_b in boxes[i + 1 :]:
            separated = (high_a + margin <= low_b) | (high_b + margin <= low_a)
            assert separated.any()


def test_car_body_markers(objects: dict[str, VoxObject]) -> None:
    _, colors = cal.make_palette()
    grid = objects["car_body"].grid
    assert grid.shape == cal.BODY_SIZE
    sx, _, sz = cal.BODY_SIZE
    front = grid[:, :, 0]
    rear = grid[:, :, sz - 1]
    assert np.count_nonzero(front == colors.front_light) == 12
    assert np.count_nonzero(rear == colors.rear_light) == 12
    assert not np.any(grid[:, :, 1 : sz - 1] == colors.front_light)
    assert np.all(grid[sx - 1, 4, :] == colors.right_stripe)
    assert not np.any(grid[: sx - 1] == colors.right_stripe)
    assert material_of_index(colors.front_light) is Material.HARD_METAL
    assert material_of_index(colors.body) is Material.WEAK_METAL


def test_wheel_disc_is_centered_on_axle(objects: dict[str, VoxObject]) -> None:
    for wheel in cal.WHEELS:
        grid = objects[wheel.object_name].grid
        assert grid.shape == (cal.WHEEL_WIDTH, cal.WHEEL_DIAMETER, cal.WHEEL_DIAMETER)
        filled = grid > 0
        # Symmetric in y and z: the bounding-box center is the axle (used by the car probe).
        assert np.array_equal(filled, filled[:, ::-1, :])
        assert np.array_equal(filled, filled[:, :, ::-1])
        assert filled[:, 0, :].any()
        assert filled[:, -1, :].any()
        assert filled[:, :, 0].any()


def test_car_wheels_touch_ground_and_clear_body(mod_dir: Path) -> None:
    body = ET.parse(mod_dir / "prefab/car.xml").getroot().find(".//vehicle/body")
    assert body is not None
    body_vox = body.find("vox")
    assert body_vox is not None
    body_y = _vec(body_vox.get("pos", ""))[1]
    half_width = cal.BODY_SIZE[0] * VOXEL_M / 2
    wheels = body.findall("wheel")
    assert {w.get("name") for w in wheels} == {"fl", "fr", "bl", "br"}
    for wheel in wheels:
        center = _vec(wheel.get("pos", ""))
        vox = wheel.find("vox")
        assert vox is not None
        bottom = center[1] + _vec(vox.get("pos", ""))[1]  # bottom-center origin
        assert bottom == pytest.approx(0.0)
        assert center[1] == pytest.approx(cal.WHEEL_DIAMETER * VOXEL_M / 2)
        inner = abs(center[0]) - cal.WHEEL_WIDTH * VOXEL_M / 2
        assert inner >= half_width + VOXEL_M - 1e-9
        assert body_y > 0
        front = center[2] < 0
        assert (wheel.get("steer") == "1") is front
        assert (wheel.get("drive") == "1") is not front


def test_car_locations(mod_dir: Path) -> None:
    root = ET.parse(mod_dir / "prefab/car.xml").getroot()
    tags = {loc.get("tags") for loc in root.iter("location")}
    assert tags == {"player", "vital", "exhaust"}
    for location in root.iter("location"):
        tag = location.get("tags", "")
        body_frame = np.array(_vec(location.get("pos", ""))) + np.array(cal.BODY_VOX_POS) * VOXEL_M
        assert body_frame == pytest.approx(np.array(cal.LOCATIONS[tag]) * VOXEL_M)
    assert cal.LOCATIONS["player"][0] < 0  # driver on the left
    assert cal.LOCATIONS["exhaust"][2] > cal.BODY_SIZE[2] / 2  # behind the rear face


@pytest.mark.parametrize(
    ("value", "text"), [(0, "0"), (-12, "-1.2"), (3, "0.3"), (15, "1.5"), (-4, "-0.4"), (10, "1")]
)
def test_meters(value: int, text: str) -> None:
    assert cal.meters(value) == text
