import numpy as np
import pytest

from buildup.render import View, as_view, ortho_view
from buildup.render.views import BACKGROUND, RenderError, edges, shade, upscale
from buildup.voxcore import VoxcoreError, new_grid

A, B = 1, 2


def _two_voxels() -> np.ndarray:
    """A at the bottom-right-front corner (x=2, y=0, z=0); B at top-left-back (0, 1, 3)."""
    grid = new_grid((3, 2, 4))
    grid[2, 0, 0] = A
    grid[0, 1, 3] = B
    return grid


def _where(image: np.ndarray, value: int) -> tuple[int, int]:
    found = np.argwhere(image == value)
    assert len(found) == 1
    return int(found[0][0]), int(found[0][1])


# (view, (row, column, depth) of A, (row, column, depth) of B, image shape)
CASES = [
    # Front: camera at -Z; +X (right side) on the image LEFT, as when facing a car.
    (View.FRONT, (1, 0, 0), (0, 2, 3), (2, 3)),
    (View.BACK, (1, 2, 3), (0, 0, 0), (2, 3)),
    # Left: camera at -X; the front (-Z) on the image left.
    (View.LEFT, (1, 0, 2), (0, 3, 0), (2, 4)),
    (View.RIGHT, (1, 3, 0), (0, 0, 2), (2, 4)),
    # Top: camera above; front at the top of the image, +X to the right.
    (View.TOP, (0, 2, 1), (3, 0, 0), (4, 3)),
    (View.BOTTOM, (0, 0, 0), (3, 2, 1), (4, 3)),
]


@pytest.mark.parametrize(("view", "a", "b", "shape"), CASES)
def test_views_are_true_views(
    view: View,
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    shape: tuple[int, int],
) -> None:
    image = ortho_view(_two_voxels(), view)
    assert image.indices.shape == shape
    for value, (row, column, depth) in ((A, a), (B, b)):
        assert _where(image.indices, value) == (row, column)
        assert image.depth[row, column] == depth
    assert np.all((image.indices == 0) == (image.depth == -1))


@pytest.mark.parametrize(("view", "a", "b", "shape"), CASES)
def test_rows_and_columns_name_grid_indices(
    view: View,
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    shape: tuple[int, int],
) -> None:
    grid = _two_voxels()
    image = ortho_view(grid, view)
    o = image.orientation
    for cell in ((2, 0, 0), (0, 1, 3)):
        row, column = _where(image.indices, int(grid[cell]))
        assert image.columns[column] == cell[o.right]
        assert image.rows[row] == cell[o.up]


def test_first_voxel_hides_the_ones_behind() -> None:
    grid = new_grid((1, 1, 3))
    grid[0, 0, 1] = A
    grid[0, 0, 2] = B
    assert ortho_view(grid, View.FRONT).indices[0, 0] == A
    assert ortho_view(grid, View.BACK).indices[0, 0] == B


def test_iso_view_is_not_an_ortho_view() -> None:
    with pytest.raises(RenderError, match="3/4"):
        ortho_view(_two_voxels(), View.ISO_FRONT)


def test_shade_background_and_depth() -> None:
    grid = new_grid((2, 1, 3))
    grid[0, 0, 0] = A
    grid[1, 0, 2] = A
    colors = np.zeros((256, 3), dtype=np.uint8)
    colors[A] = (200, 100, 50)
    image = ortho_view(grid, View.FRONT)
    rgb = shade(image, colors, grid.shape[2])
    near = rgb[0, image.columns.tolist().index(0)]
    far = rgb[0, image.columns.tolist().index(1)]
    assert near.tolist() == [200, 100, 50]
    assert far.tolist() == [130, 65, 32]  # depth 2 of 2: darkened by 35 %
    grid[1, 0, 2] = 0
    empty = shade(ortho_view(grid, View.FRONT), colors, 3)
    assert empty[0, 0].tolist() == list(BACKGROUND)


def test_edges_mark_silhouette_and_steps() -> None:
    grid = new_grid((4, 3, 1))
    grid[0, 2, 0] = A  # seen from above at depth 0
    grid[1, 2, 0] = A  # depth 0 too: no line between them
    grid[2, 0, 0] = A  # depth 2: a step down
    image = ortho_view(grid, View.TOP)  # one row: x = 0, 1, 2, 3 from left to right
    assert image.depth.tolist() == [[0, 0, 2, -1]]
    vertical, horizontal = edges(image)
    assert vertical.tolist() == [[False, True, True]]  # step, then silhouette
    assert horizontal.shape == (0, 4)


def test_upscale() -> None:
    grid = new_grid((2, 1, 1))
    grid[0, 0, 0] = A
    colors = np.full((256, 3), 255, dtype=np.uint8)
    image = ortho_view(grid, View.FRONT)
    rgb = shade(image, colors, 1)
    small = upscale(rgb, image, 2)
    assert small.shape == (2, 4, 3)
    big = upscale(rgb, image, 4)
    assert big.shape == (4, 8, 3)
    # Front view: x = 1 (empty) is the left column, x = 0 (filled) the right one.
    assert big[0, 0].tolist() == list(BACKGROUND)
    assert big[0, 7].tolist() == [255, 255, 255]
    # A 2-pixel outline straddles the boundary between the two columns.
    assert big[0, 3].tolist() != list(BACKGROUND)
    assert big[0, 4].tolist() != [255, 255, 255]
    assert big[0, 5].tolist() == [255, 255, 255]
    with pytest.raises(ValueError, match="scale"):
        upscale(rgb, image, 0)


def test_view_names_are_validated() -> None:
    assert as_view("front") is View.FRONT
    with pytest.raises(RenderError, match="unknown view 'side'"):
        as_view("side")
    with pytest.raises(RenderError, match="must be a name"):
        as_view(3)
    assert issubclass(RenderError, VoxcoreError)  # tools catch one error type


def test_color_table_is_validated() -> None:
    grid = _two_voxels()
    image = ortho_view(grid, View.FRONT)
    with pytest.raises(RenderError, match="256"):
        shade(image, np.zeros((10, 3), dtype=np.uint8), 4)
