"""Shapes in the model frame must equal the voxcore shapes, whatever window they are computed on."""

from collections.abc import Callable

import numpy as np
import pytest

from buildup.project import (
    Shape,
    box_shape,
    cylinder_shape,
    edge_cut_shape,
    ellipsoid_shape,
    wedge_shape,
)
from buildup.project.names import (
    ProjectError,
    check_mod_name,
    check_name,
    check_project_name,
    default_mod_name,
)
from buildup.project.shapes import clip_to_world, inside_world
from buildup.voxcore import VoxcoreError
from buildup.voxcore import shapes as vs

# A reference grid covering model cells -20..20 on every axis.
LOW = (-20, -20, -20)
SIZE = (40, 40, 40)


def _shift(v: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(a - b for a, b in zip(v, LOW, strict=False))


CASES: list[tuple[Shape, np.ndarray]] = [
    (box_shape((-3, 0, -5), (4, 2, 6)), vs.box(SIZE, (17, 20, 15), (24, 22, 26))),
    (
        wedge_shape((-4, 0, -6), (4, 5, 6), ("top", "front")),
        vs.wedge(SIZE, (16, 20, 14), (24, 25, 26), ("top", "front")),
    ),
    (
        edge_cut_shape((-4, 0, -6), (4, 6, 6), ("top", "back"), (3, 4.5)),
        vs.edge_cut(SIZE, (16, 20, 14), (24, 26, 26), ("top", "back"), (3, 4.5)),
    ),
    (
        cylinder_shape("x", (4, -3), 4, (-6, -4)),
        vs.cylinder(SIZE, "x", (24, 17), 4, (14, 16)),
    ),
    (
        cylinder_shape("z", (2.5, 1.5), 1.5, (5, 9)),
        vs.cylinder(SIZE, "z", (22.5, 21.5), 1.5, (25, 29)),
    ),
    (
        ellipsoid_shape((0.5, 3, -2), (5, 3.5, 7)),
        vs.ellipsoid(SIZE, (20.5, 23, 18), (5, 3.5, 7)),
    ),
]


@pytest.mark.parametrize(("shape", "expected"), CASES)
def test_shape_equals_voxcore_on_any_window(shape: Shape, expected: np.ndarray) -> None:
    assert np.array_equal(shape.mask(LOW, SIZE), expected)
    # The bounding box holds every voxel of the shape.
    s = [shape.start[i] - LOW[i] for i in range(3)]
    e = [shape.end[i] - LOW[i] for i in range(3)]
    inside = np.zeros(SIZE, dtype=bool)
    inside[s[0] : e[0], s[1] : e[1], s[2] : e[2]] = True
    assert not np.any(expected & ~inside)
    # Computing on the bounding box only gives the same voxels.
    size = tuple(shape.end[i] - shape.start[i] for i in range(3))
    window = shape.mask(shape.start, (size[0], size[1], size[2]))
    assert np.array_equal(window, expected[s[0] : e[0], s[1] : e[1], s[2] : e[2]])


@pytest.mark.parametrize(("shape", "expected"), CASES)
def test_shape_on_a_window_smaller_than_its_bounds(shape: Shape, expected: np.ndarray) -> None:
    """Paint and carve compute masks only where the shape meets the part."""
    start = (shape.start[0] + 1, shape.start[1], shape.start[2] + 2)
    size = (2, 1, 3)
    s = [start[i] - LOW[i] for i in range(3)]
    window = shape.mask(start, size)
    assert np.array_equal(window, expected[s[0] : s[0] + 2, s[1] : s[1] + 1, s[2] : s[2] + 3])


@pytest.mark.parametrize(
    "make",
    [
        lambda: ellipsoid_shape((1e308, 0, 0), (1e308, 1, 1)),
        lambda: ellipsoid_shape((float("nan"), 0, 0), (1, 1, 1)),
        lambda: ellipsoid_shape((0, 0, 0), (float("inf"), 1, 1)),
        lambda: cylinder_shape("x", (0, 5000), 1, (0, 1)),
        lambda: box_shape((0, 0, 0), (5000, 1, 1)),
    ],
)
def test_non_finite_and_huge_values_are_refused(make: Callable[[], object]) -> None:
    with pytest.raises(VoxcoreError, match=r"finite|within"):
        make()


def test_cylinder_bounds() -> None:
    shape = cylinder_shape("x", (4, -3), 4, (-6, -4))
    assert (shape.start, shape.end) == ((-6, 0, -7), (-4, 8, 1))


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: box_shape((0, 0, 0), (1, 0, 1)), "below end"),
        (lambda: box_shape((0, 0), (1, 1, 1)), "three integers"),
        (lambda: wedge_shape((0, 0, 0), (2, 2, 2), ("top", "up")), "face must be"),
        (lambda: wedge_shape((0, 0, 0), (2, 2, 2), ("top", "bottom")), "different axes"),
        (lambda: edge_cut_shape((0, 0, 0), (2, 2, 2), ("top", "front"), (0, 1)), "positive"),
        (lambda: edge_cut_shape((0, 0, 0), (2, 2, 2), "top", (1, 1)), "two values"),
        (lambda: cylinder_shape("w", (0, 0), 1, (0, 1)), "axis"),
        (lambda: cylinder_shape("x", (0, 0), 0, (0, 1)), "positive"),
        (lambda: cylinder_shape("x", (0, 0), 1, (1, 1)), "empty"),
        (lambda: cylinder_shape("x", (0, 0, 0), 1, (0, 1)), "two values"),
        (lambda: ellipsoid_shape((0, 0, 0), (1, -1, 1)), "positive"),
    ],
)
def test_invalid_shapes(make: Callable[[], object], message: str) -> None:
    with pytest.raises(VoxcoreError, match=message):
        make()


def test_clip_and_inside_world() -> None:
    assert clip_to_world((-300, 0, 0), (-128, 1, 1)) is None
    assert clip_to_world((-200, 0, 0), (-100, 1, 1)) == ((-128, 0, 0), (-100, 1, 1))
    assert clip_to_world((-200, 0, 120), (10, 1, 140)) == ((-128, 0, 120), (10, 1, 128))
    assert inside_world((128, -128, 0))
    assert not inside_world((128.5, 0, 0))


@pytest.mark.parametrize("name", ["body", "wheel_fl", "a", "x" * 32, "r2d2"])
def test_valid_names(name: str) -> None:
    assert check_name(name, "part") == name


@pytest.mark.parametrize("name", ["", "Body", "1st", "_x", "a b", "x" * 33, "dé", 3, None])
def test_invalid_names(name: object) -> None:
    with pytest.raises(ProjectError, match="invalid part name"):
        check_name(name, "part")


@pytest.mark.parametrize("name", ["con", "nul", "com1", "lpt9", "../x", "a/b", "x" * 41, "Car"])
def test_invalid_project_names(name: str) -> None:
    with pytest.raises(ProjectError, match="invalid project name"):
        check_project_name(name)


def test_mod_names() -> None:
    assert check_mod_name("Red Pickup 2") == "Red Pickup 2"
    for bad in ("Red  Pickup", " Red", "Red_Pickup", "Rouge é", "", "x" * 41, "Nul", "COM1"):
        with pytest.raises(ProjectError, match="invalid mod name"):
            check_mod_name(bad)
    assert default_mod_name("red_pickup") == "Red Pickup"
    assert default_mod_name("car__2") == "Car 2"
