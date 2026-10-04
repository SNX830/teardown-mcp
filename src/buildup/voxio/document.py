"""Raw content of a ``.vox`` file, in MagicaVoxel's own frame (as read from disk)."""

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from buildup.voxio.rotation import IDENTITY, Matrix3

Vec3 = tuple[int, int, int]


class VoxFormatError(ValueError):
    """The data is not a valid ``.vox`` file, or uses a feature this code does not support."""


class TeardownCompressedError(VoxFormatError):
    """The file uses Teardown's compressed ``TDCZ`` voxel chunk, which is not supported yet."""


@dataclass(frozen=True)
class SceneInstance:
    """One shape placed in the scene, with its transform composed from the root of the scene graph.

    Attributes:
        name: ``_name`` of the transform node directly above the shape, if any. This is the name
            Teardown XML uses in ``object="..."``.
        model_index: Index into ``VoxDocument.models``.
        translation: World translation (``_t``) of the model pivot, MagicaVoxel frame.
        rotation: World rotation, MagicaVoxel frame.
        layer: Layer id of the transform node (-1 if none).
        hidden: Whether the transform node or its layer is hidden.
    """

    name: str | None
    model_index: int
    translation: Vec3 = (0, 0, 0)
    rotation: Matrix3 = IDENTITY
    layer: int = -1
    hidden: bool = False


@dataclass
class VoxDocument:
    """Everything read from a ``.vox`` file.

    Attributes:
        version: File format version (150 or 200 in practice).
        models: Voxel grids indexed ``[x, y, z]`` in the MagicaVoxel frame; 0 means empty.
        instances: Placed shapes. Files without a scene graph get one unnamed instance per model.
        palette: (256, 4) RGBA table indexed by palette index, or ``None`` if the file has no
            ``RGBA`` chunk (MagicaVoxel then uses its default palette).
        materials: ``MATL`` dictionaries by material id.
        notes: Palette row names (``NOTE`` chunk), 32 entries when present.
    """

    version: int
    models: list[npt.NDArray[np.uint8]] = field(default_factory=list)
    instances: list[SceneInstance] = field(default_factory=list)
    palette: npt.NDArray[np.uint8] | None = None
    materials: dict[int, dict[str, str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
