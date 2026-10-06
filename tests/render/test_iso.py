import numpy as np
import pytest
from PIL import Image

from buildup.render import View, iso_image
from buildup.render.iso import FACE_LIGHT, iso_frame, projection
from buildup.render.views import BACKGROUND, RenderError
from buildup.voxcore import new_grid

A, B = 1, 2
COLORS = np.zeros((256, 3), dtype=np.uint8)
COLORS[A] = (200, 100, 50)
COLORS[B] = (40, 160, 220)


def _rgb(image: Image.Image, at: tuple[int, int]) -> list[int]:
    """Color of the pixel at (x, y)."""
    return [int(v) for v in np.asarray(image)[at[1], at[0]]]


def _pixel(image_point: np.ndarray) -> tuple[int, int]:
    return round(float(image_point[0])), round(float(image_point[1]))


@pytest.mark.parametrize("view", [View.ISO_FRONT, View.ISO_BACK])
def test_projection_axes_are_orthonormal(view: View) -> None:
    proj = projection(view)
    camera = np.array(proj.camera, dtype=np.float64)
    assert np.dot(proj.right, proj.right) == pytest.approx(1)
    assert np.dot(proj.up, proj.up) == pytest.approx(1)
    assert np.dot(proj.right, proj.up) == pytest.approx(0)
    assert np.dot(proj.right, camera) == pytest.approx(0)
    assert proj.up[1] > 0  # world up points up on screen


def test_iso_front_sees_front_right_and_top() -> None:
    proj = projection(View.ISO_FRONT)
    assert proj.camera == (1, 1, -1)
    # +X goes to the screen left (the camera is on the right side looking back at the model).
    assert proj.project(np.array([[1.0, 0, 0]]))[0][0] < 0
    # -Z (front) goes to the screen right.
    assert proj.project(np.array([[0, 0, -1.0]]))[0][0] > 0


@pytest.mark.parametrize("view", [View.ISO_FRONT, View.ISO_BACK])
def test_single_voxel_faces_are_lit_by_orientation(view: View) -> None:
    grid = new_grid((1, 1, 1))
    grid[0, 0, 0] = A
    scale = 40
    image = iso_image(grid, COLORS, view, scale)
    frame = iso_frame((1, 1, 1), view, scale)
    assert image.size == frame.size
    camera = projection(view).camera
    for axis in range(3):
        center = np.full(3, 0.5)
        center[axis] = 1.0 if camera[axis] > 0 else 0.0
        x, y = _pixel(frame.to_pixels(center[None, :])[0])
        expected = np.rint(np.array(COLORS[A], dtype=np.float64) * FACE_LIGHT[axis])
        assert _rgb(image, (x, y)) == expected.astype(int).tolist()
    assert _rgb(image, (0, 0)) == list(BACKGROUND)


def test_nearer_voxel_is_drawn_over_farther_one() -> None:
    # Seen from (1, 1, -1), cell (1, 1, 0) is exactly in front of cell (0, 0, 1).
    grid = new_grid((2, 2, 2))
    grid[0, 0, 1] = A
    scale = 30
    frame = iso_frame((2, 2, 2), View.ISO_FRONT, scale)
    near_top = np.array([[1.5, 2.0, 0.5]])  # top face center of the near cell
    point = _pixel(frame.to_pixels(near_top)[0])
    alone = iso_image(grid, COLORS, View.ISO_FRONT, scale)
    assert _rgb(alone, point) != list(BACKGROUND)  # the far voxel covers this pixel
    grid[1, 1, 0] = B
    both = iso_image(grid, COLORS, View.ISO_FRONT, scale)
    expected = np.rint(np.array(COLORS[B], dtype=np.float64) * FACE_LIGHT[1]).astype(int)
    assert _rgb(both, point) == expected.tolist()


def test_hidden_faces_are_not_needed() -> None:
    # A full block and its hollow shell look the same from outside.
    solid = np.full((4, 4, 4), A, dtype=np.uint8)
    shell = solid.copy()
    shell[1:3, 1:3, 1:3] = 0
    first = np.asarray(iso_image(solid, COLORS, View.ISO_BACK, 6))
    second = np.asarray(iso_image(shell, COLORS, View.ISO_BACK, 6))
    assert np.array_equal(first, second)


def test_bad_arguments() -> None:
    grid = new_grid((1, 1, 1))
    with pytest.raises(ValueError, match="scale"):
        iso_image(grid, COLORS, View.ISO_FRONT, 0)
    with pytest.raises(RenderError, match="orthographic"):
        projection(View.FRONT)


def test_iso_back_screen_axes() -> None:
    proj = projection(View.ISO_BACK)
    assert proj.camera == (-1, 1, 1)
    # Seen from the back left and above: +X and +Z both run to the right of the screen.
    assert proj.right == pytest.approx(np.array([1, 0, 1]) / np.sqrt(2))
    assert proj.up == pytest.approx(np.array([1, 2, -1]) / np.sqrt(6))


@pytest.mark.parametrize("view", [View.ISO_FRONT, View.ISO_BACK])
def test_iso_views_are_not_mirrored(view: View) -> None:
    # Screen right x screen up must point towards the camera (a right-handed screen frame).
    proj = projection(view)
    camera = np.array(proj.camera, dtype=np.float64)
    assert np.cross(proj.right, proj.up) == pytest.approx(camera / np.linalg.norm(camera))
