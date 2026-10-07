"""Voxel grids in the Teardown frame (AGENTS.md §6): types, validation, bounds, composition.

A grid is a ``uint8`` array indexed ``[x, y, z]``: X right, Y up, front is -Z, 1 voxel = 0.1 m.
Value 0 is empty; 1-255 is a palette index. Grid functions never modify their inputs.
"""

import math
from collections.abc import Sequence
from typing import Final, Literal

import numpy as np
import numpy.typing as npt

Grid = npt.NDArray[np.uint8]
Mask = npt.NDArray[np.bool_]
Vec3 = tuple[int, int, int]
Axis = Literal["x", "y", "z"]

EMPTY: Final = 0
AXES: Final[dict[str, int]] = {"x": 0, "y": 1, "z": 2}


class VoxcoreError(ValueError):
    """Invalid argument for a voxel operation (bad size, index, axis, region...)."""


def axis_number(axis: str) -> int:
    """Array axis of ``"x"``, ``"y"`` or ``"z"``.

    Raises:
        VoxcoreError: For any other name.
    """
    if axis not in AXES:
        raise VoxcoreError(f"axis must be 'x', 'y' or 'z', got {axis!r}")
    return AXES[axis]


def as_int(value: object, what: str, *, minimum: int | None = None) -> int:
    """Validate one integer (not a bool), optionally at least ``minimum``.

    Raises:
        VoxcoreError: Otherwise, naming ``what``.
    """
    if isinstance(value, bool) or not isinstance(value, int | np.integer):
        raise VoxcoreError(f"{what} must be an integer, got {value!r}")
    if minimum is not None and value < minimum:
        raise VoxcoreError(f"{what} must be an integer >= {minimum}, got {value!r}")
    return int(value)


def as_pair(value: object, what: str) -> tuple[object, object]:
    """Validate a tuple or list of exactly two items (checked further by the caller).

    Raises:
        VoxcoreError: Otherwise, naming ``what``.
    """
    if not isinstance(value, tuple | list) or len(value) != 2:
        raise VoxcoreError(f"{what} must be two values, got {value!r}")
    return value[0], value[1]


def as_number(value: object, what: str, *, positive: bool = False) -> float:
    """Validate one finite number (not a bool), optionally strictly positive.

    Raises:
        VoxcoreError: Otherwise, naming ``what``.
    """
    if isinstance(value, bool) or not isinstance(value, int | float | np.number):
        raise VoxcoreError(f"{what} must be a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise VoxcoreError(f"{what} must be a finite number, got {value!r}")
    if positive and number <= 0:
        raise VoxcoreError(f"{what} must be positive, got {value!r}")
    return number


def as_vec3(value: object, what: str, *, minimum: int | None = None) -> Vec3:
    """Validate three integers (a tuple or list), optionally each at least ``minimum``.

    Raises:
        VoxcoreError: Otherwise, naming ``what``.
    """
    if (
        not isinstance(value, tuple | list)
        or len(value) != 3
        or any(isinstance(v, bool) or not isinstance(v, int | np.integer) for v in value)
    ):
        raise VoxcoreError(f"{what} must be three integers, got {value!r}")
    x, y, z = (int(v) for v in value)
    if minimum is not None and min(x, y, z) < minimum:
        raise VoxcoreError(f"{what} must be three integers >= {minimum}, got {value!r}")
    return x, y, z


def as_float3(value: object, what: str, *, positive: bool = False) -> tuple[float, float, float]:
    """Validate three finite numbers (a tuple or list), optionally each strictly positive.

    Raises:
        VoxcoreError: Otherwise, naming ``what``.
    """
    if (
        not isinstance(value, tuple | list)
        or len(value) != 3
        or any(isinstance(v, bool) or not isinstance(v, int | float | np.number) for v in value)
    ):
        raise VoxcoreError(f"{what} must be three numbers, got {value!r}")
    x, y, z = (float(v) for v in value)
    if not all(math.isfinite(v) for v in (x, y, z)):
        raise VoxcoreError(f"{what} must be three finite numbers, got {value!r}")
    if positive and min(x, y, z) <= 0:
        raise VoxcoreError(f"{what} must be three positive numbers, got {value!r}")
    return x, y, z


def check_index(index: object) -> int:
    """Return ``index`` if it is a usable palette index (1-255).

    Raises:
        VoxcoreError: Otherwise (0 means empty and cannot be painted).
    """
    if isinstance(index, bool) or not isinstance(index, int | np.integer) or not 1 <= index <= 255:
        raise VoxcoreError(f"palette index must be an integer from 1 to 255, got {index!r}")
    return int(index)


def check_grid(grid: object) -> Grid:
    """Return ``grid`` if it is a 3D ``uint8`` array with at least one cell.

    Raises:
        VoxcoreError: Otherwise.
    """
    if not isinstance(grid, np.ndarray) or grid.dtype != np.uint8 or grid.ndim != 3:
        raise VoxcoreError("grid must be a 3D numpy array of dtype uint8")
    if grid.size == 0:
        raise VoxcoreError("grid must have at least one cell")
    return grid


def check_mask(grid: Grid, mask: Mask) -> Mask:
    """Return ``mask`` if it is a boolean array with the shape of ``grid``.

    Raises:
        VoxcoreError: Otherwise.
    """
    if mask.dtype != np.bool_ or mask.shape != grid.shape:
        raise VoxcoreError(f"mask must be a boolean array of shape {grid.shape}")
    return mask


def new_grid(size: Vec3) -> Grid:
    """Return an empty grid of ``size`` voxels (x, y, z), each at least 1.

    Raises:
        VoxcoreError: If a size is not a positive integer.
    """
    return np.zeros(as_vec3(size, "size", minimum=1), dtype=np.uint8)


def filled_bounds(grid: Grid) -> tuple[Vec3, Vec3] | None:
    """Bounding box of the non-empty voxels as ``(start, end)`` (end exclusive), or ``None``."""
    filled = np.argwhere(check_grid(grid) != EMPTY)
    if len(filled) == 0:
        return None
    low = filled.min(axis=0)
    high = filled.max(axis=0) + 1
    return (int(low[0]), int(low[1]), int(low[2])), (int(high[0]), int(high[1]), int(high[2]))


def crop(grid: Grid) -> tuple[Grid, Vec3]:
    """Remove the empty border of a grid.

    Returns:
        The cropped grid and the position of its first cell in the original grid.

    Raises:
        VoxcoreError: If the grid is empty.
    """
    bounds = filled_bounds(grid)
    if bounds is None:
        raise VoxcoreError("cannot crop an empty grid")
    (x0, y0, z0), (x1, y1, z1) = bounds
    return grid[x0:x1, y0:y1, z0:z1].copy(), (x0, y0, z0)


def compose(parts: Sequence[tuple[Grid, Vec3]]) -> tuple[Grid, Vec3]:
    """Merge placed grids into one grid covering all of them.

    Args:
        parts: ``(grid, origin)`` pairs; ``origin`` is the position of the grid's first cell
            (Teardown frame, voxels). Where parts overlap, a later part's non-empty voxels win.

    Returns:
        The merged grid and its origin.

    Raises:
        VoxcoreError: If ``parts`` is empty.
    """
    if not parts:
        raise VoxcoreError("nothing to compose")
    parts = [(check_grid(grid), as_vec3(origin, "origin")) for grid, origin in parts]
    lows = np.array([origin for _, origin in parts])
    highs = np.array([np.add(origin, check_grid(grid).shape) for grid, origin in parts])
    low = lows.min(axis=0)
    size = highs.max(axis=0) - low
    merged = np.zeros(tuple(int(s) for s in size), dtype=np.uint8)
    for grid, origin in parts:
        x, y, z = (int(v) for v in np.subtract(origin, low))
        sx, sy, sz = grid.shape
        target = merged[x : x + sx, y : y + sy, z : z + sz]
        np.copyto(target, grid, where=grid != EMPTY)
    return merged, (int(low[0]), int(low[1]), int(low[2]))
