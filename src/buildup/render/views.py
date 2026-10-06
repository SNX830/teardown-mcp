"""Orthographic views of a grid, computed with numpy (one pixel per voxel).

Each view is what a camera outside the model sees, looking straight at one side, with Y up on
screen (top and bottom views: the vehicle front, -Z, at the top of the image). Views are true
views, never mirrored: in the front view the model's right side (+X) appears on the LEFT of the
image, as when facing a car.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

import numpy as np
import numpy.typing as npt

from buildup.voxcore import EMPTY, Grid, VoxcoreError
from buildup.voxcore.grid import check_grid

RGB = npt.NDArray[np.uint8]
BACKGROUND: Final = (236, 236, 232)
EDGE_DARKEN: Final = 0.55
DEPTH_SHADE: Final = 0.35


class RenderError(VoxcoreError):
    """Invalid argument for a render function (a ``VoxcoreError``: tools catch one type)."""


def meters(value_vox: float) -> str:
    """Format a length in voxels as meters (1 voxel = 0.1 m), e.g. ``-12`` -> ``"-1.2"``."""
    text = f"{value_vox / 10:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


class View(StrEnum):
    """Camera positions. Orthographic views look along one axis; ``iso_*`` are 3/4 views."""

    FRONT = "front"  # camera on the -Z side (vehicle front), looking towards +Z
    BACK = "back"  # camera on the +Z side, looking towards -Z
    LEFT = "left"  # camera on the -X side (vehicle left)
    RIGHT = "right"  # camera on the +X side
    TOP = "top"  # camera above, front (-Z) at the top of the image
    BOTTOM = "bottom"  # camera below, front (-Z) at the top of the image
    ISO_FRONT = "iso_front"  # 3/4 view from front, right and above
    ISO_BACK = "iso_back"  # 3/4 view from back, left and above


def as_view(value: object) -> View:
    """Validate a view name such as ``"front"`` or ``"iso_back"``.

    Raises:
        RenderError: For anything else, listing the valid names.
    """
    names = ", ".join(v.value for v in View)
    if not isinstance(value, str):
        raise RenderError(f"view must be a name, got {value!r}; use one of: {names}")
    try:
        return View(value)
    except ValueError:
        raise RenderError(f"unknown view {value!r}; use one of: {names}") from None


@dataclass(frozen=True)
class Orientation:
    """How an orthographic view maps grid axes to the image.

    Attributes:
        depth: Grid axis the camera looks along; ``depth_sign`` +1 if the camera is on the low
            side (looks towards +axis), -1 if on the high side.
        right: Grid axis that runs to the right of the image, ``right_sign`` +1 if it grows to
            the right.
        up: Grid axis that runs up the image, ``up_sign`` +1 if it grows upwards.
        seen_from: Plain description of the camera position.
    """

    depth: int
    depth_sign: int
    right: int
    right_sign: int
    up: int
    up_sign: int
    seen_from: str


ORIENTATIONS: Final[dict[View, Orientation]] = {
    View.FRONT: Orientation(2, 1, 0, -1, 1, 1, "from the front (-Z)"),
    View.BACK: Orientation(2, -1, 0, 1, 1, 1, "from the back (+Z)"),
    View.LEFT: Orientation(0, 1, 2, 1, 1, 1, "from the left (-X)"),
    View.RIGHT: Orientation(0, -1, 2, -1, 1, 1, "from the right (+X)"),
    View.TOP: Orientation(1, -1, 0, 1, 2, -1, "from above (+Y), front at the top"),
    View.BOTTOM: Orientation(1, 1, 0, -1, 2, -1, "from below (-Y), front at the top"),
}


@dataclass(frozen=True)
class ViewImage:
    """An orthographic view at one pixel per voxel.

    Attributes:
        view: Which view.
        indices: ``(height, width)`` palette index of the visible voxel, 0 where empty.
        depth: ``(height, width)`` distance in voxels from the camera side of the grid to the
            visible voxel, -1 where empty.
        columns: Grid index (along ``orientation.right``) of each image column.
        rows: Grid index (along ``orientation.up``) of each image row, top row first.
    """

    view: View
    indices: npt.NDArray[np.uint8]
    depth: npt.NDArray[np.int32]
    columns: npt.NDArray[np.int64]
    rows: npt.NDArray[np.int64]

    @property
    def orientation(self) -> Orientation:
        """Axis mapping of this view."""
        return ORIENTATIONS[self.view]


def ortho_view(grid: Grid, view: View) -> ViewImage:
    """Compute the visible voxel of every pixel of an orthographic view.

    Raises:
        RenderError: For an unknown view or a 3/4 view (use ``buildup.render.iso``).
    """
    view = as_view(view)
    if view not in ORIENTATIONS:
        raise RenderError(f"{view.value} is a 3/4 view, not an orthographic view")
    o = ORIENTATIONS[view]
    arr = np.transpose(check_grid(grid), (o.right, o.up, o.depth))
    if o.right_sign < 0:
        arr = arr[::-1, :, :]
    if o.up_sign < 0:
        arr = arr[:, ::-1, :]
    if o.depth_sign < 0:
        arr = arr[:, :, ::-1]
    filled = arr != EMPTY
    hit = filled.any(axis=2)
    first = np.argmax(filled, axis=2)
    indices = np.take_along_axis(arr, first[:, :, None], axis=2)[:, :, 0]
    indices = np.where(hit, indices, 0).astype(np.uint8)
    depth = np.where(hit, first, -1).astype(np.int32)
    # Image layout: rows from top to bottom (up axis reversed), columns left to right.
    n_right, n_up = arr.shape[0], arr.shape[1]
    right_index = np.arange(n_right) if o.right_sign > 0 else np.arange(n_right)[::-1]
    up_index = np.arange(n_up) if o.up_sign > 0 else np.arange(n_up)[::-1]
    return ViewImage(
        view=View(view),
        indices=indices.T[::-1, :].copy(),
        depth=depth.T[::-1, :].copy(),
        columns=right_index.astype(np.int64),
        rows=up_index[::-1].astype(np.int64),
    )


def color_table(colors: object) -> npt.NDArray[np.float64]:
    """Validate a ``(256, 3)`` or ``(256, 4)`` color table and return its RGB part as floats.

    Raises:
        RenderError: For any other shape.
    """
    table = np.asarray(colors)
    if table.ndim != 2 or table.shape[0] != 256 or table.shape[1] not in (3, 4):
        raise RenderError(
            f"colors must be a (256, 3) or (256, 4) table (Palette.rgba()), got shape {table.shape}"
        )
    return table[:, :3].astype(np.float64)


def shade(image: ViewImage, colors: npt.NDArray[np.uint8], grid_depth: int) -> RGB:
    """Color a view: palette colors, darker with depth so steps read as relief.

    Args:
        image: The view.
        colors: ``(256, 3)`` or ``(256, 4)`` RGB(A) table indexed by palette index.
        grid_depth: Grid size along the view axis (for the depth shading range).

    Returns:
        ``(height, width, 3)`` RGB array; empty pixels get ``BACKGROUND``.
    """
    table = color_table(colors)
    rgb = table[image.indices]
    factor = 1.0 - DEPTH_SHADE * np.clip(image.depth, 0, None) / max(1, grid_depth - 1)
    rgb = rgb * factor[:, :, None]
    rgb[image.depth < 0] = BACKGROUND
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8)


def edges(image: ViewImage) -> tuple[npt.NDArray[np.bool_], npt.NDArray[np.bool_]]:
    """Where to draw outlines between neighbouring pixels.

    Returns:
        ``vertical`` of shape ``(height, width - 1)``: a line between columns ``c`` and ``c + 1``;
        ``horizontal`` of shape ``(height - 1, width)``: a line between rows ``r`` and ``r + 1``.
        A line is drawn where one side is empty and the other is not, or where the visible
        voxels are more than one voxel apart in depth (a step in the surface).
    """
    d = image.depth

    def boundary(a: npt.NDArray[np.int32], b: npt.NDArray[np.int32]) -> npt.NDArray[np.bool_]:
        fa, fb = a >= 0, b >= 0
        line: npt.NDArray[np.bool_] = (fa != fb) | (fa & fb & (np.abs(a - b) > 1))
        return line

    return boundary(d[:, :-1], d[:, 1:]), boundary(d[:-1, :], d[1:, :])


def upscale(rgb: RGB, image: ViewImage, scale: int) -> RGB:
    """Enlarge a shaded view to ``scale`` pixels per voxel and draw the outlines (1 pixel)."""
    if scale < 1:
        raise RenderError(f"scale must be >= 1, got {scale}")
    big = np.repeat(np.repeat(rgb, scale, axis=0), scale, axis=1)
    if scale < 3:  # outlines would hide the colors
        return big
    vertical, horizontal = edges(image)
    dark = big.astype(np.float64)
    for r, c in np.argwhere(vertical):
        x = (c + 1) * scale - 1
        dark[r * scale : (r + 1) * scale, x : x + 2] *= EDGE_DARKEN
    for r, c in np.argwhere(horizontal):
        y = (r + 1) * scale - 1
        dark[y : y + 2, c * scale : (c + 1) * scale] *= EDGE_DARKEN
    return np.clip(np.rint(dark), 0, 255).astype(np.uint8)
