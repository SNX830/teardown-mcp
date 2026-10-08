"""Profiles: a 2D silhouette (polygon or ASCII drawing) extruded across the model, with bevels.

A profile lies in one of three planes:

- ``side``: the Z-Y plane (as in the left preview), extruded along X. Points are ``(z, y)``.
- ``front``: the X-Y plane, extruded along Z. Points are ``(x, y)``; a drawing in this plane
  reads like the BACK preview (+X to the right), not the front one.
- ``top``: the X-Z plane (as in the top preview), extruded along Y. Points are ``(x, z)``.

The section is a 2D boolean array indexed ``[h, v]`` (first then second coordinate of the
points); cell ``(i, j)`` is inside a polygon when its center ``(i + 0.5, j + 0.5)`` is (even-odd
rule), so a polygon through whole coordinates covers the same cells as a box with those corners.

A bevel shrinks the section near both ends of the extrusion, which rounds or chamfers every edge
between the outline and the end faces (the sides of a car body, seen from the front).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
import numpy.typing as npt

from buildup.voxcore.grid import Mask, Vec3, VoxcoreError, as_int, as_pair, as_vec3

Plane = Literal["side", "front", "top"]
BevelStyle = Literal["chamfer", "round"]
Section = npt.NDArray[np.bool_]

#: Plane -> (array axis of the first point coordinate, of the second, extrusion axis).
PLANES: Final[dict[str, tuple[int, int, int]]] = {
    "side": (2, 1, 0),
    "front": (0, 1, 2),
    "top": (0, 2, 1),
}
BEVEL_STYLES: Final = ("chamfer", "round")
MAX_BEVEL: Final = 32
MIN_POLYGON_POINTS: Final = 3
SECTION_DIMENSIONS: Final = 2
#: Character that leaves a cell empty in an ASCII section, besides whitespace (spaces, tabs);
#: every other character fills its cell.
EMPTY_CHARACTER: Final = "."


def plane_axes(plane: object) -> tuple[int, int, int]:
    """Array axes of a plane: (first coordinate, second coordinate, extrusion).

    Raises:
        VoxcoreError: For an unknown plane.
    """
    if not isinstance(plane, str) or plane not in PLANES:
        raise VoxcoreError(f"plane must be one of {', '.join(PLANES)}, got {plane!r}")
    return PLANES[plane]


def polygon_section(
    points: Sequence[tuple[float, float]], start: tuple[int, int], size: tuple[int, int]
) -> Section:
    """Cells of a window inside a polygon (even-odd rule on cell centers).

    Args:
        points: Polygon corners ``(h, v)`` in voxels, at least 3, in order (closed
            automatically).
        start: First cell ``(h, v)`` of the window.
        size: Window size in cells.

    Returns:
        ``size``-shaped boolean array.

    Raises:
        VoxcoreError: Fewer than 3 points.
    """
    if len(points) < MIN_POLYGON_POINTS:
        raise VoxcoreError(
            f"a polygon needs at least {MIN_POLYGON_POINTS} points, got {len(points)}"
        )
    h = (np.arange(size[0], dtype=np.float64) + start[0] + 0.5)[:, None]
    v = (np.arange(size[1], dtype=np.float64) + start[1] + 0.5)[None, :]
    inside = np.zeros(size, dtype=np.bool_)
    for (h0, v0), (h1, v1) in zip(points, [*points[1:], points[0]], strict=True):
        if v0 == v1:
            continue  # horizontal edges never cross a horizontal ray
        crosses = (v0 > v) != (v1 > v)
        at = h0 + (v - v0) * (h1 - h0) / (v1 - v0)
        inside ^= crosses & (h < at)
    return inside


def ascii_section(rows: Sequence[str]) -> Section:
    """Section drawn as text: one character per cell, the first row on top.

    Whitespace and dots are empty cells, any other character fills its cell. The result is indexed
    ``[h, v]`` with ``h`` the character position and ``v`` counted from the LAST row (``v = 0``
    is the bottom row as drawn).

    Raises:
        VoxcoreError: No rows, or nothing filled.
    """
    if not rows:
        raise VoxcoreError("the drawing has no rows")
    width = max(len(row) for row in rows)
    section = np.zeros((width, len(rows)), dtype=np.bool_)
    for r, row in enumerate(rows):
        for c, char in enumerate(row):
            section[c, len(rows) - 1 - r] = not char.isspace() and char != EMPTY_CHARACTER
    if not section.any():
        raise VoxcoreError(
            "the drawing fills no cell: use a character such as '#' for filled cells "
            "and spaces or dots for empty ones"
        )
    return section


def inner_distance(section: Section, limit: int) -> npt.NDArray[np.int64]:
    """Steps from each filled cell to the outside of the section, at most ``limit + 1``.

    Border cells (a side neighbour is empty or out of the array) are at 1. Steps alternate
    side-only and side-or-diagonal neighbours, so distances grow in octagons, close to circles.
    """
    distance = np.zeros(section.shape, dtype=np.int64)
    current = section.copy()
    for step in range(limit + 1):
        if not current.any():
            break
        distance[current] += 1
        padded = np.pad(current, 1, constant_values=False)
        h, v = current.shape
        eroded = current.copy()
        for dh, dv in ((0, 1), (2, 1), (1, 0), (1, 2)):
            eroded &= padded[dh : dh + h, dv : dv + v]
        if step % 2:
            for dh, dv in ((0, 0), (0, 2), (2, 0), (2, 2)):
                eroded &= padded[dh : dh + h, dv : dv + v]
        current = eroded
    return distance


def bevel_insets(length: int, bevel: int, style: BevelStyle) -> list[int]:
    """How many cells to remove from the section's outline in each layer of the extrusion.

    A layer keeps the cells whose ``inner_distance`` is above its inset. Layer ``k`` of
    ``length`` is ``d = min(k, length - 1 - k)`` layers from the nearest end; 0 from
    ``d = bevel`` on. ``chamfer``: ``bevel - d``, the same 45 degree stair as
    ``voxcore.chamfer`` (``bevel=1`` removes the single row of cells along the edge).
    ``round``: the cells whose center is outside a quarter circle of radius ``bevel`` tangent
    to the end face and to the outline (it removes less than a chamfer of the same size:
    ``round`` 2 removes the edge row, ``round`` 4 is a 2-step stair).
    """
    insets = []
    for k in range(length):
        d = min(k, length - 1 - k)
        if d >= bevel:
            insets.append(0)
        elif style == "chamfer":
            insets.append(bevel - d)
        else:
            # Cell centers: d + 0.5 from the end face, inner_distance - 0.5 from the outline.
            t = bevel - (d + 0.5)
            depth = bevel - math.sqrt(bevel * bevel - t * t)
            insets.append(max(0, math.ceil(depth + 0.5) - 1))
    return insets


@dataclass(frozen=True)
class Bevel:
    """Bevel of the edges at both ends of an extrusion.

    Attributes:
        size: Cells removed from the outline in the end layers, 0 (none) to ``MAX_BEVEL``.
        style: ``chamfer`` (straight 45 degree stair) or ``round`` (quarter circle).
    """

    size: int = 0
    style: BevelStyle = "chamfer"

    def __post_init__(self) -> None:
        size = as_int(self.size, "bevel", minimum=0)
        if size > MAX_BEVEL:
            raise VoxcoreError(f"bevel must be at most {MAX_BEVEL} voxels, got {size}")
        bevel_style(self.style)
        object.__setattr__(self, "size", size)


def bevel_style(value: object) -> BevelStyle:
    """Validate a bevel style name.

    Raises:
        VoxcoreError: Otherwise.
    """
    if value == "chamfer":
        return "chamfer"
    if value == "round":
        return "round"
    raise VoxcoreError(f"bevel_style must be one of {', '.join(BEVEL_STYLES)}, got {value!r}")


@dataclass(frozen=True)
class Profile:
    """A section extruded along the third axis of its plane.

    Attributes:
        plane: ``side``, ``front`` or ``top`` (see the module documentation).
        section: Non-empty boolean array ``[h, v]``.
        start: Position of the section's cell ``(0, 0)`` on the plane's first two axes.
        span: Extrusion cells ``span[0] <= c < span[1]`` along the third axis.
        bevel: Bevel of the edges at both ends.
    """

    plane: Plane
    section: Section
    start: tuple[int, int]
    span: tuple[int, int]
    bevel: Bevel = Bevel()

    def __post_init__(self) -> None:
        plane_axes(self.plane)
        section = self.section
        if section.ndim != SECTION_DIMENSIONS or section.dtype != np.bool_ or section.size == 0:
            raise VoxcoreError("section must be a non-empty 2D boolean array")
        h_raw, v_raw = as_pair(self.start, "section start")
        start = (as_int(h_raw, "section start"), as_int(v_raw, "section start"))
        lo_raw, hi_raw = as_pair(self.span, "span")
        lo, hi = as_int(lo_raw, "span start"), as_int(hi_raw, "span end")
        if lo >= hi:
            raise VoxcoreError(
                f"span {lo}..{hi} is empty: the first value must be below the second"
            )
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "span", (lo, hi))


def extrude(size: Vec3, profile: Profile, offset: Vec3 = (0, 0, 0)) -> Mask:
    """Mask of a profile over a grid.

    Args:
        size: Grid size.
        profile: The profile, in coordinates where the grid's first cell is at ``offset``.
        offset: Position of the grid's first cell in the profile's coordinates.

    Returns:
        Boolean mask of the grid (the parts of the profile outside it are clipped).

    Raises:
        VoxcoreError: Bad size or offset.
    """
    size = as_vec3(size, "grid size", minimum=1)
    offset = as_vec3(offset, "offset")
    h_axis, v_axis, e_axis = plane_axes(profile.plane)
    section, bevel = profile.section, profile.bevel
    h0 = profile.start[0] - offset[h_axis]
    v0 = profile.start[1] - offset[v_axis]
    lo, hi = profile.span[0] - offset[e_axis], profile.span[1] - offset[e_axis]
    layers = np.zeros((size[h_axis], size[v_axis], size[e_axis]), dtype=np.bool_)
    # Part of the section inside the grid.
    hs, vs = max(0, -h0), max(0, -v0)
    he = min(section.shape[0], size[h_axis] - h0)
    ve = min(section.shape[1], size[v_axis] - v0)
    if hs < he and vs < ve:
        cut = inner_distance(section, bevel.size)[hs:he, vs:ve]
        insets = bevel_insets(hi - lo, bevel.size, bevel.style)
        for e in range(max(0, lo), min(size[e_axis], hi)):
            layers[h0 + hs : h0 + he, v0 + vs : v0 + ve, e] = cut > insets[e - lo]
    # ``layers`` is indexed [h, v, e]: move the axes back to [x, y, z].
    order = [0, 0, 0]
    for source, target in enumerate((h_axis, v_axis, e_axis)):
        order[target] = source
    mask: Mask = np.transpose(layers, order).copy()
    return mask
