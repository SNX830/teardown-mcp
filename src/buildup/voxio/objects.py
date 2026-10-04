"""Named voxel objects in the Teardown frame, and their conversion from a read ``VoxDocument``."""

import re
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

from buildup.voxio.axes import grid_from_magica, translation_to_origin
from buildup.voxio.document import Vec3, VoxDocument, VoxFormatError
from buildup.voxio.rotation import IDENTITY

#: Allowed object names (decision D-018): words of letters, digits, ``_``, ``.`` or ``-``
#: separated by single spaces, 1 to 64 characters. Official files use names such as "window 1".
# Always use fullmatch(): with match(), "$" would accept a trailing newline.
OBJECT_NAME_PATTERN: Final = re.compile(r"(?=.{1,64}\Z)[A-Za-z0-9_.-]+(?: [A-Za-z0-9_.-]+)*")

#: Largest model edge the .vox format can store (voxel coordinates are single bytes).
MAX_MODEL_SIZE: Final = 256


class InvalidObjectNameError(VoxFormatError):
    """An object name does not follow ``OBJECT_NAME_PATTERN``."""


@dataclass(frozen=True, eq=False)
class VoxObject:
    """A named voxel model in the Teardown frame.

    Attributes:
        name: Object name, used by Teardown XML as ``object="name"``. Letters, digits, ``_``,
            ``.`` and ``-``, words separated by single spaces, 1 to 64 characters.
        grid: ``uint8`` array indexed ``[x, y, z]`` (Teardown frame: Y up, front is -Z);
            0 = empty, 1-255 = palette index. Each edge 1 to 256 voxels.
        origin: Teardown-frame position of the grid's minimum corner in the file's scene, in voxels.
            Sets where the object sits in the MagicaVoxel scene (and in game when the whole file is
            loaded at once, docs/TEARDOWN_REFERENCE.md §4); a Teardown XML ``object="..."``
            reference places the object itself.
    """

    name: str
    grid: npt.NDArray[np.uint8]
    origin: Vec3 = (0, 0, 0)

    def __post_init__(self) -> None:
        if not OBJECT_NAME_PATTERN.fullmatch(self.name):
            raise InvalidObjectNameError(
                f"invalid object name {self.name!r}: use 1-64 letters, digits, '_', '.' or '-', "
                "with single spaces between words"
            )
        if self.grid.dtype != np.uint8 or self.grid.ndim != 3:
            raise ValueError(f"object {self.name!r}: grid must be a 3D uint8 array")
        if any(not 1 <= s <= MAX_MODEL_SIZE for s in self.grid.shape):
            raise ValueError(
                f"object {self.name!r}: size {self.grid.shape} exceeds 1..{MAX_MODEL_SIZE} per axis"
            )

    @property
    def size(self) -> Vec3:
        """Grid size in voxels (x, y, z), Teardown frame."""
        x, y, z = self.grid.shape
        return (x, y, z)


class UnsupportedRotationError(VoxFormatError):
    """The file contains rotated objects, which cannot be converted yet."""


def objects_from_document(document: VoxDocument) -> list[VoxObject]:
    """Convert the named, unrotated instances of a document into Teardown-frame objects.

    Unnamed instances are skipped.

    Raises:
        UnsupportedRotationError: If a named instance is rotated (rotated imports come later,
            see docs/ROADMAP.md 0.8.0).
        InvalidObjectNameError: If a name does not follow ``OBJECT_NAME_PATTERN``.
    """
    objects: list[VoxObject] = []
    for instance in document.instances:
        if instance.name is None:
            continue
        if instance.rotation != IDENTITY:
            raise UnsupportedRotationError(f"object {instance.name!r} is rotated")
        model = document.models[instance.model_index]
        x, y, z = model.shape
        origin = translation_to_origin(instance.translation, (x, y, z))
        objects.append(VoxObject(instance.name, grid_from_magica(model), origin))
    return objects
