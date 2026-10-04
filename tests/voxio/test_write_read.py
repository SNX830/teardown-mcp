"""Writer output, read back with our reader, and checked against the official layout."""

import struct
from pathlib import Path

import numpy as np
import pytest

from buildup.palette import Finish, Material, Palette, palette_row_names
from buildup.voxio import (
    InvalidObjectNameError,
    UndefinedPaletteIndexError,
    VoxFormatError,
    VoxObject,
    encode_vox,
    objects_from_document,
    read_vox,
    write_vox,
)


def _scene() -> tuple[list[VoxObject], Palette]:
    palette = Palette()
    metal = palette.index_for(Material.WEAK_METAL, (200, 40, 40), Finish.metal())
    glass = palette.index_for(Material.GLASS, (120, 150, 170))
    lamp = palette.index_for(Material.HARD_METAL, (255, 240, 200), Finish.emissive(power=3))

    body = np.zeros((5, 3, 7), dtype=np.uint8)
    body[:, 0, :] = metal
    body[1:4, 1, 2:5] = glass
    body[2, 2, 0] = lamp
    wheel = np.full((1, 4, 4), metal, dtype=np.uint8)
    objects = [VoxObject("body", body, (0, 1, 0)), VoxObject("wheel_fl", wheel, (-1, 0, -3))]
    return objects, palette


def _chunk_ids(data: bytes) -> list[str]:
    ids: list[str] = []
    pos = 20
    while pos < len(data):
        ids.append(data[pos : pos + 4].decode())
        content, children = struct.unpack_from("<ii", data, pos + 4)
        pos += 12 + content + children
    return ids


def test_round_trip_preserves_objects(tmp_path: Path) -> None:
    objects, palette = _scene()
    path = tmp_path / "sub" / "car.vox"
    write_vox(path, objects, palette)
    restored = objects_from_document(read_vox(path))
    assert [o.name for o in restored] == ["body", "wheel_fl"]
    for original, copy in zip(objects, restored, strict=True):
        assert copy.origin == original.origin
        assert np.array_equal(copy.grid, original.grid)


def test_header_and_chunk_order_match_official_files() -> None:
    objects, palette = _scene()
    data = encode_vox(objects, palette)
    assert data[:4] == b"VOX "
    assert struct.unpack_from("<i", data, 4)[0] == 150
    assert data[8:12] == b"MAIN"
    content, children = struct.unpack_from("<ii", data, 12)
    assert content == 0
    assert 20 + children == len(data)
    ids = _chunk_ids(data)
    expected_scene = ["nTRN", "nGRP", "nTRN", "nSHP", "nTRN", "nSHP"]
    assert ids[:4] == ["SIZE", "XYZI", "SIZE", "XYZI"]
    assert ids[4:10] == expected_scene
    assert ids[10:18] == ["LAYR"] * 8
    assert ids[18] == "RGBA"
    assert ids[19:275] == ["MATL"] * 256
    assert ids[275:] == ["NOTE"]


def test_palette_materials_and_notes_are_written() -> None:
    objects, palette = _scene()
    document = read_vox(encode_vox(objects, palette))
    assert document.version == 150
    assert document.palette is not None
    assert np.array_equal(document.palette[1:], palette.rgba()[1:])
    assert document.notes == palette_row_names()
    assert sorted(document.materials) == list(range(1, 257))
    for index, entry in palette.entries.items():
        assert document.materials[index] == entry.finish.to_matl()
    assert document.materials[256]["_type"] == "_diffuse"


def test_instances_are_named_and_unrotated() -> None:
    objects, palette = _scene()
    document = read_vox(encode_vox(objects, palette))
    assert [(i.name, i.model_index, i.layer, i.hidden) for i in document.instances] == [
        ("body", 0, 0, False),
        ("wheel_fl", 1, 0, False),
    ]
    assert all(i.rotation == ((1, 0, 0), (0, 1, 0), (0, 0, 1)) for i in document.instances)


def test_rejects_duplicate_names() -> None:
    objects, palette = _scene()
    with pytest.raises(VoxFormatError, match="duplicate object names: body"):
        encode_vox([objects[0], objects[0]], palette)


def test_rejects_empty_scene_and_empty_object() -> None:
    _, palette = _scene()
    with pytest.raises(VoxFormatError, match="no objects"):
        encode_vox([], palette)
    with pytest.raises(VoxFormatError, match="empty"):
        encode_vox([VoxObject("void", np.zeros((2, 2, 2), dtype=np.uint8))], palette)


def test_rejects_undefined_palette_indices() -> None:
    _, palette = _scene()
    grid = np.full((1, 1, 1), 60, dtype=np.uint8)
    with pytest.raises(UndefinedPaletteIndexError, match=r"\[60\]"):
        encode_vox([VoxObject("block", grid)], palette)


@pytest.mark.parametrize(
    "name",
    ["", " lead", "trail ", "double  space", "é", "a/b", "door: left", "x" * 65, "abc\n", "a\nb"],
)
def test_object_rejects_invalid_names(name: str) -> None:
    with pytest.raises(InvalidObjectNameError, match="invalid object name"):
        VoxObject(name, np.ones((1, 1, 1), dtype=np.uint8))


@pytest.mark.parametrize("name", ["window 1", "wheel_fl", "chassis_r4-1", "a.b", "x" * 64])
def test_object_accepts_valid_names(name: str) -> None:
    assert VoxObject(name, np.ones((1, 1, 1), dtype=np.uint8)).name == name


def test_object_rejects_bad_grids() -> None:
    with pytest.raises(ValueError, match="uint8"):
        VoxObject("a", np.ones((1, 1, 1), dtype=np.int32))
    with pytest.raises(ValueError, match="uint8"):
        VoxObject("a", np.ones((1, 1), dtype=np.uint8))
    with pytest.raises(ValueError, match="exceeds"):
        VoxObject("a", np.ones((257, 1, 1), dtype=np.uint8))


def test_largest_model_round_trips() -> None:
    palette = Palette()
    index = palette.index_for(Material.CONCRETE, (100, 100, 100))
    grid = np.zeros((256, 1, 256), dtype=np.uint8)
    grid[0, 0, 0] = grid[255, 0, 255] = index
    restored = objects_from_document(read_vox(encode_vox([VoxObject("slab", grid)], palette)))
    assert np.array_equal(restored[0].grid, grid)
    assert restored[0].size == (256, 1, 256)
