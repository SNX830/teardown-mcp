"""Reading and writing MagicaVoxel ``.vox`` files (see docs/TEARDOWN_REFERENCE.md §1-2, §5)."""

from buildup.voxio.document import (
    SceneInstance,
    TeardownCompressedError,
    VoxDocument,
    VoxFormatError,
)
from buildup.voxio.objects import (
    MAX_MODEL_SIZE,
    OBJECT_NAME_PATTERN,
    InvalidObjectNameError,
    UnsupportedRotationError,
    VoxObject,
    objects_from_document,
)
from buildup.voxio.reader import read_vox
from buildup.voxio.rotation import RotationError, decode_rotation, encode_rotation
from buildup.voxio.writer import UndefinedPaletteIndexError, encode_vox, write_vox

__all__ = [
    "MAX_MODEL_SIZE",
    "OBJECT_NAME_PATTERN",
    "InvalidObjectNameError",
    "RotationError",
    "SceneInstance",
    "TeardownCompressedError",
    "UndefinedPaletteIndexError",
    "UnsupportedRotationError",
    "VoxDocument",
    "VoxFormatError",
    "VoxObject",
    "decode_rotation",
    "encode_rotation",
    "encode_vox",
    "objects_from_document",
    "read_vox",
    "write_vox",
]
