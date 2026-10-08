"""See-through (glass) voxels in previews: they tint what lies behind them."""

import numpy as np
import pytest
from PIL import Image

from buildup.render import Annotations, View, iso_image, ortho_view, preview_sheet
from buildup.render.iso import FACE_LIGHT, iso_frame
from buildup.render.views import (
    BACKGROUND,
    GLASS_ALPHA,
    RenderError,
    edges,
    see_through_mask,
    shade,
)
from buildup.voxcore import new_grid

SOLID, GLASS, OTHER_GLASS = 1, 2, 3
COLORS = np.zeros((256, 3), dtype=np.uint8)
COLORS[SOLID] = (200, 40, 40)
COLORS[GLASS] = (100, 180, 240)
COLORS[OTHER_GLASS] = (20, 220, 20)
CLEAR = {GLASS, OTHER_GLASS}


def _line(*cells: int) -> np.ndarray:
    """A 1 x 1 x n grid seen from the front: cells listed from the front (z = 0) backwards."""
    grid = new_grid((1, 1, len(cells)))
    grid[0, 0, :] = cells
    return grid


def _mix(behind: np.ndarray, glass: np.ndarray) -> np.ndarray:
    return behind * (1 - GLASS_ALPHA) + glass * GLASS_ALPHA


def test_glass_in_front_of_a_solid_voxel_is_a_layer() -> None:
    image = ortho_view(_line(0, GLASS, 0, SOLID), View.FRONT, CLEAR)
    assert image.indices[0, 0] == SOLID
    assert image.depth[0, 0] == 3
    assert image.glass[:, 0, 0].tolist() == [GLASS]
    assert image.surface is not None
    assert image.surface[0, 0] == 1
    assert image.outline_depth[0, 0] == 1


def test_consecutive_glass_voxels_are_one_layer_and_separate_runs_are_two() -> None:
    thick = ortho_view(_line(GLASS, GLASS, GLASS, SOLID), View.FRONT, CLEAR)
    assert thick.glass[:, 0, 0].tolist() == [GLASS]
    two = ortho_view(_line(GLASS, 0, OTHER_GLASS, 0), View.FRONT, CLEAR)
    assert two.glass[:, 0, 0].tolist() == [GLASS, OTHER_GLASS]  # nearest first
    assert two.indices[0, 0] == 0
    assert two.depth[0, 0] == -1


def test_glass_behind_a_solid_voxel_is_hidden() -> None:
    image = ortho_view(_line(SOLID, GLASS), View.FRONT, CLEAR)
    assert image.glass.shape[0] == 0
    assert image.indices[0, 0] == SOLID


def test_without_see_through_indices_glass_is_opaque() -> None:
    image = ortho_view(_line(0, GLASS, 0, SOLID), View.FRONT)
    assert image.indices[0, 0] == GLASS
    assert image.glass.shape[0] == 0
    assert image.surface is None


def test_layers_follow_the_view_orientation() -> None:
    grid = new_grid((3, 2, 4))
    grid[2, 0, 0] = GLASS  # bottom, right side (+X), front
    grid[2, 0, 3] = SOLID
    image = ortho_view(grid, View.FRONT, CLEAR)
    # The front view shows +X on the image left, the bottom row last.
    assert np.argwhere(image.glass[0] == GLASS).tolist() == [[1, 0]]
    assert np.argwhere(image.indices == SOLID).tolist() == [[1, 0]]


def test_shade_tints_what_is_behind_each_layer() -> None:
    image = ortho_view(_line(GLASS, 0, SOLID), View.FRONT, CLEAR)
    rgb = shade(image, COLORS, 3)
    solid = COLORS[SOLID] * (1 - 0.35 * 2 / 2)  # depth shading of the far voxel
    assert rgb[0, 0].tolist() == np.rint(_mix(solid, COLORS[GLASS])).tolist()
    image = ortho_view(_line(GLASS, 0, OTHER_GLASS), View.FRONT, CLEAR)
    rgb = shade(image, COLORS, 3)
    expected = _mix(_mix(np.array(BACKGROUND, dtype=float), COLORS[OTHER_GLASS]), COLORS[GLASS])
    assert rgb[0, 0].tolist() == np.rint(expected).tolist()


def test_window_outline_follows_the_glass_surface() -> None:
    grid = new_grid((2, 1, 3))
    grid[:, 0, 2] = SOLID
    grid[0, 0, 0] = GLASS  # a pane in front of the left half only
    vertical, _ = edges(ortho_view(grid, View.FRONT, CLEAR))
    assert vertical.tolist() == [[True]]
    vertical, _ = edges(ortho_view(grid, View.FRONT))
    assert vertical.tolist() == [[True]]
    flat = new_grid((2, 1, 1))
    flat[0, 0, 0], flat[1, 0, 0] = GLASS, SOLID
    vertical, _ = edges(ortho_view(flat, View.FRONT, CLEAR))
    assert vertical.tolist() == [[False]]  # flush pane: no step


@pytest.mark.parametrize("bad", [0, 256, -1, True, 1.5, "2"])
def test_see_through_indices_are_checked(bad: object) -> None:
    with pytest.raises(RenderError, match="see-through"):
        see_through_mask([bad])  # type: ignore[list-item]  # runtime check of bad input


def test_see_through_mask_marks_the_indices() -> None:
    mask = see_through_mask([GLASS, int(np.uint8(OTHER_GLASS))])
    assert mask.shape == (256,)
    assert np.flatnonzero(mask).tolist() == [GLASS, OTHER_GLASS]


def _face_center(
    view: View, cell: tuple[int, int, int], shape: tuple[int, int, int]
) -> tuple[int, int]:
    """Pixel at the center of the camera-facing -Z face of a cell, in an ISO_FRONT image."""
    frame = iso_frame(shape, view, 10)
    point = np.array([[cell[0] + 0.5, cell[1] + 0.5, cell[2]]], dtype=np.float64)
    x, y = frame.to_pixels(point)[0]
    return round(float(x)), round(float(y))


def _rgb(image: Image.Image, at: tuple[int, int]) -> np.ndarray:
    pixel: np.ndarray = np.asarray(image)[at[1], at[0]].astype(float)
    return pixel


def test_iso_glass_face_blends_over_the_solid_behind() -> None:
    grid = new_grid((3, 3, 3))
    grid[:, :, 1:] = SOLID  # a wall behind the pane
    grid[1, 1, 0] = GLASS
    shape = (3, 3, 3)
    # Seen through the center of the pane's front face, the camera ray meets the wall's front
    # face: with see-through glass the pixel is the wall tinted by the glass.
    at = _face_center(View.ISO_FRONT, (1, 1, 0), shape)
    opaque = _rgb(iso_image(grid, COLORS, View.ISO_FRONT, 10), at)
    clear = _rgb(iso_image(grid, COLORS, View.ISO_FRONT, 10, CLEAR), at)
    front = FACE_LIGHT[2]
    assert opaque.tolist() == np.rint(COLORS[GLASS] * front).tolist()
    expected = _mix(np.rint(COLORS[SOLID] * front), np.rint(COLORS[GLASS] * front))
    assert clear == pytest.approx(expected, abs=1)


def test_iso_glass_against_glass_draws_no_inner_face() -> None:
    one = new_grid((1, 1, 1))
    one[0, 0, 0] = GLASS
    two = new_grid((1, 1, 2))
    two[0, 0, :] = GLASS
    at_one = _face_center(View.ISO_FRONT, (0, 0, 0), (1, 1, 1))
    at_two = _face_center(View.ISO_FRONT, (0, 0, 0), (1, 1, 2))
    # The visible front face of a thicker pane is tinted once, like a 1-voxel pane, because the
    # face between the two glass voxels is not drawn.
    single = _rgb(iso_image(one, COLORS, View.ISO_FRONT, 10, CLEAR), at_one)
    double = _rgb(iso_image(two, COLORS, View.ISO_FRONT, 10, CLEAR), at_two)
    assert single.tolist() == double.tolist()


def test_preview_sheet_draws_glass_see_through() -> None:
    grid = new_grid((8, 6, 12))
    grid[:, :, 8:] = SOLID
    grid[:, :, 2] = GLASS
    plain = np.asarray(preview_sheet(grid, COLORS))
    clear = np.asarray(preview_sheet(grid, COLORS, annotations=Annotations(see_through=CLEAR)))
    assert plain.shape == clear.shape
    assert not np.array_equal(plain, clear)
    with pytest.raises(RenderError):
        preview_sheet(grid, COLORS, annotations=Annotations(see_through=[300]))


def test_iso_small_scale_and_empty_grid() -> None:
    grid = new_grid((2, 2, 2))
    grid[0, 0, 0] = GLASS
    grid[1, 1, 1] = SOLID
    small = iso_image(grid, COLORS, View.ISO_FRONT, 3, CLEAR)  # no outlines below scale 5
    assert small.size == iso_frame((2, 2, 2), View.ISO_FRONT, 3).size
    empty = np.asarray(iso_image(new_grid((2, 2, 2)), COLORS, View.ISO_FRONT, 3, CLEAR))
    assert (empty == np.array(BACKGROUND, dtype=np.uint8)).all()
