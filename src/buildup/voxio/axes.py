"""Conversion between the Teardown frame used internally and MagicaVoxel's frame.

- Teardown frame (internal, AGENTS.md §6): X right, Y up, vehicles face -Z.
- MagicaVoxel frame: Z up.
- Mapping (docs/TEARDOWN_REFERENCE.md §5, status DEDUCED): MagicaVoxel (x, y, z) -> Teardown
  (x, z, -y). Equivalently, Teardown (x, y, z) -> MagicaVoxel (x, -z, y).

Voxel cells: Teardown cell ``z`` covers ``[z, z + 1)``, which maps to MagicaVoxel ``y`` in
``(-z - 1, -z]``, i.e. MagicaVoxel cell ``-z - 1``.

Positions in a MagicaVoxel scene are given by the model's pivot, located at ``floor(size / 2)`` in
model coordinates (docs/TEARDOWN_REFERENCE.md §2).

This is the only module that knows about MagicaVoxel axes.
"""

import numpy as np
import numpy.typing as npt

Vec3 = tuple[int, int, int]
Grid = npt.NDArray[np.uint8]


def grid_to_magica(grid: Grid) -> Grid:
    """Convert a Teardown-frame grid ``[x, y, z]`` to a MagicaVoxel-frame grid ``[x, y, z]``."""
    return np.ascontiguousarray(np.flip(grid, axis=2).transpose(0, 2, 1))


def grid_from_magica(grid: Grid) -> Grid:
    """Convert a MagicaVoxel-frame grid to a Teardown-frame grid (inverse of ``grid_to_magica``)."""
    return np.ascontiguousarray(np.flip(grid.transpose(0, 2, 1), axis=2))


def size_to_magica(size: Vec3) -> Vec3:
    """Convert a Teardown-frame grid size to the MagicaVoxel-frame size."""
    return (size[0], size[2], size[1])


def pivot(size: Vec3) -> Vec3:
    """Pivot of a MagicaVoxel model of the given size: ``floor(size / 2)`` on each axis."""
    return (size[0] // 2, size[1] // 2, size[2] // 2)


def origin_to_translation(origin: Vec3, size: Vec3) -> Vec3:
    """MagicaVoxel ``_t`` translation for a Teardown-frame grid placed at ``origin``.

    Args:
        origin: Teardown-frame position of the grid's minimum corner, in voxels.
        size: Teardown-frame grid size.
    """
    ox, oy, oz = origin
    sx, sy, sz = size
    mv_min = (ox, -(oz + sz), oy)
    p = pivot((sx, sz, sy))
    return (mv_min[0] + p[0], mv_min[1] + p[1], mv_min[2] + p[2])


def translation_to_origin(translation: Vec3, magica_size: Vec3) -> Vec3:
    """Teardown-frame origin of an unrotated MagicaVoxel model (inverse of origin_to_translation).

    Args:
        translation: MagicaVoxel ``_t`` of the model.
        magica_size: MagicaVoxel-frame size of the model.
    """
    p = pivot(magica_size)
    mx, my, mz = (translation[0] - p[0], translation[1] - p[1], translation[2] - p[2])
    return (mx, mz, -my - magica_size[1])
