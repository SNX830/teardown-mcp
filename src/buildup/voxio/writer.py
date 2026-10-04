"""Writer for MagicaVoxel ``.vox`` files, version 150, following the layout of official game files.

Chunk order (as in official game files, docs/TEARDOWN_REFERENCE.md §2): ``SIZE``/``XYZI`` per model,
root ``nTRN``, ``nGRP``, then one ``nTRN`` (named) + ``nSHP`` per object, 8 ``LAYR``, ``RGBA``,
256 ``MATL``, ``NOTE``. The editor-only chunks ``IMAP``, ``rOBJ`` and ``rCAM`` are left out on
purpose.
Rotations are never written (decision D-003).
"""

import struct
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import numpy as np

from buildup.palette import MAX_INDEX, Finish, Palette, palette_row_names
from buildup.voxio.axes import grid_to_magica, origin_to_translation
from buildup.voxio.document import VoxFormatError
from buildup.voxio.objects import VoxObject

VOX_VERSION: Final = 150
LAYER_COUNT: Final = 8


class UndefinedPaletteIndexError(VoxFormatError):
    """An object uses palette indices that the palette does not define."""


def _string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("<i", len(raw)) + raw


def _dict(values: dict[str, str]) -> bytes:
    return struct.pack("<i", len(values)) + b"".join(
        _string(k) + _string(v) for k, v in values.items()
    )


def _chunk(chunk_id: str, content: bytes, children: bytes = b"") -> bytes:
    return (
        chunk_id.encode("ascii")
        + struct.pack("<ii", len(content), len(children))
        + content
        + children
    )


def _transform(
    node_id: int, attributes: dict[str, str], child: int, layer: int, frame: dict[str, str]
) -> bytes:
    return _chunk(
        "nTRN",
        struct.pack("<i", node_id)
        + _dict(attributes)
        + struct.pack("<iiii", child, -1, layer, 1)
        + _dict(frame),
    )


def _check(objects: Sequence[VoxObject], palette: Palette) -> None:
    if not objects:
        raise VoxFormatError("nothing to write: no objects")
    names = [obj.name for obj in objects]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise VoxFormatError(f"duplicate object names: {', '.join(duplicates)}")
    for obj in objects:
        used = np.unique(obj.grid)
        used = used[used != 0]
        if used.size == 0:
            raise VoxFormatError(f"object {obj.name!r} is empty")
        undefined = [int(i) for i in used if int(i) not in palette.entries]
        if undefined:
            raise UndefinedPaletteIndexError(
                f"object {obj.name!r} uses palette indices not defined in the palette: {undefined}"
            )


def encode_vox(objects: Sequence[VoxObject], palette: Palette) -> bytes:
    """Encode named objects and their palette as ``.vox`` bytes.

    Objects are written in the given order (later objects get higher node ids). Which one Teardown
    treats as "newer" when objects overlap is UNVERIFIED (docs/TEARDOWN_REFERENCE.md §4): avoid
    overlapping objects.

    Raises:
        VoxFormatError: No objects, duplicate names, an empty object, or palette indices used by an
            object but not defined in the palette (``UndefinedPaletteIndexError``).
    """
    _check(objects, palette)
    parts: list[bytes] = []

    for obj in objects:
        grid = grid_to_magica(obj.grid)
        x, y, z = np.nonzero(grid)
        voxels = np.column_stack((x, y, z, grid[x, y, z])).astype(np.uint8)
        parts.append(_chunk("SIZE", struct.pack("<iii", *grid.shape)))
        parts.append(_chunk("XYZI", struct.pack("<i", len(voxels)) + voxels.tobytes()))

    # Scene graph: root transform 0 -> group 1 -> (transform 2k+2 -> shape 2k+3) per object.
    child_ids = [2 + 2 * k for k in range(len(objects))]
    parts.append(_transform(0, {}, 1, -1, {}))
    parts.append(
        _chunk(
            "nGRP",
            struct.pack("<i", 1)
            + _dict({})
            + struct.pack(f"<i{len(child_ids)}i", len(child_ids), *child_ids),
        )
    )
    for k, obj in enumerate(objects):
        tx, ty, tz = origin_to_translation(obj.origin, obj.size)
        parts.append(
            _transform(2 + 2 * k, {"_name": obj.name}, 3 + 2 * k, 0, {"_t": f"{tx} {ty} {tz}"})
        )
        parts.append(
            _chunk(
                "nSHP",
                struct.pack("<i", 3 + 2 * k) + _dict({}) + struct.pack("<ii", 1, k) + _dict({}),
            )
        )

    parts.extend(
        _chunk(
            "LAYR", struct.pack("<i", layer) + _dict({"_name": str(layer)}) + struct.pack("<i", -1)
        )
        for layer in range(LAYER_COUNT)
    )

    # RGBA position p holds palette index p + 1; the last position (index 256) is unused.
    rgba = np.zeros((256, 4), dtype=np.uint8)
    rgba[:MAX_INDEX] = palette.rgba()[1:]
    parts.append(_chunk("RGBA", rgba.tobytes()))

    # MATL ids 1..256 as in official files; id 256 has no palette index and stays matte.
    for material_id in range(1, 257):
        matl = palette.matl(material_id) if material_id <= MAX_INDEX else Finish.matte().to_matl()
        parts.append(_chunk("MATL", struct.pack("<i", material_id) + _dict(matl)))

    notes = palette_row_names()
    parts.append(
        _chunk("NOTE", struct.pack("<i", len(notes)) + b"".join(_string(n) for n in notes))
    )

    children = b"".join(parts)
    return b"VOX " + struct.pack("<i", VOX_VERSION) + _chunk("MAIN", b"", children)


def write_vox(path: Path, objects: Sequence[VoxObject], palette: Palette) -> None:
    """Write named objects and their palette to a ``.vox`` file (see ``encode_vox``).

    The parent folder is created if needed.
    """
    data = encode_vox(objects, palette)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
