from typing import Any

import numpy as np
import pytest

from buildup.voxcore import (
    VoxcoreError,
    box,
    chamfer,
    cylinder,
    edge_cut,
    ellipsoid,
    half_space,
    sphere,
    wedge,
)
from buildup.voxcore.grid import as_float3, as_number


def test_box_exact_region_and_clipping() -> None:
    mask = box((4, 4, 4), (1, 0, 2), (3, 2, 4))
    assert mask.dtype == np.bool_
    assert mask.shape == (4, 4, 4)
    assert np.count_nonzero(mask) == 2 * 2 * 2
    assert mask[1, 0, 2]
    assert mask[2, 1, 3]
    assert not mask[0, 0, 2]
    # Partly outside the grid: clipped, no error.
    assert np.count_nonzero(box((4, 4, 4), (-2, -2, -2), (1, 1, 1))) == 1


@pytest.mark.parametrize(
    ("start", "end"), [((0, 0, 0), (0, 1, 1)), ((2, 0, 0), (1, 1, 1)), ((0, 0), (1, 1, 1))]
)
def test_box_rejects_empty_or_malformed_region(start: Any, end: Any) -> None:
    with pytest.raises(VoxcoreError):
        box((4, 4, 4), start, end)


@pytest.mark.parametrize("size", [(0, 1, 1), (1, 1), (1.5, 1, 1), (True, 1, 1)])
def test_bad_grid_size(size: Any) -> None:
    with pytest.raises(VoxcoreError):
        box(size, (0, 0, 0), (1, 1, 1))


def test_cylinder_wheel_profile() -> None:
    # Diameter 8 along X: rows of 4, 6, 8, 8, 8, 8, 6, 4 voxels.
    mask = cylinder((2, 8, 8), "x", (4, 4), 4, (0, 2))
    rows = [int(np.count_nonzero(mask[0, y, :])) for y in range(8)]
    assert rows == [4, 6, 8, 8, 8, 8, 6, 4]
    assert np.array_equal(mask[0], mask[1])
    # Symmetric: the box center is the axle.
    assert np.array_equal(mask, mask[:, ::-1, :])
    assert np.array_equal(mask, mask[:, :, ::-1])


def test_cylinder_span_and_axis() -> None:
    mask = cylinder((5, 10, 5), "y", (2.5, 2.5), 1, (2, 7))
    assert np.count_nonzero(mask[:, 0:2, :]) == 0
    assert np.count_nonzero(mask[:, 7:, :]) == 0
    # Odd diameter: a plus sign of 5 voxels per layer (radius 1 around a voxel center).
    assert np.count_nonzero(mask[:, 3, :]) == 5
    assert mask[2, 3, 2]


@pytest.mark.parametrize(
    ("axis", "radius", "span"), [("w", 1, (0, 1)), ("x", 0, (0, 1)), ("x", 1, (2, 2))]
)
def test_cylinder_rejects_bad_arguments(axis: Any, radius: float, span: tuple[int, int]) -> None:
    with pytest.raises(VoxcoreError):
        cylinder((4, 4, 4), axis, (2, 2), radius, span)


def test_sphere_is_symmetric_and_bounded() -> None:
    mask = sphere((6, 6, 6), (3, 3, 3), 3)
    for axis in range(3):
        assert np.array_equal(mask, np.flip(mask, axis=axis))
    assert mask[0, 2, 2]  # touches the grid faces at the middle
    assert not mask[0, 0, 0]  # corners are outside
    assert np.count_nonzero(mask) == 136


def test_ellipsoid_radii_per_axis() -> None:
    mask = ellipsoid((10, 4, 4), (5, 2, 2), (5, 2, 2))
    assert mask[0, 1, 1]
    assert mask[9, 2, 2]
    with pytest.raises(VoxcoreError):
        ellipsoid((4, 4, 4), (2, 2, 2), (1, 0, 1))


def test_half_space() -> None:
    mask = half_space((4, 1, 1), (2, 0, 0), (1, 0, 0))
    assert mask[:, 0, 0].tolist() == [True, True, False, False]
    with pytest.raises(VoxcoreError):
        half_space((4, 1, 1), (2, 0, 0), (0, 0, 0))


def test_chamfer_steps() -> None:
    size = (1, 4, 4)
    full = box(size, (0, 0, 0), (1, 4, 4))
    one = chamfer(size, (0, 0, 0), (1, 4, 4), 1, [("top", "front")])
    two = chamfer(size, (0, 0, 0), (1, 4, 4), 2, [("top", "front")])
    assert np.count_nonzero(full) - np.count_nonzero(one) == 1
    assert not one[0, 3, 0]  # the top-front edge voxel (top = high y, front = low z)
    assert np.count_nonzero(full) - np.count_nonzero(two) == 3
    assert not two[0, 3, 1]
    assert not two[0, 2, 0]
    assert two[0, 2, 1]


def test_edge_cut_uses_both_depths() -> None:
    size = (1, 4, 8)
    cut = edge_cut(size, (0, 0, 0), (1, 4, 8), ("top", "front"), (2, 4))
    # Top row (d_top = 0.5): cut while d_front / 4 <= 0.75, i.e. the first 3 voxels.
    assert cut[0, 3, :].tolist() == [True, True, True, False, False, False, False, False]
    assert cut[0, 2, :].tolist() == [True, False, False, False, False, False, False, False]
    with pytest.raises(VoxcoreError):
        edge_cut(size, (0, 0, 0), (1, 4, 8), ("top", "bottom"), (1, 1))
    with pytest.raises(VoxcoreError):
        edge_cut(size, (0, 0, 0), (1, 4, 8), ("top", "front"), (0, 1))
    roof: Any = "roof"
    with pytest.raises(VoxcoreError):
        edge_cut(size, (0, 0, 0), (1, 4, 8), (roof, "front"), (1, 1))


def test_wedge_is_a_ramp() -> None:
    size = (1, 4, 4)
    ramp = wedge(size, (0, 0, 0), (1, 4, 4), ("top", "front"))
    heights = [int(np.count_nonzero(ramp[0, :, z])) for z in range(4)]
    assert heights == [1, 2, 3, 4]  # low at the front (-Z), full height at the back
    assert heights == sorted(heights)


@pytest.mark.parametrize(
    ("start", "end"),
    [((-5, 0, 0), (-1, 4, 4)), ((10, 0, 0), (12, 4, 4)), ((0, -9, 0), (4, 0, 4))],
)
def test_box_entirely_outside_the_grid_is_empty(start: Any, end: Any) -> None:
    size = (10, 4, 4)
    assert not box(size, start, end).any()
    assert not edge_cut(size, start, end, ("top", "front"), (2, 2)).any()
    assert not chamfer(size, start, end, 1, [("top", "front")]).any()


def test_cylinder_validates_json_like_inputs() -> None:
    radius: Any = "3"
    with pytest.raises(VoxcoreError, match="radius"):
        cylinder((4, 4, 4), "x", (2, 2), radius, (0, 1))
    center: Any = (2,)
    with pytest.raises(VoxcoreError, match="center"):
        cylinder((4, 4, 4), "x", center, 1, (0, 1))
    span: Any = (0.5, 2)
    with pytest.raises(VoxcoreError, match="span"):
        cylinder((4, 4, 4), "x", (2, 2), 1, span)
    # Lists are accepted like tuples (JSON arrays).
    as_list: Any = [2, 2]
    span_list: Any = [0, 4]
    assert cylinder((4, 4, 4), "x", as_list, 1, span_list).any()


def test_chamfer_amount_must_be_an_integer() -> None:
    amount: Any = 1.5
    with pytest.raises(VoxcoreError, match="chamfer amount"):
        chamfer((4, 4, 4), (0, 0, 0), (4, 4, 4), amount, [("top", "front")])
    with pytest.raises(VoxcoreError, match="chamfer amount"):
        chamfer((4, 4, 4), (0, 0, 0), (4, 4, 4), 0, [("top", "front")])


def test_edge_cut_validates_faces_and_depths() -> None:
    size = (4, 4, 4)
    depths: Any = ("a", 1)
    with pytest.raises(VoxcoreError, match="depth"):
        edge_cut(size, (0, 0, 0), (4, 4, 4), ("top", "front"), depths)
    faces: Any = ("top", "front", "left")
    with pytest.raises(VoxcoreError, match="faces"):
        edge_cut(size, (0, 0, 0), (4, 4, 4), faces, (1, 1))
    with pytest.raises(VoxcoreError, match="faces"):
        wedge(size, (0, 0, 0), (4, 4, 4), faces)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_numbers_must_be_finite(bad: float) -> None:
    with pytest.raises(VoxcoreError, match="finite"):
        as_number(bad, "radius")
    with pytest.raises(VoxcoreError, match="finite"):
        as_float3((0, bad, 0), "center")
    with pytest.raises(VoxcoreError, match="finite"):
        sphere((4, 4, 4), (2, 2, bad), 1)
