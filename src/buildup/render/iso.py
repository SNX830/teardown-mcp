"""3/4 (isometric) views of a grid, drawn face by face with Pillow.

The camera looks from a corner of the model (for ``ISO_FRONT``: from the front, the right and
above, so the -Z, +X and +Y faces are visible). Only voxel faces that touch an empty cell are
drawn, from the farthest to the nearest (painter's algorithm, exact for unit cubes seen along a
cube diagonal).
"""

from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw

from buildup.render.views import BACKGROUND, RenderError, View, as_view, color_table
from buildup.voxcore import EMPTY, Grid
from buildup.voxcore.grid import check_grid
from buildup.voxcore.ops import neighbor

#: Camera direction (from the model towards the camera) of each 3/4 view.
CAMERAS: Final[dict[View, tuple[int, int, int]]] = {
    View.ISO_FRONT: (1, 1, -1),
    View.ISO_BACK: (-1, 1, 1),
}
#: Brightness of faces by the axis of their normal (X, Y, Z): the top is lit, the sides darker.
FACE_LIGHT: Final = (0.78, 1.0, 0.62)
OUTLINE_DARKEN: Final = 0.7
#: Unit square corners of a face, per normal axis, as offsets from the face's base corner.
_FACE_CORNERS: Final[dict[int, tuple[tuple[int, int, int], ...]]] = {
    0: ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)),
    1: ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
    2: ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)),
}


@dataclass(frozen=True)
class Projection:
    """Screen axes of a 3/4 view: a point ``p`` (voxels) goes to ``(p . right, -(p . up))``."""

    camera: tuple[int, int, int]
    right: npt.NDArray[np.float64]
    up: npt.NDArray[np.float64]

    def project(self, points: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Screen coordinates (x right, y down) of ``(n, 3)`` points, in voxel units."""
        return np.stack([points @ self.right, -(points @ self.up)], axis=-1)


def projection(view: View) -> Projection:
    """Screen axes for a 3/4 view.

    Raises:
        RenderError: For an unknown view or an orthographic view.
    """
    view = as_view(view)
    if view not in CAMERAS:
        raise RenderError(f"{view.value} is an orthographic view, not a 3/4 view")
    camera = CAMERAS[view]
    c = np.array(camera, dtype=np.float64)
    forward = -c / np.linalg.norm(c)
    right = np.cross(forward, (0.0, 1.0, 0.0))
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return Projection(camera, right, up)


@dataclass(frozen=True)
class IsoFrame:
    """Placement of a 3/4 view in its image.

    Attributes:
        projection: Screen axes.
        scale: Pixels per voxel edge.
        offset: Subtracted from scaled screen coordinates to get pixel coordinates.
        size: Image size in pixels (width, height).
    """

    projection: Projection
    scale: int
    offset: npt.NDArray[np.float64]
    size: tuple[int, int]

    def to_pixels(self, points: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Pixel coordinates of ``(n, 3)`` grid points (voxel units, grid frame)."""
        return self.projection.project(points) * self.scale - self.offset


def iso_frame(shape: tuple[int, int, int], view: View, scale: int) -> IsoFrame:
    """Image frame of a 3/4 view of a grid of ``shape``: the grid box plus a 2-pixel margin.

    Raises:
        RenderError: If ``scale`` is below 1.
    """
    if scale < 1:
        raise RenderError(f"scale must be >= 1, got {scale}")
    proj = projection(view)
    corners = np.array(
        [[x, y, z] for x in (0, shape[0]) for y in (0, shape[1]) for z in (0, shape[2])],
        dtype=np.float64,
    )
    screen = proj.project(corners) * scale
    low = screen.min(axis=0) - 2
    size = np.ceil(screen.max(axis=0) - low + 2).astype(int)
    return IsoFrame(proj, scale, low, (int(size[0]), int(size[1])))


def iso_image(grid: Grid, colors: npt.NDArray[np.uint8], view: View, scale: int) -> Image.Image:
    """Draw a 3/4 view.

    Args:
        grid: The model.
        colors: ``(256, 3)`` or ``(256, 4)`` RGB(A) table indexed by palette index.
        view: ``View.ISO_FRONT`` or ``View.ISO_BACK``.
        scale: Pixels per voxel edge (screen length of a voxel edge seen face on).

    Returns:
        An RGB image just large enough for the whole grid box, plus a 2-pixel margin.
    """
    grid = check_grid(grid)
    frame = iso_frame((grid.shape[0], grid.shape[1], grid.shape[2]), view, scale)
    proj, low = frame.projection, frame.offset
    image = Image.new("RGB", frame.size, BACKGROUND)
    draw = ImageDraw.Draw(image)
    table = color_table(colors)

    filled = grid != EMPTY
    faces: list[tuple[float, int, int, npt.NDArray[np.int64]]] = []
    for axis, sign in enumerate(proj.camera):
        exposed = filled & ~neighbor(filled, axis, sign)
        cells = np.argwhere(exposed)
        if len(cells) == 0:
            continue
        depth = (cells + 0.5) @ np.array(proj.camera, dtype=np.float64)
        faces.extend((float(d), axis, sign, cell) for d, cell in zip(depth, cells, strict=True))
    faces.sort(key=lambda f: (f[0], f[1]))

    outline = scale >= 5
    offsets = {a: np.array(_FACE_CORNERS[a], dtype=np.float64) for a in range(3)}
    for _, axis, sign, cell in faces:
        base = cell.astype(np.float64)
        if sign > 0:
            base[axis] += 1.0
        polygon = proj.project(base + offsets[axis]) * scale - low
        color = table[grid[tuple(cell)]] * FACE_LIGHT[axis]
        fill = tuple(int(v) for v in np.clip(np.rint(color), 0, 255))
        points = [(float(x), float(y)) for x, y in polygon]
        if outline:
            line = tuple(int(v * OUTLINE_DARKEN) for v in fill)
            draw.polygon(points, fill=fill, outline=line)
        else:
            draw.polygon(points, fill=fill)
    return image
