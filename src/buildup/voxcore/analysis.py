"""Analysis of grids: connected parts.

Teardown voxels only hold together through faces; voxels touching only by an edge or a corner
fall apart when damaged (docs/TEARDOWN_REFERENCE.md §4). Parts are therefore face-connected
components.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from buildup.voxcore.grid import EMPTY, Grid, Vec3, check_grid
from buildup.voxcore.ops import neighbor

Labels = npt.NDArray[np.int32]


@dataclass(frozen=True)
class Component:
    """A face-connected group of voxels.

    Attributes:
        label: Its number in the label array (1 = largest component).
        voxels: Number of voxels.
        start: Bounding box start (grid indices).
        end: Bounding box end (exclusive).
    """

    label: int
    voxels: int
    start: Vec3
    end: Vec3


def label_components(grid: Grid) -> tuple[Labels, list[Component]]:
    """Find the face-connected components of the non-empty voxels.

    Returns:
        An ``int32`` array of the grid's shape (0 for empty cells, else the component label)
        and the components, largest first (label 1 is the largest; ties keep scan order).
    """
    filled = check_grid(grid) != EMPTY
    labels = np.where(filled, np.arange(1, grid.size + 1, dtype=np.int32).reshape(grid.shape), 0)
    labels = labels.astype(np.int32)
    # Propagate the smallest label through face neighbours until nothing changes.
    while True:
        previous = labels
        for axis in range(3):
            for step in (-1, 1):
                other = neighbor(labels, axis, step)
                take = filled & (other > 0) & (other < labels)
                labels = np.where(take, other, labels)
        # Pointer jumping: label L names voxel L - 1, which is in the same component and may
        # already carry a smaller label.
        flat = labels.ravel()
        labels = np.where(filled, flat[np.maximum(labels, 1) - 1], 0).astype(np.int32)
        if np.array_equal(labels, previous):
            break

    raw = labels[filled]
    if raw.size == 0:
        return labels, []
    unique, first, counts = np.unique(raw, return_index=True, return_counts=True)
    # Largest first; ties in scan order of their first voxel.
    order = np.lexsort((first, -counts))
    remap = np.zeros(int(unique.max()) + 1, dtype=np.int32)
    remap[unique[order]] = np.arange(1, len(order) + 1, dtype=np.int32)
    result = remap[labels].astype(np.int32)

    # Bounding boxes of all components in one pass: sort the voxels by label, then reduce.
    cells = np.argwhere(filled)
    cell_labels = result[filled]
    by_label = np.argsort(cell_labels, kind="stable")
    sorted_cells = cells[by_label]
    starts = np.searchsorted(cell_labels[by_label], np.arange(1, len(order) + 1))
    lows = np.minimum.reduceat(sorted_cells, starts, axis=0)
    highs = np.maximum.reduceat(sorted_cells, starts, axis=0) + 1
    sizes = counts[order]
    components = [
        Component(
            label=n + 1,
            voxels=int(sizes[n]),
            start=(int(lows[n][0]), int(lows[n][1]), int(lows[n][2])),
            end=(int(highs[n][0]), int(highs[n][1]), int(highs[n][2])),
        )
        for n in range(len(order))
    ]
    return result, components


def components(grid: Grid) -> list[Component]:
    """Face-connected components of the non-empty voxels, largest first."""
    return label_components(grid)[1]


def is_connected(grid: Grid) -> bool:
    """True if all non-empty voxels form one face-connected piece (or the grid is empty)."""
    return len(components(grid)) <= 1
