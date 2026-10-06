from typing import Any

import numpy as np
import pytest
from PIL import Image

from buildup.render import Annotations, Marker, RenderError, View, meters, preview_sheet
from buildup.render.sheet import (
    MARGIN,
    MARKER,
    RULER,
    TITLE_HEIGHT,
    boundary_pixel,
    choose_scale,
    group_markers,
    ruler_spacing,
    ticks,
)
from buildup.voxcore import VoxcoreError, new_grid

COLORS = np.full((256, 3), 120, dtype=np.uint8)
HEADER = 46


def _rgb(image: Image.Image, at: tuple[int, int]) -> list[int]:
    """Color of the pixel at (x, y)."""
    return [int(v) for v in np.asarray(image)[at[1], at[0]]]


def _car_like() -> np.ndarray:
    grid = new_grid((16, 6, 36))
    grid[:, 2:6, :] = 1
    return grid


def test_default_sheet_has_six_panels_and_is_deterministic() -> None:
    first = preview_sheet(_car_like(), COLORS, origin=(-8, 0, -18))
    second = preview_sheet(_car_like(), COLORS, origin=(-8, 0, -18))
    assert first.mode == "RGB"
    assert first.width > 900
    assert np.array_equal(np.asarray(first), np.asarray(second))


def test_marker_is_drawn_at_its_position_in_a_front_view() -> None:
    grid = _car_like()
    origin = (-8, 0, -18)
    marker = Marker("axle", (-8.0, 4.0, -12.0))  # left edge of the body (x = -0.8 m), y 0.4 m
    sheet = preview_sheet(
        grid,
        COLORS,
        origin=origin,
        views=[View.FRONT],
        annotations=Annotations("t", (marker,)),
    )
    scale = choose_scale(grid.shape)
    # Front view: columns follow -X, so x = -0.8 m (grid boundary 0) is the right image edge.
    x = MARGIN + RULER + boundary_pixel(0, 16, -1, scale, rows=False)
    y = HEADER + TITLE_HEIGHT + boundary_pixel(4, 6, 1, scale, rows=True)
    assert x == MARGIN + RULER + 16 * scale
    assert _rgb(sheet, (int(x), int(y))) == list(MARKER)


def test_sheet_needs_a_view() -> None:
    with pytest.raises(ValueError, match="view"):
        preview_sheet(_car_like(), COLORS, views=[])


def test_scale_and_rulers() -> None:
    assert choose_scale((16, 6, 36)) == 8
    assert choose_scale((300, 1, 1)) == 1
    assert choose_scale((1, 1, 1)) == 16
    assert ruler_spacing(36, 8) == 5  # every 0.5 m, 40 px apart
    assert ruler_spacing(14, 4) == 10  # small model at a small scale: 1 m, readable labels
    assert ruler_spacing(1000, 1) == 100
    assert ticks(-18, 36, 8) == [(3, -15), (8, -10), (13, -5), (18, 0), (23, 5), (28, 10), (33, 15)]


@pytest.mark.parametrize(
    ("value", "text"),
    [(0, "0"), (-12, "-1.2"), (5, "0.5"), (10, "1"), (-0.4, "-0.04"), (0.01, "0")],
)
def test_meters(value: float, text: str) -> None:
    assert meters(value) == text


def test_boundary_pixel_directions() -> None:
    assert boundary_pixel(2, 10, 1, 3, rows=False) == 6  # columns growing to the right
    assert boundary_pixel(2, 10, -1, 3, rows=False) == 24
    assert boundary_pixel(2, 10, 1, 3, rows=True) == 24  # Y up: row pixels grow downwards
    assert boundary_pixel(2, 10, -1, 3, rows=True) == 6


def test_group_markers_merges_same_pixel() -> None:
    groups = group_markers([((10.2, 5.0), "fl"), ((30.0, 5.0), "fr"), ((9.8, 5.1), "bl")])
    assert groups == [((10.2, 5.0), "fl + bl"), ((30.0, 5.0), "fr")]


def test_marker_in_a_top_view_where_rows_grow_with_z() -> None:
    grid = _car_like()
    origin = (-8, 0, -18)
    marker = Marker("nose", (0.0, 6.0, -18.0))  # center of the front edge (z = -1.8 m)
    sheet = preview_sheet(
        grid, COLORS, origin=origin, views=[View.TOP], annotations=Annotations("t", (marker,))
    )
    scale = choose_scale(grid.shape)
    # Top view: columns follow +X, rows follow -Z (front at the top): the front edge is row 0.
    x = MARGIN + RULER + boundary_pixel(8, 16, 1, scale, rows=False)
    y = HEADER + TITLE_HEIGHT + boundary_pixel(0, 36, -1, scale, rows=True)
    assert y == HEADER + TITLE_HEIGHT
    assert _rgb(sheet, (int(x), int(y))) == list(MARKER)


def test_sheet_validates_its_inputs() -> None:
    bad_view: Any = ["side"]
    with pytest.raises(RenderError, match="unknown view"):
        preview_sheet(_car_like(), COLORS, views=bad_view)
    bad_origin: Any = (0.5, 0, 0)
    with pytest.raises(VoxcoreError, match="origin"):
        preview_sheet(_car_like(), COLORS, origin=bad_origin)
    short: Any = (1.0, 2.0)
    bad_marker = Marker("m", short)
    with pytest.raises(VoxcoreError, match="marker 'm'"):
        preview_sheet(_car_like(), COLORS, annotations=Annotations(markers=(bad_marker,)))
