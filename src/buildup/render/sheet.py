"""Preview sheet: several annotated views of a model on one image, for an AI that cannot see it.

Orthographic panels carry rulers labelled in meters with Teardown-frame coordinates, and say which
side of the model each image edge shows. 3/4 panels carry an axis gizmo (1 m, or 0.5 m at large
scales). Optional markers
(labelled points such as wheel centers) are drawn on every panel.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw, ImageFont

from buildup.render.iso import CAMERAS, iso_frame, iso_image
from buildup.render.views import (
    BACKGROUND,
    ORIENTATIONS,
    RenderError,
    View,
    as_view,
    color_table,
    meters,
    ortho_view,
    shade,
    upscale,
)
from buildup.voxcore import EMPTY, Grid, Vec3
from buildup.voxcore.grid import as_float3, as_vec3, check_grid

DEFAULT_VIEWS: Final = (
    View.FRONT,
    View.LEFT,
    View.TOP,
    View.BACK,
    View.ISO_FRONT,
    View.ISO_BACK,
)
PANEL_TARGET: Final = 320  # pixels for the longest grid edge
MAX_SCALE: Final = 16
COLUMNS: Final = 3
MARGIN: Final = 12
RULER: Final = 34  # space for a ruler and its labels
TITLE_HEIGHT: Final = 58
MIN_TICK_GAP: Final = 36  # pixels between ruler ticks
GIZMO_LENGTH: Final = 10  # voxels (1 m)
MAX_GIZMO_PIXELS: Final = 80  # beyond this, the gizmo shows 0.5 m
MIN_PANEL_WIDTH: Final = 300
TEXT: Final = (30, 30, 30)
MARKER: Final = (200, 0, 130)
LABEL_BACK: Final = (255, 255, 255)
AXIS_COLORS: Final = ((215, 40, 40), (30, 160, 30), (40, 80, 220))
#: Side of a model for (axis, sign).
SIDE_NAMES: Final[dict[tuple[int, int], str]] = {
    (0, 1): "+X right side",
    (0, -1): "-X left side",
    (1, 1): "+Y top",
    (1, -1): "-Y bottom",
    (2, -1): "-Z front",
    (2, 1): "+Z back",
}
AXIS_NAMES: Final = "XYZ"
#: Ruler spacings to choose from, in voxels (1 voxel = 0.1 m).
SPACINGS: Final = (1, 2, 5, 10, 20, 50, 100)

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


@dataclass(frozen=True)
class Marker:
    """A labelled point drawn on every panel.

    Attributes:
        label: Short text, for example ``"wheel_fl"``.
        position: Teardown-frame position in voxels, as continuous coordinates: voxel ``i``
            spans ``i`` to ``i + 1`` and its center is ``i + 0.5`` (the axle of a wheel whose
            cells are 8 to 15 is at 12.0). Ruler ticks label the same coordinates, divided by
            10 (meters).
    """

    label: str
    position: tuple[float, float, float]


@dataclass(frozen=True)
class Annotations:
    """Optional texts and points of a preview sheet.

    Attributes:
        title: Text at the top of the sheet.
        markers: Labelled points drawn on every panel.
    """

    title: str = ""
    markers: tuple[Marker, ...] = ()


@dataclass(frozen=True)
class _Scene:
    """What every panel needs."""

    grid: Grid
    colors: npt.NDArray[np.uint8]
    scale: int
    origin: Vec3
    markers: tuple[Marker, ...]


def _font(size: int) -> Font:
    return ImageFont.load_default(size=size)


def choose_scale(shape: Sequence[int], target: int = PANEL_TARGET) -> int:
    """Pixels per voxel so that the longest edge spans about ``target`` pixels (1 to 16)."""
    return max(1, min(MAX_SCALE, target // max(shape)))


def ruler_spacing(extent_vox: int, scale: int) -> int:
    """Tick spacing in voxels: at most 10 ticks, and at least ``MIN_TICK_GAP`` pixels apart."""
    for spacing in SPACINGS:
        if extent_vox / spacing <= 10 and spacing * scale >= MIN_TICK_GAP:
            return spacing
    return SPACINGS[-1]


def ticks(origin: int, n: int, scale: int) -> list[tuple[int, int]]:
    """``(grid boundary index, Teardown coordinate)`` of the ruler ticks over ``n`` cells.

    Ticks fall on Teardown coordinates (voxels) that are multiples of ``ruler_spacing``.
    """
    spacing = ruler_spacing(n, scale)
    first = -(-origin // spacing) * spacing
    return [(t - origin, t) for t in range(first, origin + n + 1, spacing)]


def boundary_pixel(g: float, n: int, sign: int, scale: int, rows: bool) -> float:
    """Pixel position of grid boundary ``g`` along an image axis of ``n`` cells.

    Args:
        g: Boundary position in grid voxels (0 to ``n``; fractional for markers).
        n: Number of cells along this image axis.
        sign: +1 if the grid axis grows to the right (columns) or upwards (rows).
        scale: Pixels per voxel.
        rows: True for the vertical image axis (pixel rows grow downwards).
    """
    grows_with_pixels = sign < 0 if rows else sign > 0
    return (g if grows_with_pixels else n - g) * scale


def _ortho_panel(scene: _Scene, view: View) -> Image.Image:
    grid, scale, origin = scene.grid, scene.scale, scene.origin
    o = ORIENTATIONS[view]
    image = ortho_view(grid, view)
    rgb = upscale(shade(image, scene.colors, grid.shape[o.depth]), image, scale)
    n_right, n_up = grid.shape[o.right], grid.shape[o.up]
    font, small = _font(14), _font(12)
    width = max(RULER + rgb.shape[1] + MARGIN * 4, MIN_PANEL_WIDTH)
    height = TITLE_HEIGHT + rgb.shape[0] + RULER + MARGIN
    panel = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(panel)
    draw.text((4, 2), f"{view.value.upper()} view, {o.seen_from}", fill=TEXT, font=font)
    left_side = SIDE_NAMES[(o.right, -o.right_sign)]
    right_side = SIDE_NAMES[(o.right, o.right_sign)]
    draw.text((4, 20), f"image left: {left_side} | right: {right_side}", fill=TEXT, font=small)
    x0, y0 = RULER, TITLE_HEIGHT
    panel.paste(Image.fromarray(rgb), (x0, y0))
    bottom = y0 + rgb.shape[0]
    right_edge = x0 + rgb.shape[1]

    # Horizontal ruler, below the image.
    draw.line([(x0, bottom + 2), (right_edge, bottom + 2)], fill=TEXT)
    for g, coord in ticks(origin[o.right], n_right, scale):
        x = x0 + boundary_pixel(g, n_right, o.right_sign, scale, rows=False)
        draw.line([(x, bottom + 2), (x, bottom + 7)], fill=TEXT)
        draw.text((x, bottom + 9), meters(coord), fill=TEXT, font=small, anchor="ma")
    reserved = []
    x_title = f"{AXIS_NAMES[o.right]} (m)"
    draw.text((right_edge + 4, bottom + 2), x_title, fill=TEXT, font=small)
    reserved.append(draw.textbbox((right_edge + 4, bottom + 2), x_title, font=small))

    # Vertical ruler, left of the image.
    draw.line([(x0 - 2, y0), (x0 - 2, bottom)], fill=TEXT)
    for g, coord in ticks(origin[o.up], n_up, scale):
        y = y0 + boundary_pixel(g, n_up, o.up_sign, scale, rows=True)
        draw.line([(x0 - 7, y), (x0 - 2, y)], fill=TEXT)
        draw.text((x0 - 9, y), meters(coord), fill=TEXT, font=small, anchor="rm")
    y_title = f"{AXIS_NAMES[o.up]} (m)"
    draw.text((2, y0 - 18), y_title, fill=TEXT, font=small)
    reserved.append(draw.textbbox((2, y0 - 18), y_title, font=small))

    placed = []
    for marker in scene.markers:
        p = np.subtract(marker.position, origin)
        x = x0 + boundary_pixel(float(p[o.right]), n_right, o.right_sign, scale, rows=False)
        y = y0 + boundary_pixel(float(p[o.up]), n_up, o.up_sign, scale, rows=True)
        placed.append(((x, y), marker.label))
    _draw_markers(draw, placed, small, width, reserved)
    return panel


def group_markers(
    placed: Sequence[tuple[tuple[float, float], str]],
) -> list[tuple[tuple[float, float], str]]:
    """Merge markers that land on the same pixel (e.g. front and rear wheel in a front view).

    Labels of merged markers are joined with ``" + "``, in their original order.
    """
    groups: dict[tuple[int, int], tuple[tuple[float, float], list[str]]] = {}
    for at, label in placed:
        key = (round(at[0]), round(at[1]))
        if key in groups:
            groups[key][1].append(label)
        else:
            groups[key] = (at, [label])
    return [(at, " + ".join(labels)) for at, labels in groups.values()]


def _draw_markers(
    draw: ImageDraw.ImageDraw,
    placed: Sequence[tuple[tuple[float, float], str]],
    font: Font,
    panel_width: int,
    reserved: Sequence[tuple[float, float, float, float]],
) -> None:
    """Draw marker crosses, then labels in free spots, each tied to its cross by a thin line."""
    taken = [(float(r[0]), float(r[1]), float(r[2]), float(r[3])) for r in reserved]
    groups = group_markers(placed)
    for (x, y), _ in groups:
        draw.line([(x - 6, y), (x + 6, y)], fill=MARKER, width=2)
        draw.line([(x, y - 6), (x, y + 6)], fill=MARKER, width=2)
    for (x, y), label in groups:
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        box = _free_label_box((x, y), (right - left, bottom - top), panel_width, taken)
        taken.append(box)
        # Leader line from the cross to the nearest point of the label box.
        nx = min(max(x, box[0]), box[2])
        ny = min(max(y, box[1]), box[3])
        if abs(nx - x) + abs(ny - y) > 4:
            draw.line([(x, y), (nx, ny)], fill=MARKER, width=1)
        draw.rectangle([(box[0] - 1, box[1] - 1), (box[2] + 1, box[3] + 1)], fill=LABEL_BACK)
        draw.text((box[0] - left, box[1] - top), label, fill=MARKER, font=font)


def _free_label_box(
    at: tuple[float, float],
    size: tuple[float, float],
    panel_width: int,
    taken: Sequence[tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    """First label box near ``at`` that stays in the panel and overlaps no taken box."""
    x, y = at
    w, h = size
    candidates = []
    for dy in (-18, 8, -34, 24, -50, 40):
        for side in (x + 7, x - 7 - w):
            tx = min(max(2.0, side), panel_width - 2 - w)
            candidates.append((tx, y + dy, tx + w, y + dy + h))
    for box in candidates:
        if all(
            box[2] < t[0] - 2 or box[0] > t[2] + 2 or box[3] < t[1] - 2 or box[1] > t[3] + 2
            for t in taken
        ):
            return box
    return candidates[0]


def _iso_panel(scene: _Scene, view: View) -> Image.Image:
    grid, scale = scene.grid, scene.scale
    shape = (grid.shape[0], grid.shape[1], grid.shape[2])
    picture = iso_image(grid, scene.colors, view, scale)
    frame = iso_frame(shape, view, scale)
    font, small = _font(14), _font(12)
    # The axis gizmo gets its own area below the picture: 1 m, or 0.5 m at large scales.
    length = GIZMO_LENGTH if GIZMO_LENGTH * scale <= MAX_GIZMO_PIXELS else GIZMO_LENGTH // 2
    tips = {
        axis: frame.projection.project(np.array([d], dtype=np.float64))[0] * scale
        for axis, d in (
            (0, (length, 0, 0)),
            (1, (0, length, 0)),
            (2, (0, 0, -length)),
        )
    }
    ends = np.array([(0.0, 0.0), *tips.values()])
    gizmo_low, gizmo_high = ends.min(axis=0), ends.max(axis=0)
    gizmo_height = int(gizmo_high[1] - gizmo_low[1]) + 30
    width = max(picture.width + MARGIN * 2, MIN_PANEL_WIDTH)
    height = TITLE_HEIGHT + picture.height + gizmo_height + MARGIN
    panel = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(panel)
    sides = ", ".join(
        SIDE_NAMES[(axis, sign)].split(" ", 1)[1] for axis, sign in enumerate(CAMERAS[view])
    )
    draw.text((4, 2), f"{view.value.upper()} view (3/4)", fill=TEXT, font=font)
    draw.text((4, 20), f"visible faces: {sides}", fill=TEXT, font=small)
    x0, y0 = MARGIN, TITLE_HEIGHT
    panel.paste(picture, (x0, y0))
    shift = np.array([x0, y0], dtype=np.float64)

    # Axis gizmo: three lines from a common point, in the area below the picture.
    base = np.array([MARGIN + 40.0, y0 + picture.height + 8.0]) - gizmo_low
    for axis, label in ((0, "+X"), (1, "+Y"), (2, "-Z front")):
        tip = base + tips[axis]
        draw.line(
            [(float(base[0]), float(base[1])), (float(tip[0]), float(tip[1]))],
            fill=AXIS_COLORS[axis],
            width=2,
        )
        draw.text((float(tip[0]) + 3, float(tip[1]) - 7), label, fill=AXIS_COLORS[axis], font=small)
    draw.text(
        (float(base[0] + gizmo_high[0]) + 70, float(base[1]) - 7),
        f"axis lines: {meters(length)} m",
        fill=TEXT,
        font=small,
    )

    placed = []
    for marker in scene.markers:
        point = np.subtract(marker.position, scene.origin)[None, :].astype(np.float64)
        at = frame.to_pixels(point)[0] + shift
        placed.append(((float(at[0]), float(at[1])), marker.label))
    _draw_markers(draw, placed, small, width, [])
    return panel


def preview_sheet(
    grid: Grid,
    colors: npt.NDArray[np.uint8],
    *,
    origin: Vec3 = (0, 0, 0),
    views: Sequence[View] = DEFAULT_VIEWS,
    annotations: Annotations | None = None,
) -> Image.Image:
    """Draw an annotated multi-view preview of a model.

    Args:
        grid: The model (Teardown frame).
        colors: ``(256, 3)`` or ``(256, 4)`` RGB(A) table indexed by palette index
            (``Palette.rgba()``).
        origin: Teardown-frame position of the grid's first cell, in voxels; rulers and
            markers use Teardown coordinates.
        views: Panels to draw, three per row.
        annotations: Title and markers (none by default).

    Returns:
        An RGB image.

    Raises:
        RenderError: If ``views`` is empty or names an unknown view.
        VoxcoreError: If ``origin`` or a marker position is malformed.
    """
    grid = check_grid(grid)
    origin = as_vec3(origin, "origin")
    chosen = [as_view(v) for v in views]
    if not chosen:
        raise RenderError("at least one view is needed")
    annotations = annotations or Annotations()
    for marker in annotations.markers:
        as_float3(marker.position, f"position of marker {marker.label!r}")
    scale = choose_scale(grid.shape)
    color_table(colors)  # fail early on a malformed table
    scene = _Scene(grid, colors, scale, origin, annotations.markers)
    panels = [_iso_panel(scene, v) if v in CAMERAS else _ortho_panel(scene, v) for v in chosen]
    rows = [panels[i : i + COLUMNS] for i in range(0, len(panels), COLUMNS)]
    header_h = 46
    width = max(sum(p.width for p in row) + MARGIN * (len(row) + 1) for row in rows)
    height = header_h + sum(max(p.height for p in row) + MARGIN for row in rows)
    sheet = Image.new("RGB", (width, height), (250, 250, 248))
    draw = ImageDraw.Draw(sheet)
    sx, sy, sz = grid.shape
    count = int(np.count_nonzero(grid != EMPTY))
    summary = (
        f"grid {sx} x {sy} x {sz} voxels = {meters(sx)} x {meters(sy)} x {meters(sz)} m "
        f"(X width, Y height, Z length) | {count} voxels | first cell at "
        f"({meters(origin[0])}, {meters(origin[1])}, {meters(origin[2])}) m | "
        f"{scale} px per voxel"
    )
    draw.text((MARGIN, 6), annotations.title or "Buildup preview", fill=TEXT, font=_font(18))
    draw.text((MARGIN, 28), summary, fill=TEXT, font=_font(12))
    y = header_h
    for row in rows:
        x = MARGIN
        for panel in row:
            sheet.paste(panel, (x, y))
            x += panel.width + MARGIN
        y += max(p.height for p in row) + MARGIN
    return sheet
