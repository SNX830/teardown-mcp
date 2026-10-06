"""Operations on grids. Every function returns a new grid and leaves its inputs unchanged.

Neighbours are face neighbours (6 per voxel): in Teardown voxels only hold together through faces
(docs/TEARDOWN_REFERENCE.md §4). Cells outside the grid count as empty.
"""

from typing import Literal

import numpy as np
import numpy.typing as npt

from buildup.voxcore.grid import (
    EMPTY,
    Axis,
    Grid,
    Mask,
    VoxcoreError,
    as_int,
    axis_number,
    check_grid,
    check_index,
    check_mask,
)


def neighbor[S: np.generic](values: npt.NDArray[S], axis: int, step: int) -> npt.NDArray[S]:
    """``out[i] = values[i + step]`` along ``axis`` (``step`` is 1 or -1); zero outside."""
    if step not in (-1, 1):
        raise VoxcoreError(f"step must be 1 or -1, got {step}")
    out = np.zeros_like(values)
    src = [slice(None)] * 3
    dst = [slice(None)] * 3
    if step == 1:
        src[axis], dst[axis] = slice(1, None), slice(None, -1)
    else:
        src[axis], dst[axis] = slice(None, -1), slice(1, None)
    out[tuple(dst)] = values[tuple(src)]
    return out


def fill(grid: Grid, mask: Mask, index: int) -> Grid:
    """Set every voxel of ``mask`` to palette ``index``, replacing what was there."""
    out = check_grid(grid).copy()
    out[check_mask(grid, mask)] = check_index(index)
    return out


def paint(grid: Grid, mask: Mask, index: int) -> Grid:
    """Repaint the non-empty voxels of ``mask`` with palette ``index``; empty cells stay empty."""
    out = check_grid(grid).copy()
    out[check_mask(grid, mask) & (grid != EMPTY)] = check_index(index)
    return out


def carve(grid: Grid, mask: Mask) -> Grid:
    """Empty every voxel of ``mask``."""
    out = check_grid(grid).copy()
    out[check_mask(grid, mask)] = EMPTY
    return out


def _check_same_shape(base: Grid, other: Grid) -> None:
    check_grid(base)
    check_grid(other)
    if base.shape != other.shape:
        raise VoxcoreError(f"grids must have the same shape: {base.shape} and {other.shape}")


def union(base: Grid, other: Grid) -> Grid:
    """``base`` with the non-empty voxels of ``other`` added (``other`` wins where both are set)."""
    _check_same_shape(base, other)
    return np.where(other != EMPTY, other, base).astype(np.uint8)


def subtract(base: Grid, other: Grid) -> Grid:
    """``base`` without the cells where ``other`` has a voxel."""
    _check_same_shape(base, other)
    return np.where(other != EMPTY, EMPTY, base).astype(np.uint8)


def intersect(base: Grid, other: Grid) -> Grid:
    """``base`` only where ``other`` also has a voxel."""
    _check_same_shape(base, other)
    return np.where(other != EMPTY, base, EMPTY).astype(np.uint8)


def flip(grid: Grid, axis: Axis) -> Grid:
    """Reverse the grid along ``axis`` (along ``"x"``: a left-right mirror image)."""
    return np.flip(check_grid(grid), axis=axis_number(axis)).copy()


def mirror(grid: Grid, axis: Axis, keep: Literal["low", "high"] = "low") -> Grid:
    """Make the grid symmetric about its center plane across ``axis``.

    The ``keep`` half is copied, mirrored, over the other half; for an odd size the middle slice
    is kept as is. Typical use: model the left side of a vehicle (``axis="x"``, low X) and mirror
    it to the right.

    Raises:
        VoxcoreError: If ``keep`` is not ``"low"`` or ``"high"``.
    """
    if keep not in ("low", "high"):
        raise VoxcoreError(f"keep must be 'low' or 'high', got {keep!r}")
    out = check_grid(grid).copy()
    a = axis_number(axis)
    n = out.shape[a]
    half = n // 2
    low = [slice(None)] * 3
    high = [slice(None)] * 3
    low[a] = slice(0, half)
    high[a] = slice(n - half, n)
    if keep == "low":
        out[tuple(high)] = np.flip(out[tuple(low)], axis=a)
    else:
        out[tuple(low)] = np.flip(out[tuple(high)], axis=a)
    return out


def _erode_26(filled: Mask) -> Mask:
    """Voxels whose 26 neighbours (faces, edges, corners) are all filled; outside is empty."""
    padded = np.pad(filled, 1, constant_values=False)
    sx, sy, sz = filled.shape
    out = filled.copy()
    for dx in (0, 1, 2):
        for dy in (0, 1, 2):
            for dz in (0, 1, 2):
                out &= padded[dx : dx + sx, dy : dy + sy, dz : dz + sz]
    return out


def hollow(grid: Grid, thickness: int = 1) -> Grid:
    """Empty the inside of solid parts, keeping a shell ``thickness`` voxels thick.

    A voxel is kept when an empty cell (or the grid border) is within ``thickness`` steps of it,
    counting diagonal steps too. Counting diagonals keeps the shell of slopes and curves joined by
    faces: with face steps only, a sphere's shell would be a staircase of voxels touching by
    edges, which falls apart in Teardown (docs/TEARDOWN_REFERENCE.md §4).

    Raises:
        VoxcoreError: If ``thickness`` is not an integer of at least 1.
    """
    thickness = as_int(thickness, "thickness", minimum=1)
    filled = check_grid(grid) != EMPTY
    inner = filled
    for _ in range(thickness):
        inner = _erode_26(inner)
    out = grid.copy()
    out[inner] = EMPTY
    return out


def outside(grid: Grid) -> Mask:
    """Empty cells connected to the grid border through empty cells (face steps)."""
    empty = check_grid(grid) == EMPTY
    reach: Mask = np.zeros_like(empty)
    reach[0, :, :] = reach[-1, :, :] = True
    reach[:, 0, :] = reach[:, -1, :] = True
    reach[:, :, 0] = reach[:, :, -1] = True
    reach &= empty
    while True:
        grown: Mask = reach.copy()
        for axis in range(3):
            for step in (-1, 1):
                grown |= neighbor(reach, axis, step)
        grown &= empty
        if np.array_equal(grown, reach):
            return reach
        reach = grown


def fill_enclosed(grid: Grid, index: int) -> Grid:
    """Fill empty cavities that are completely enclosed (not reachable from the grid border)."""
    out = check_grid(grid).copy()
    out[(grid == EMPTY) & ~outside(grid)] = check_index(index)
    return out
