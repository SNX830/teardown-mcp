"""Reader for MagicaVoxel ``.vox`` files (versions 150 and 200).

Layout from the official specification (github.com/ephtracy/voxel-model); see
docs/TEARDOWN_REFERENCE.md §2. Unknown chunks are skipped.
"""

import os
import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import numpy.typing as npt

from buildup.voxio.document import (
    SceneInstance,
    TeardownCompressedError,
    Vec3,
    VoxDocument,
    VoxFormatError,
)
from buildup.voxio.rotation import (
    IDENTITY,
    Matrix3,
    RotationError,
    apply,
    decode_rotation,
    multiply,
)

_MAX_SCENE_DEPTH = 256
# Nodes may be shared (several transforms pointing to one shape, as in official files), so a crafted
# file could make the traversal explode; this caps the total number of node visits.
_MAX_SCENE_VISITS = 1_000_000


class _Cursor:
    """Little-endian reader over a chunk's content, raising VoxFormatError on truncation."""

    def __init__(self, data: bytes, what: str) -> None:
        self.data = data
        self.pos = 0
        self.what = what

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise VoxFormatError(f"truncated {self.what} chunk")
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def int32(self) -> int:
        value: int = struct.unpack("<i", self.take(4))[0]
        return value

    def string(self) -> str:
        return self.take(self.int32()).decode("utf-8", errors="replace")

    def dict(self) -> dict[str, str]:
        return {self.string(): self.string() for _ in range(self.int32())}


@dataclass(frozen=True)
class _Context:
    depth: int = 0
    name: str | None = None
    layer: int = -1
    hidden: bool = False

    def deeper(self) -> "_Context":
        """Same context one level deeper, without the transform name (names attach to shapes)."""
        return _Context(self.depth + 1, None, self.layer, self.hidden)


@dataclass
class _Transform:
    attributes: dict[str, str]
    child: int
    layer: int
    frame: dict[str, str]


@dataclass
class _Group:
    children: list[int]


@dataclass
class _Shape:
    model: int


@dataclass
class _Parsed:
    version: int
    sizes: list[Vec3] = field(default_factory=list)
    models: list[npt.NDArray[np.uint8]] = field(default_factory=list)
    nodes: dict[int, _Transform | _Group | _Shape] = field(default_factory=dict)
    hidden_layers: set[int] = field(default_factory=set)
    palette: npt.NDArray[np.uint8] | None = None
    materials: dict[int, dict[str, str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def read_vox(source: str | os.PathLike[str] | bytes | bytearray) -> VoxDocument:
    """Read a ``.vox`` file.

    Args:
        source: Path of the file, or its raw bytes.

    Raises:
        VoxFormatError: If the data is not a valid ``.vox`` file.
        OSError: If the file cannot be read.
    """
    data = bytes(source) if isinstance(source, bytes | bytearray) else Path(source).read_bytes()
    if len(data) < 20 or data[:4] != b"VOX " or data[8:12] != b"MAIN":
        raise VoxFormatError("not a MagicaVoxel .vox file")
    (version,) = struct.unpack_from("<i", data, 4)
    main_content, main_children = struct.unpack_from("<ii", data, 12)
    start = 20 + main_content
    end = start + main_children
    if main_content < 0 or main_children < 0 or end > len(data):
        raise VoxFormatError("truncated MAIN chunk")

    parsed = _Parsed(version)
    pos = start
    while pos < end:
        if pos + 12 > end:
            raise VoxFormatError("truncated chunk header")
        chunk_id = data[pos : pos + 4].decode("ascii", errors="replace")
        content_size, children_size = struct.unpack_from("<ii", data, pos + 4)
        if content_size < 0 or children_size < 0 or pos + 12 + content_size + children_size > end:
            raise VoxFormatError(f"truncated {chunk_id} chunk")
        _read_chunk(parsed, chunk_id, data[pos + 12 : pos + 12 + content_size])
        pos += 12 + content_size + children_size

    if len(parsed.models) != len(parsed.sizes):
        raise VoxFormatError("SIZE and XYZI chunks are not paired")
    return VoxDocument(
        version=version,
        models=parsed.models,
        instances=_instances(parsed),
        palette=parsed.palette,
        materials=parsed.materials,
        notes=parsed.notes,
    )


def _read_size(parsed: _Parsed, cursor: _Cursor) -> None:
    size = (cursor.int32(), cursor.int32(), cursor.int32())
    if any(not 1 <= s <= 256 for s in size):
        raise VoxFormatError(f"invalid model size {size}")
    parsed.sizes.append(size)


def _read_xyzi(parsed: _Parsed, cursor: _Cursor) -> None:
    parsed.models.append(_read_voxels(parsed, cursor))


def _read_rgba(parsed: _Parsed, cursor: _Cursor) -> None:
    # The specification stores 256 colors; some official Teardown files store only 255 (1020 bytes).
    count = 255 if len(cursor.data) == 255 * 4 else 256
    colors = np.frombuffer(cursor.take(count * 4), dtype=np.uint8).reshape(count, 4)
    palette = np.zeros((256, 4), dtype=np.uint8)
    palette[1:] = colors[:255]  # the color at position i is palette index i + 1
    parsed.palette = palette


def _read_tdcz(parsed: _Parsed, cursor: _Cursor) -> None:
    # Teardown's own compressed voxel chunk (docs/TEARDOWN_REFERENCE.md §2): its voxel order is not
    # verified yet, so such files are refused instead of being decoded wrongly.
    del parsed, cursor
    raise TeardownCompressedError(
        "this file stores its voxels in Teardown's compressed TDCZ format, not supported yet"
    )


def _read_matl(parsed: _Parsed, cursor: _Cursor) -> None:
    material_id = cursor.int32()
    parsed.materials[material_id] = cursor.dict()


def _read_note(parsed: _Parsed, cursor: _Cursor) -> None:
    parsed.notes = [cursor.string() for _ in range(cursor.int32())]


def _read_layr(parsed: _Parsed, cursor: _Cursor) -> None:
    layer_id = cursor.int32()
    if cursor.dict().get("_hidden") == "1":
        parsed.hidden_layers.add(layer_id)


def _read_ntrn(parsed: _Parsed, cursor: _Cursor) -> None:
    node_id = cursor.int32()
    attributes = cursor.dict()
    child, _reserved, layer, frame_count = (cursor.int32() for _ in range(4))
    frames = [cursor.dict() for _ in range(frame_count)]
    parsed.nodes[node_id] = _Transform(attributes, child, layer, frames[0] if frames else {})


def _read_ngrp(parsed: _Parsed, cursor: _Cursor) -> None:
    node_id = cursor.int32()
    cursor.dict()
    parsed.nodes[node_id] = _Group([cursor.int32() for _ in range(cursor.int32())])


def _read_nshp(parsed: _Parsed, cursor: _Cursor) -> None:
    node_id = cursor.int32()
    cursor.dict()
    if cursor.int32() < 1:
        raise VoxFormatError(f"shape node {node_id} has no model")
    parsed.nodes[node_id] = _Shape(cursor.int32())


# PACK, IMAP, rOBJ, rCAM, MATT and unknown future chunks are skipped.
_CHUNK_READERS: dict[str, Callable[[_Parsed, _Cursor], None]] = {
    "SIZE": _read_size,
    "XYZI": _read_xyzi,
    "RGBA": _read_rgba,
    "MATL": _read_matl,
    "NOTE": _read_note,
    "LAYR": _read_layr,
    "nTRN": _read_ntrn,
    "nGRP": _read_ngrp,
    "nSHP": _read_nshp,
    "TDCZ": _read_tdcz,
}


def _read_chunk(parsed: _Parsed, chunk_id: str, content: bytes) -> None:
    reader = _CHUNK_READERS.get(chunk_id)
    if reader is not None:
        reader(parsed, _Cursor(content, chunk_id))


def _read_voxels(parsed: _Parsed, cursor: _Cursor) -> npt.NDArray[np.uint8]:
    if len(parsed.sizes) != len(parsed.models) + 1:
        raise VoxFormatError("XYZI chunk without a preceding SIZE chunk")
    size = parsed.sizes[-1]
    count = cursor.int32()
    voxels = np.frombuffer(cursor.take(count * 4), dtype=np.uint8).reshape(count, 4)
    x, y, z, color = voxels.T
    if count and (x.max() >= size[0] or y.max() >= size[1] or z.max() >= size[2]):
        raise VoxFormatError(f"voxel outside its model of size {size}")
    grid = np.zeros(size, dtype=np.uint8)
    grid[x, y, z] = color
    return grid


def _parse_translation(text: str | None) -> Vec3:
    if not text:
        return (0, 0, 0)
    parts = text.split()
    if len(parts) != 3:
        raise VoxFormatError(f"invalid translation {text!r}")
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError as error:
        raise VoxFormatError(f"invalid translation {text!r}") from error


def _parse_rotation(text: str | None) -> Matrix3:
    if not text:
        return IDENTITY
    try:
        return decode_rotation(int(text))
    except (ValueError, RotationError) as error:
        raise VoxFormatError(f"invalid rotation {text!r}") from error


def _instances(parsed: _Parsed) -> list[SceneInstance]:
    if 0 not in parsed.nodes:
        return [SceneInstance(name=None, model_index=i) for i in range(len(parsed.models))]

    instances: list[SceneInstance] = []
    visits = 0

    def visit(node_id: int, rotation: Matrix3, translation: Vec3, context: _Context) -> None:
        nonlocal visits
        visits += 1
        if context.depth > _MAX_SCENE_DEPTH:
            raise VoxFormatError("scene graph is too deep or cyclic")
        if visits > _MAX_SCENE_VISITS:
            raise VoxFormatError("scene graph is too large")
        node = parsed.nodes.get(node_id)
        if node is None:
            raise VoxFormatError(f"scene graph references missing node {node_id}")
        match node:
            case _Transform():
                local_t = _parse_translation(node.frame.get("_t"))
                world_t = apply(rotation, local_t)
                child_context = _Context(
                    depth=context.depth + 1,
                    name=node.attributes.get("_name"),
                    layer=node.layer,
                    hidden=context.hidden
                    or node.attributes.get("_hidden") == "1"
                    or node.layer in parsed.hidden_layers,
                )
                visit(
                    node.child,
                    multiply(rotation, _parse_rotation(node.frame.get("_r"))),
                    (
                        world_t[0] + translation[0],
                        world_t[1] + translation[1],
                        world_t[2] + translation[2],
                    ),
                    child_context,
                )
            case _Group():
                # Official files sometimes list the same child several times in one group
                # (docs/TEARDOWN_REFERENCE.md §2): visit it once.
                for child in dict.fromkeys(node.children):
                    visit(child, rotation, translation, context.deeper())
            case _Shape():
                if not 0 <= node.model < len(parsed.models):
                    raise VoxFormatError(f"shape references missing model {node.model}")
                instances.append(
                    SceneInstance(
                        name=context.name,
                        model_index=node.model,
                        translation=translation,
                        rotation=rotation,
                        layer=context.layer,
                        hidden=context.hidden,
                    )
                )

    visit(0, IDENTITY, (0, 0, 0), _Context())
    return instances
