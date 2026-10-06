from typing import Any

import numpy as np
import pytest

from buildup.voxcore import (
    VoxcoreError,
    box,
    carve,
    compose,
    crop,
    fill,
    fill_enclosed,
    filled_bounds,
    flip,
    hollow,
    intersect,
    is_connected,
    mirror,
    new_grid,
    outside,
    paint,
    sphere,
    subtract,
    union,
    wedge,
)
from buildup.voxcore.ops import neighbor


def _cube(n: int, index: int = 5) -> np.ndarray[Any, np.dtype[np.uint8]]:
    return np.full((n, n, n), index, dtype=np.uint8)


def test_new_grid() -> None:
    grid = new_grid((2, 3, 4))
    assert grid.shape == (2, 3, 4)
    assert grid.dtype == np.uint8
    assert not grid.any()
    bad: Any = (2, 0, 4)
    with pytest.raises(VoxcoreError):
        new_grid(bad)


def test_fill_paint_carve_do_not_modify_input() -> None:
    grid = new_grid((3, 1, 1))
    grid[0, 0, 0] = 9
    mask = box(grid.shape, (0, 0, 0), (2, 1, 1))
    filled = fill(grid, mask, 4)
    assert filled[:, 0, 0].tolist() == [4, 4, 0]
    painted = paint(grid, mask, 4)
    assert painted[:, 0, 0].tolist() == [4, 0, 0]  # paint never creates voxels
    carved = carve(filled, box(grid.shape, (1, 0, 0), (3, 1, 1)))
    assert carved[:, 0, 0].tolist() == [4, 0, 0]
    assert grid[:, 0, 0].tolist() == [9, 0, 0]


@pytest.mark.parametrize("index", [0, 256, -1, 1.5, True])
def test_bad_palette_index(index: Any) -> None:
    grid = new_grid((1, 1, 1))
    with pytest.raises(VoxcoreError):
        fill(grid, grid == 0, index)


def test_mask_must_match_grid() -> None:
    grid = new_grid((2, 2, 2))
    with pytest.raises(VoxcoreError):
        fill(grid, np.ones((1, 2, 2), dtype=np.bool_), 1)
    not_bool: Any = np.ones((2, 2, 2), dtype=np.uint8)
    with pytest.raises(VoxcoreError):
        fill(grid, not_bool, 1)


def test_bad_grid() -> None:
    with pytest.raises(VoxcoreError):
        flip(np.zeros((2, 2), dtype=np.uint8), "x")
    wrong_dtype: Any = np.zeros((2, 2, 2), dtype=np.int32)
    with pytest.raises(VoxcoreError):
        flip(wrong_dtype, "x")
    with pytest.raises(VoxcoreError):
        flip(np.zeros((0, 2, 2), dtype=np.uint8), "x")


def test_booleans() -> None:
    a = np.array([1, 1, 0, 0], dtype=np.uint8).reshape(4, 1, 1)
    b = np.array([0, 2, 2, 0], dtype=np.uint8).reshape(4, 1, 1)
    assert union(a, b).ravel().tolist() == [1, 2, 2, 0]
    assert subtract(a, b).ravel().tolist() == [1, 0, 0, 0]
    assert intersect(a, b).ravel().tolist() == [0, 1, 0, 0]
    with pytest.raises(VoxcoreError):
        union(a, new_grid((2, 1, 1)))


def test_flip_and_mirror() -> None:
    grid = np.array([1, 2, 3, 4, 5], dtype=np.uint8).reshape(5, 1, 1)
    assert flip(grid, "x").ravel().tolist() == [5, 4, 3, 2, 1]
    assert mirror(grid, "x").ravel().tolist() == [1, 2, 3, 2, 1]
    assert mirror(grid, "x", keep="high").ravel().tolist() == [5, 4, 3, 4, 5]
    even = np.array([1, 2, 3, 4], dtype=np.uint8).reshape(1, 4, 1)
    assert mirror(even, "y").ravel().tolist() == [1, 2, 2, 1]
    bad_keep: Any = "middle"
    with pytest.raises(VoxcoreError):
        mirror(grid, "x", keep=bad_keep)
    bad_axis: Any = "w"
    with pytest.raises(VoxcoreError):
        flip(grid, bad_axis)


def test_hollow_keeps_a_shell() -> None:
    cube = _cube(5)
    shell = hollow(cube)
    assert np.count_nonzero(shell) == 5**3 - 3**3
    assert shell[2, 2, 2] == 0
    assert shell[0, 2, 2] == 5
    thick = hollow(cube, thickness=2)
    assert np.count_nonzero(thick) == 5**3 - 1
    with pytest.raises(VoxcoreError):
        hollow(cube, thickness=0)


def test_hollow_touching_the_grid_border_keeps_border_voxels() -> None:
    slab = np.full((3, 3, 1), 7, dtype=np.uint8)
    assert np.array_equal(hollow(slab), slab)  # every voxel touches the outside


def test_fill_enclosed_and_outside() -> None:
    shell = hollow(_cube(5))
    assert not outside(shell)[2, 2, 2]
    refilled = fill_enclosed(shell, 9)
    assert refilled[2, 2, 2] == 9
    assert np.count_nonzero(refilled == 9) == 27
    # An opening makes the cavity part of the outside: nothing to fill.
    opened = carve(shell, box(shell.shape, (2, 2, 0), (3, 3, 1)))
    assert np.count_nonzero(fill_enclosed(opened, 9) == 9) == 0


def test_neighbor_shift() -> None:
    values = np.array([1, 2, 3], dtype=np.int32).reshape(3, 1, 1)
    assert neighbor(values, 0, 1).ravel().tolist() == [2, 3, 0]
    assert neighbor(values, 0, -1).ravel().tolist() == [0, 1, 2]
    with pytest.raises(VoxcoreError):
        neighbor(values, 0, 2)


def test_bounds_crop_compose() -> None:
    grid = new_grid((4, 4, 4))
    assert filled_bounds(grid) is None
    with pytest.raises(VoxcoreError):
        crop(grid)
    grid[1, 2, 3] = 1
    grid[2, 2, 3] = 1
    assert filled_bounds(grid) == ((1, 2, 3), (3, 3, 4))
    cropped, offset = crop(grid)
    assert cropped.shape == (2, 1, 1)
    assert offset == (1, 2, 3)

    a = np.full((2, 1, 1), 1, dtype=np.uint8)
    b = np.full((2, 1, 1), 2, dtype=np.uint8)
    b[1, 0, 0] = 0
    merged, origin = compose([(a, (0, 0, 0)), (b, (1, 0, 0)), (a, (-3, 2, 0))])
    assert origin == (-3, 0, 0)
    assert merged.shape == (6, 3, 1)  # x from -3 to 3
    assert merged[3:6, 0, 0].tolist() == [1, 2, 0]  # later part wins only where it has voxels
    assert merged[0:2, 2, 0].tolist() == [1, 1]
    with pytest.raises(VoxcoreError):
        compose([])


@pytest.mark.parametrize("radius", [2.5, 4.3, 7.7, 13.0])
@pytest.mark.parametrize("thickness", [1, 2])
def test_hollow_round_shapes_stay_in_one_piece(radius: float, thickness: int) -> None:
    n = int(2 * radius + 4)
    size = (n, n, n)
    ball = fill(new_grid(size), sphere(size, (n / 2, n / 2, n / 2), radius), 1)
    shell = hollow(ball, thickness)
    assert np.count_nonzero(shell) <= np.count_nonzero(ball)  # small balls have no inside
    # Voxels hold together through faces only: a staircase touching by edges would fall apart.
    assert is_connected(shell)


def test_hollow_open_slope_stays_in_one_piece() -> None:
    size = (20, 12, 30)
    ramp = fill(new_grid(size), wedge(size, (1, 1, 1), (19, 11, 29), ("top", "front")), 1)
    shell = carve(hollow(ramp), box(size, (0, 0, 0), (2, 12, 30)))  # remove the x = 1 end cap
    assert is_connected(shell)


def test_hollow_thickness_must_be_an_integer() -> None:
    thickness: Any = 1.5
    with pytest.raises(VoxcoreError, match="thickness"):
        hollow(_cube(3), thickness)


def test_compose_rejects_fractional_origins() -> None:
    origin: Any = (0.5, 0, 0)
    with pytest.raises(VoxcoreError, match="origin"):
        compose([(_cube(1), origin)])
