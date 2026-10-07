import json

import numpy as np
import pytest

from buildup.palette import Finish, Material, Palette
from buildup.teardown import (
    MANIFEST_VERSION,
    TOPICS,
    Assembly,
    AssemblyError,
    PlacedObject,
    Wheel,
    build_manifest,
    check_assembly,
    reference,
)
from buildup.teardown.reference import _materials_text


def _solid(size: tuple[int, int, int], index: int) -> np.ndarray:
    return np.full(size, index, dtype=np.uint8)


@pytest.fixture
def palette() -> Palette:
    palette = Palette()
    assert palette.index_for(Material.WEAK_METAL, (200, 0, 0)) == 121
    assert palette.index_for(Material.GLASS, (100, 150, 200)) == 1
    assert palette.index_for(Material.PLASTIC, (20, 20, 20), Finish.matte()) == 153
    return palette


def _car(palette: Palette, anchors: dict[str, tuple[float, float, float]]) -> Assembly:
    body_grid = _solid((16, 6, 40), 121)
    body_grid[:, 5, :4] = 1
    body = PlacedObject("body", body_grid, (-8, 3, -20))
    wheels = tuple(
        Wheel(
            name,
            PlacedObject(f"wheel_{name}", _solid((2, 8, 8), 153), (x0, 0, z - 4)),
            (x0 + 1.0, 4.0, float(z)),
            steer=z < 0,
            drive=z > 0,
        )
        for name, x0, z in (("fl", -10, -13), ("fr", 8, -13), ("bl", -10, 13), ("br", 8, 13))
    )
    return Assembly("car", "vehicle", (body,), wheels, anchors, palette, {121: "paint", 1: "glass"})


FULL_ANCHORS = {"player": (-4.0, 9.0, 2.0), "vital": (0.0, 6.0, -15.0), "exhaust": (5.0, 4.0, 20.0)}


def test_placed_object_geometry(palette: Palette) -> None:
    obj = PlacedObject("body", _solid((16, 6, 40), 121), (-8, 3, -20))
    assert obj.size == (16, 6, 40)
    assert obj.end == (8, 9, 20)
    assert obj.vox_pos == (0, 3, 0)


def test_placed_object_rejects_empty_and_oversized() -> None:
    with pytest.raises(AssemblyError, match="empty"):
        PlacedObject("x", np.zeros((2, 2, 2), np.uint8), (0, 0, 0))
    with pytest.raises(AssemblyError, match="larger"):
        PlacedObject("x", np.ones((257, 1, 1), np.uint8), (0, 0, 0))


def test_complete_car_has_no_warnings(palette: Palette) -> None:
    assert check_assembly(_car(palette, FULL_ANCHORS)) == []


def test_missing_locations_are_reported(palette: Palette) -> None:
    warnings = check_assembly(_car(palette, {"player": (-4.0, 9.0, 2.0), "lamp": (0, 0, 0)}))
    assert len(warnings) == 1
    assert "missing vehicle anchors: vital, exhaust" in warnings[0]


def test_overlaps_and_loose_pieces_are_reported(palette: Palette) -> None:
    car = _car(palette, FULL_ANCHORS)
    loose = _solid((3, 3, 3), 121)
    loose[1, 1, 1] = 0
    loose[0, 0, 0] = 0
    loose[:, :, 1] = 0  # two slabs, z = 0 and z = 2, not touching
    # Overlap with the body (y 3..9): rows y 7, 8 x 3 columns x slabs z 0, 2, minus (0, 0, 0).
    extra = PlacedObject("roof", loose, (-1, 7, 0))
    warnings = check_assembly(
        Assembly(car.name, car.kind, (*car.body, extra), car.wheels, car.anchors, palette, {})
    )
    assert any("'body' and 'roof' share 11 voxel positions" in w for w in warnings)
    assert any("'roof' is made of 2 separate pieces" in w for w in warnings)


def test_wheel_overlapping_the_body_is_reported(palette: Palette) -> None:
    car = _car(palette, FULL_ANCHORS)
    sunk = car.wheels[0]
    moved = Wheel(
        sunk.name,
        PlacedObject(sunk.obj.name, sunk.obj.grid, (-9, 0, -17)),
        (-8.0, 4.0, -13.0),
        sunk.steer,
        sunk.drive,
    )
    assembly = Assembly(
        "car", "vehicle", car.body, (moved, *car.wheels[1:]), car.anchors, palette, {}
    )
    assert any("'body' and 'wheel_fl'" in w for w in check_assembly(assembly))


@pytest.mark.parametrize(
    ("kind", "body", "wheels", "message"),
    [
        ("vehicle", False, True, "no body part"),
        ("vehicle", True, False, "needs wheels"),
        ("prop", True, True, "cannot have wheels"),
    ],
)
def test_impossible_exports(
    palette: Palette, kind: str, body: bool, wheels: bool, message: str
) -> None:
    car = _car(palette, FULL_ANCHORS)
    assembly = Assembly(
        "x",
        "vehicle" if kind == "vehicle" else "prop",
        car.body if body else (),
        car.wheels if wheels else (),
        {},
        palette,
        {},
    )
    with pytest.raises(AssemblyError, match=message):
        check_assembly(assembly)


def test_manifest(palette: Palette) -> None:
    manifest = build_manifest(_car(palette, {**FULL_ANCHORS, "lamp": (3, 8, -20)}), "test 1.0")
    json.dumps(manifest)  # JSON-ready
    assert manifest["manifest_version"] == MANIFEST_VERSION == 1
    assert manifest["generator"] == "test 1.0"
    assert manifest["vox_file"] == "MOD/vox/car.vox"
    body = manifest["objects"][0]
    assert body == {
        "name": "body",
        "role": "body",
        "size_vox": [16, 6, 40],
        "size_m": [1.6, 0.6, 4.0],
        "min_corner_vox": [-8, 3, -20],
        "max_corner_vox": [8, 9, 20],
        "vox_pos_vox": [0, 3, 0],
        "vox_pos_m": [0.0, 0.3, 0.0],
        "voxels": 16 * 6 * 40,
        "materials": ["glass", "weak metal"],
        "palette_indices": [1, 121],
    }
    assert [o["role"] for o in manifest["objects"]] == ["body"] + ["wheel"] * 4
    fl = manifest["wheels"][0]
    assert fl == {
        "name": "fl",
        "object": "wheel_fl",
        "axle_vox": [-9.0, 4.0, -13.0],
        "axle_m": [-0.9, 0.4, -1.3],
        "diameter_m": 0.8,
        "width_m": 0.2,
        "steer": True,
        "drive": False,
        "vox_pos_in_wheel_m": [0.0, -0.4, 0.0],
    }
    anchors = {a["name"]: a for a in manifest["anchors"]}
    assert anchors["player"]["location_tag"] == "player"
    assert anchors["lamp"]["location_tag"] is None
    assert anchors["lamp"]["position_m"] == [0.3, 0.8, -2.0]
    assert manifest["palette"][0] == {
        "index": 1,
        "name": "glass",
        "material": "glass",
        "rgb": [100, 150, 200],
        "finish": "glass",
    }
    assert manifest["palette"][2]["name"] is None  # plastic has no color name here
    assert manifest["material_index_ranges"]["weak metal"] == [121, 136]


def test_prop_anchors_are_not_locations(palette: Palette) -> None:
    crate = PlacedObject("crate", _solid((4, 4, 4), 121), (-2, 0, -2))
    prop = Assembly("crate", "prop", (crate,), (), {"player": (0, 5, 0)}, palette, {})
    assert check_assembly(prop) == []  # props need no vehicle locations
    (anchor,) = build_manifest(prop, "test")["anchors"]
    assert anchor["location_tag"] is None


def test_reference_topics() -> None:
    for topic, body in TOPICS.items():
        assert reference(topic) == body
        assert len(body) > 200
    with pytest.raises(KeyError, match="unknown topic 'xml'"):
        reference("xml")


def test_materials_reference_lists_every_material() -> None:
    text = _materials_text()
    for material in Material:
        assert material.value in text
    assert "weak metal    indices 121-136 (16 colors)" in text
