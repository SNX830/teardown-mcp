"""Orthographic views of a grid, computed with numpy (one pixel per voxel).

Each view is what a camera outside the model sees, looking straight at one side, with Y up on
screen (top and bottom views: the vehicle front, -Z, at the top of the image). Views are true
views, never mirrored: in the front view the model's right side (+X) appears on the LEFT of the
image, as when facing a car.

See-through voxels (glass, as it looks in game: docs/TEARDOWN_REFERENCE.md §3) are drawn as
tinted layers over what lies behind them.
"""

from collections.abc import Collection
from dataclasses import dataclass, field
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
#: Opacity of one layer of see-through voxels in previews.
GLASS_ALPHA: Final = 0.35
PALETTE_SIZE: Final = 256


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
        indices: ``(height, width)`` palette index of the first voxel that is not see-through,
            0 where there is none.
        depth: ``(height, width)`` distance in voxels from the camera side of the grid to that
            voxel, -1 where there is none.
        columns: Grid index (along ``orientation.right``) of each image column.
        rows: Grid index (along ``orientation.up``) of each image row, top row first.
        glass: ``(layers, height, width)`` palette indices of the see-through layers in front
            of that voxel, nearest first (0 = no layer): a layer is a run of consecutive
            see-through voxels along the line of sight. No layers without see-through voxels.
        surface: ``(height, width)`` depth of the first voxel of any kind, -1 where empty, or
            ``None`` when there is no see-through voxel (then it equals ``depth``).
    """

    view: View
    indices: npt.NDArray[np.uint8]
    depth: npt.NDArray[np.int32]
    columns: npt.NDArray[np.int64]
    rows: npt.NDArray[np.int64]
    glass: npt.NDArray[np.uint8] = field(
        default_factory=lambda: np.zeros((0, 0, 0), dtype=np.uint8)
    )
    surface: npt.NDArray[np.int32] | None = None

    @property
    def outline_depth(self) -> npt.NDArray[np.int32]:
        """Depth used for outlines: the first voxel of any kind."""
        return self.depth if self.surface is None else self.surface

    @property
    def orientation(self) -> Orientation:
        """Axis mapping of this view."""
        return ORIENTATIONS[self.view]


def see_through_mask(see_through: Collection[int]) -> npt.NDArray[np.bool_]:
    """``(256,)`` table: whether each palette index is drawn see-through.

    Raises:
        RenderError: For an index outside 1..255.
    """
    table = np.zeros(PALETTE_SIZE, dtype=np.bool_)
    for index in see_through:
        if isinstance(index, bool) or not isinstance(index, int | np.integer):
            raise RenderError(f"see-through palette indices must be integers, got {index!r}")
        if not 0 < index < PALETTE_SIZE:
            raise RenderError(f"see-through palette indices must be 1..255, got {index}")
        table[int(index)] = True
    return table


def ortho_view(grid: Grid, view: View, see_through: Collection[int] = ()) -> ViewImage:
    """Compute the visible voxel of every pixel of an orthographic view.

    Args:
        grid: The model.
        view: An orthographic view.
        see_through: Palette indices drawn see-through (glass); none by default.

    Raises:
        RenderError: For an unknown view, a 3/4 view (use ``buildup.render.iso``) or a bad
            see-through index.
    """
    clear = see_through_mask(see_through)
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
    glassy = clear[arr]
    solid = (arr != EMPTY) & ~glassy
    indices, depth = _first(arr, solid)
    surface = None
    glass = np.zeros((0, *depth.shape), dtype=np.uint8)
    if glassy.any():
        surface = _first(arr, arr != EMPTY)[1]
        glass = _glass_layers(arr, glassy, depth)
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
        glass=np.transpose(glass, (0, 2, 1))[:, ::-1, :].copy(),
        surface=None if surface is None else surface.T[::-1, :].copy(),
    )


def _first(
    arr: Grid, mask: npt.NDArray[np.bool_]
) -> tuple[npt.NDArray[np.uint8], npt.NDArray[np.int32]]:
    """Palette index and depth of the first ``mask`` cell along the last axis (0, -1 if none)."""
    hit = mask.any(axis=2)
    first = np.argmax(mask, axis=2)
    indices = np.take_along_axis(arr, first[:, :, None], axis=2)[:, :, 0]
    return (
        np.where(hit, indices, 0).astype(np.uint8),
        np.where(hit, first, -1).astype(np.int32),
    )


def _glass_layers(
    arr: Grid, glassy: npt.NDArray[np.bool_], depth: npt.NDArray[np.int32]
) -> npt.NDArray[np.uint8]:
    """See-through layers in front of ``depth`` (all of them where it is -1), nearest first."""
    n = arr.shape[2]
    limit = np.where(depth < 0, n, depth)
    in_front = np.arange(n)[None, None, :] < limit[:, :, None]
    before = np.zeros_like(glassy)
    before[:, :, 1:] = glassy[:, :, :-1]
    starts = glassy & ~before & in_front
    count = int(starts.sum(axis=2).max())
    layers = np.zeros((count, arr.shape[0], arr.shape[1]), dtype=np.uint8)
    seen = np.zeros(depth.shape, dtype=np.int64)
    for d in range(n):
        here = starts[:, :, d]
        if here.any():
            rows, cols = np.nonzero(here)
            layers[seen[rows, cols], rows, cols] = arr[rows, cols, d]
            seen[here] += 1
    return layers


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
        ``(height, width, 3)`` RGB array; empty pixels get ``BACKGROUND``; each see-through
        layer tints what lies behind it (opacity ``GLASS_ALPHA``).
    """
    table = color_table(colors)
    rgb = table[image.indices]
    factor = 1.0 - DEPTH_SHADE * np.clip(image.depth, 0, None) / max(1, grid_depth - 1)
    rgb = rgb * factor[:, :, None]
    rgb[image.depth < 0] = BACKGROUND
    for layer in image.glass[::-1]:  # farthest layer first
        tinted = rgb * (1.0 - GLASS_ALPHA) + table[layer] * GLASS_ALPHA
        rgb = np.where((layer != EMPTY)[:, :, None], tinted, rgb)
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8)


def edges(image: ViewImage) -> tuple[npt.NDArray[np.bool_], npt.NDArray[np.bool_]]:
    """Where to draw outlines between neighbouring pixels.

    Returns:
        ``vertical`` of shape ``(height, width - 1)``: a line between columns ``c`` and ``c + 1``;
        ``horizontal`` of shape ``(height - 1, width)``: a line between rows ``r`` and ``r + 1``.
        A line is drawn where one side is empty and the other is not, or where the visible
        voxels are more than one voxel apart in depth (a step in the surface). See-through
        voxels count as surface here, so windows keep their outline.
    """
    d = image.outline_depth

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
