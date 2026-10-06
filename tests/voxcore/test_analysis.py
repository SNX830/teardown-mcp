from collections import deque

import numpy as np

from buildup.voxcore import components, is_connected, label_components, new_grid


def test_empty_grid_has_no_component() -> None:
    labels, found = label_components(new_grid((3, 3, 3)))
    assert found == []
    assert not labels.any()
    assert is_connected(new_grid((1, 1, 1)))


def test_face_connectivity_only() -> None:
    grid = new_grid((3, 3, 3))
    grid[0, 0, 0] = 1
    grid[1, 1, 0] = 1  # touches the first voxel by an edge only
    grid[2, 2, 2] = 1  # by a corner only
    found = components(grid)
    assert len(found) == 3
    assert not is_connected(grid)


def test_components_sorted_largest_first_with_bounds() -> None:
    grid = new_grid((10, 1, 3))
    grid[0:6, 0, 0] = 1  # 6 voxels
    grid[8, 0, 0:3] = 2  # 3 voxels, different colors do not matter
    grid[3, 0, 2] = 3  # single floating voxel
    labels, found = label_components(grid)
    assert [c.voxels for c in found] == [6, 3, 1]
    assert [c.label for c in found] == [1, 2, 3]
    assert found[0].start == (0, 0, 0)
    assert found[0].end == (6, 1, 1)
    assert found[1].start == (8, 0, 0)
    assert found[1].end == (9, 1, 3)
    assert labels[3, 0, 2] == 3
    assert labels[5, 0, 0] == 1
    assert labels.dtype == np.int32


def test_long_snake_is_one_component() -> None:
    # A winding path is the slow case for label propagation.
    grid = new_grid((9, 1, 9))
    for row in range(0, 9, 2):
        grid[:, 0, row] = 1
        if row + 1 < 9:
            column = 8 if (row // 2) % 2 == 0 else 0
            grid[column, 0, row + 1] = 1
    assert is_connected(grid)
    assert components(grid)[0].voxels == np.count_nonzero(grid)


def _bfs_component_sizes(grid: np.ndarray) -> list[int]:
    """Reference implementation: breadth-first search over face neighbours."""
    seen = np.zeros(grid.shape, dtype=bool)
    sizes = []
    for start in map(tuple, np.argwhere(grid > 0)):
        if seen[start]:
            continue
        seen[start] = True
        queue = deque([start])
        count = 0
        while queue:
            cell = queue.popleft()
            count += 1
            for axis in range(3):
                for step in (-1, 1):
                    nxt = list(cell)
                    nxt[axis] += step
                    t = tuple(nxt)
                    if all(0 <= t[i] < grid.shape[i] for i in range(3)) and grid[t] and not seen[t]:
                        seen[t] = True
                        queue.append(t)
        sizes.append(count)
    return sorted(sizes, reverse=True)


def test_components_match_a_reference_search_on_random_grids() -> None:
    rng = np.random.default_rng(1234)
    for density in (0.2, 0.35, 0.5, 0.7):
        for _ in range(10):
            grid = (rng.random((7, 6, 8)) < density).astype(np.uint8)
            labels, found = label_components(grid)
            assert [c.voxels for c in found] == _bfs_component_sizes(grid)
            for c in found:
                cells = np.argwhere(labels == c.label)
                assert tuple(cells.min(axis=0)) == c.start
                assert tuple(cells.max(axis=0) + 1) == c.end


def test_many_components_are_fast_enough() -> None:
    checker = (np.indices((40, 40, 40)).sum(axis=0) % 2).astype(np.uint8)
    found = components(checker)
    assert len(found) == 32000
    assert all(c.voxels == 1 for c in found)
