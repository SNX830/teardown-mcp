"""Reader tests on small hand-built files."""

import struct
from pathlib import Path

import numpy as np
import pytest

from buildup.voxio import (
    InvalidObjectNameError,
    TeardownCompressedError,
    UnsupportedRotationError,
    VoxFormatError,
    objects_from_document,
    read_vox,
    reader,
)
from buildup.voxio.rotation import IDENTITY_BYTE


def _string(text: str) -> bytes:
    raw = text.encode()
    return struct.pack("<i", len(raw)) + raw


def _dict(values: dict[str, str]) -> bytes:
    return struct.pack("<i", len(values)) + b"".join(
        _string(k) + _string(v) for k, v in values.items()
    )


def _chunk(chunk_id: str, content: bytes) -> bytes:
    return chunk_id.encode() + struct.pack("<ii", len(content), 0) + content


def _file(*chunks: bytes, version: int = 150) -> bytes:
    children = b"".join(chunks)
    return (
        b"VOX "
        + struct.pack("<i", version)
        + b"MAIN"
        + struct.pack("<ii", 0, len(children))
        + children
    )


def _model(size: tuple[int, int, int], voxels: list[tuple[int, int, int, int]]) -> bytes:
    xyzi = struct.pack("<i", len(voxels)) + b"".join(bytes(v) for v in voxels)
    return _chunk("SIZE", struct.pack("<iii", *size)) + _chunk("XYZI", xyzi)


def _trn(
    node: int, child: int, attrs: dict[str, str], frame: dict[str, str], layer: int = 0
) -> bytes:
    return _chunk(
        "nTRN",
        struct.pack("<i", node)
        + _dict(attrs)
        + struct.pack("<iiii", child, -1, layer, 1)
        + _dict(frame),
    )


def _grp(node: int, children: list[int]) -> bytes:
    return _chunk(
        "nGRP",
        struct.pack("<i", node)
        + _dict({})
        + struct.pack(f"<i{len(children)}i", len(children), *children),
    )


def _shp(node: int, model: int) -> bytes:
    return _chunk(
        "nSHP", struct.pack("<i", node) + _dict({}) + struct.pack("<ii", 1, model) + _dict({})
    )


def test_file_without_scene_graph_or_palette() -> None:
    document = read_vox(_file(_model((2, 1, 1), [(1, 0, 0, 7)])))
    assert document.palette is None
    assert len(document.instances) == 1
    assert document.instances[0].name is None
    grid = document.models[0]
    assert grid.shape == (2, 1, 1)
    assert grid[1, 0, 0] == 7
    assert grid[0, 0, 0] == 0
    assert objects_from_document(document) == []  # unnamed instances are skipped


def test_rgba_position_is_index_minus_one() -> None:
    colors = bytearray(256 * 4)
    colors[0:4] = bytes((1, 2, 3, 255))  # position 0 -> palette index 1
    document = read_vox(_file(_model((1, 1, 1), [(0, 0, 0, 1)]), _chunk("RGBA", bytes(colors))))
    assert document.palette is not None
    assert tuple(document.palette[1]) == (1, 2, 3, 255)
    assert tuple(document.palette[0]) == (0, 0, 0, 0)


def test_nested_groups_compose_transforms() -> None:
    # Two non-symmetric, non-commuting rotations, so that a transposed matrix or a swapped
    # multiplication order gives a different result. Expected values are written out by hand.
    outer = 17  # rows (0, -1, 0), (1, 0, 0), (0, 0, 1): quarter turn about Z
    inner = 40  # rows (1, 0, 0), (0, 0, -1), (0, 1, 0): quarter turn about X
    data = _file(
        _model((1, 1, 1), [(0, 0, 0, 1)]),
        _trn(0, 1, {}, {}, layer=-1),
        _grp(1, [2]),
        _trn(2, 3, {"_name": "outer"}, {"_t": "10 0 0", "_r": str(outer)}),
        _grp(3, [4]),
        _trn(4, 5, {"_name": "inner"}, {"_t": "1 2 3", "_r": str(inner)}, layer=1),
        _shp(5, 0),
        _chunk(
            "LAYR",
            struct.pack("<i", 1) + _dict({"_name": "1", "_hidden": "1"}) + struct.pack("<i", -1),
        ),
    )
    (instance,) = read_vox(data).instances
    assert instance.name == "inner"
    # world translation = R_outer @ (1, 2, 3) + (10, 0, 0) = (-2, 1, 3) + (10, 0, 0)
    assert instance.translation == (8, 1, 3)
    # world rotation = R_outer @ R_inner
    assert instance.rotation == ((0, 0, 1), (1, 0, 0), (0, 1, 0))
    assert instance.layer == 1
    assert instance.hidden  # its layer is hidden


def test_duplicate_children_in_one_group_are_visited_once() -> None:
    data = _file(
        _model((1, 1, 1), [(0, 0, 0, 1)]),
        _trn(0, 1, {}, {}, layer=-1),
        _grp(1, [2, 2, 2]),
        _trn(2, 3, {"_name": "once"}, {}),
        _shp(3, 0),
    )
    assert [i.name for i in read_vox(data).instances] == ["once"]


def test_shape_shared_by_two_transforms_gives_two_instances() -> None:
    # Official files share shape nodes between transforms (instancing).
    data = _file(
        _model((1, 1, 1), [(0, 0, 0, 1)]),
        _trn(0, 1, {}, {}, layer=-1),
        _grp(1, [2, 4]),
        _trn(2, 3, {"_name": "left"}, {"_t": "-5 0 0"}),
        _trn(4, 3, {"_name": "right"}, {"_t": "5 0 0"}),
        _shp(3, 0),
    )
    assert [(i.name, i.translation) for i in read_vox(data).instances] == [
        ("left", (-5, 0, 0)),
        ("right", (5, 0, 0)),
    ]


def test_exploding_scene_graph_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader, "_MAX_SCENE_VISITS", 20)
    # Level L: group 3L+1 holds two transforms (3L+2, 3L+3) that both point to the next group, so
    # every level doubles the number of paths (2**10 for 10 levels); the last level is a shape.
    chunks = [_model((1, 1, 1), [(0, 0, 0, 1)]), _trn(0, 1, {}, {}, layer=-1)]
    for level in range(10):
        group = 3 * level + 1
        chunks += [
            _grp(group, [group + 1, group + 2]),
            _trn(group + 1, group + 3, {}, {}),
            _trn(group + 2, group + 3, {}, {}),
        ]
    chunks.append(_shp(31, 0))
    with pytest.raises(VoxFormatError, match="too large"):
        read_vox(_file(*chunks))


def test_read_from_a_bytearray() -> None:
    assert read_vox(bytearray(_file(_model((1, 1, 1), [(0, 0, 0, 4)])))).models[0][0, 0, 0] == 4


def test_read_from_a_string_path(tmp_path: Path) -> None:
    path = tmp_path / "a.vox"
    path.write_bytes(_file(_model((1, 1, 1), [(0, 0, 0, 2)])))
    assert read_vox(str(path)).models[0][0, 0, 0] == 2


def test_names_with_spaces_are_imported() -> None:
    data = _file(
        _model((1, 1, 1), [(0, 0, 0, 1)]),
        _trn(0, 1, {}, {}, layer=-1),
        _grp(1, [2]),
        _trn(2, 3, {"_name": "window 1"}, {}),
        _shp(3, 0),
    )
    assert [o.name for o in objects_from_document(read_vox(data))] == ["window 1"]


def test_unsupported_names_raise_a_format_error() -> None:
    data = _file(
        _model((1, 1, 1), [(0, 0, 0, 1)]),
        _trn(0, 1, {}, {}, layer=-1),
        _grp(1, [2]),
        _trn(2, 3, {"_name": "door: left"}, {}),
        _shp(3, 0),
    )
    with pytest.raises(InvalidObjectNameError, match="door: left"):
        objects_from_document(read_vox(data))


def test_rotated_named_object_cannot_be_converted_yet() -> None:
    data = _file(
        _model((1, 1, 1), [(0, 0, 0, 1)]),
        _trn(0, 1, {}, {}, layer=-1),
        _grp(1, [2]),
        _trn(2, 3, {"_name": "wheel"}, {"_r": "17"}),
        _shp(3, 0),
    )
    with pytest.raises(UnsupportedRotationError, match="wheel"):
        objects_from_document(read_vox(data))


def test_identity_rotation_byte_is_accepted() -> None:
    data = _file(
        _model((1, 2, 1), [(0, 1, 0, 3)]),
        _trn(0, 1, {}, {}, layer=-1),
        _grp(1, [2]),
        _trn(2, 3, {"_name": "a"}, {"_r": str(IDENTITY_BYTE), "_t": "0 0 0"}),
        _shp(3, 0),
    )
    (obj,) = objects_from_document(read_vox(data))
    assert obj.name == "a"
    assert int(np.count_nonzero(obj.grid)) == 1


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not a vox file at all", "not a MagicaVoxel"),
        (b"VOX " + struct.pack("<i", 150) + b"MAIN" + struct.pack("<ii", 0, 999), "truncated MAIN"),
        (_file(_chunk("SIZE", struct.pack("<ii", 1, 1))), "truncated SIZE"),
        (_file(_chunk("SIZE", struct.pack("<iii", 0, 1, 1))), "invalid model size"),
        (_file(_chunk("XYZI", struct.pack("<i", 0))), "without a preceding SIZE"),
        (_file(_model((1, 1, 1), [(1, 0, 0, 1)])), "outside its model"),
        (_file(_chunk("SIZE", struct.pack("<iii", 1, 1, 1))), "not paired"),
        (
            _file(_model((1, 1, 1), [(0, 0, 0, 1)]), _trn(0, 9, {}, {}, layer=-1)),
            "missing node 9",
        ),
        (
            _file(_model((1, 1, 1), [(0, 0, 0, 1)]), _trn(0, 1, {}, {}), _shp(1, 4)),
            "missing model 4",
        ),
        (
            _file(_model((1, 1, 1), [(0, 0, 0, 1)]), _trn(0, 1, {}, {"_t": "1 2"}), _shp(1, 0)),
            "invalid translation",
        ),
        (
            _file(_model((1, 1, 1), [(0, 0, 0, 1)]), _trn(0, 1, {}, {"_t": "a b c"}), _shp(1, 0)),
            "invalid translation",
        ),
        (
            _file(_model((1, 1, 1), [(0, 0, 0, 1)]), _trn(0, 1, {}, {"_r": "3"}), _shp(1, 0)),
            "invalid rotation",
        ),
        (
            _file(_model((1, 1, 1), [(0, 0, 0, 1)]), _trn(0, 0, {}, {}, layer=-1)),
            "cyclic",
        ),
        (
            _file(
                _model((1, 1, 1), [(0, 0, 0, 1)]),
                _trn(0, 1, {}, {}),
                _chunk("nSHP", struct.pack("<i", 1) + _dict({}) + struct.pack("<i", 0)),
            ),
            "has no model",
        ),
        (_file(_chunk("ABCD", b""), b"XY"), "truncated chunk header"),
        (_file(_chunk("NOTE", struct.pack("<ii", 1, 50))), "truncated NOTE"),
    ],
)
def test_invalid_files_raise(data: bytes, message: str) -> None:
    with pytest.raises(VoxFormatError, match=message):
        read_vox(data)


def test_unknown_chunks_are_skipped() -> None:
    document = read_vox(
        _file(_chunk("rOBJ", _dict({"_type": "_x"})), _model((1, 1, 1), [(0, 0, 0, 5)]))
    )
    assert len(document.models) == 1


def test_palette_with_255_colors_is_accepted() -> None:
    colors = bytes((9, 8, 7, 255)) + bytes(254 * 4)
    document = read_vox(_file(_model((1, 1, 1), [(0, 0, 0, 1)]), _chunk("RGBA", colors)))
    assert document.palette is not None
    assert tuple(document.palette[1]) == (9, 8, 7, 255)
    assert tuple(document.palette[255]) == (0, 0, 0, 0)


def test_teardown_compressed_chunk_is_refused_explicitly() -> None:
    data = _file(_chunk("SIZE", struct.pack("<iii", 1, 1, 1)), _chunk("TDCZ", b"\x00" * 16))
    with pytest.raises(TeardownCompressedError, match="TDCZ"):
        read_vox(data)
