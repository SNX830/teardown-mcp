"""Shapes placed in the model frame, as drawn by the modelling tools.

A ``Shape`` knows its bounding box in model-frame voxels and computes its mask over any window
of cells, so that a tool only allocates arrays the size of the shape, whatever the part's size.
The geometry itself is ``buildup.voxcore.shapes`` (coordinates shifted to the window).
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from buildup.voxcore import Axis, Face, Mask, Vec3, VoxcoreError
from buildup.voxcore import profile as vp
from buildup.voxcore import shapes as vs
from buildup.voxcore.grid import as_float3, as_int, as_number, as_pair, as_vec3, axis_number

#: Model space: every voxel must have coordinates in ``WORLD_MIN <= c < WORLD_MAX`` on each axis.
#: 256 voxels (25.6 m) per axis, the ``.vox`` limit for one object, so any part fits in one
#: object and the whole model in a 256^3 grid (16 MB) for previews (decision D-022).
WORLD_MIN: Final = -128
WORLD_MAX: Final = 128

#: Largest absolute value accepted for shape centers and sizes (voxels): far beyond model space,
#: small enough that bounding boxes stay ordinary integers.
MAX_COORDINATE: Final = 4096

MaskFunction = Callable[[Vec3, Vec3], Mask]

# Literal values by name, to turn checked strings into typed names without casts.
_FACE_NAMES: Final[dict[str, Face]] = {
    "left": "left",
    "right": "right",
    "bottom": "bottom",
    "top": "top",
    "front": "front",
    "back": "back",
}
_AXIS_NAMES: Final[dict[str, Axis]] = {"x": "x", "y": "y", "z": "z"}
_PLANE_NAMES: Final[dict[str, vp.Plane]] = {"side": "side", "front": "front", "top": "top"}


@dataclass(frozen=True)
class Shape:
    """A shape in the model frame.

    Attributes:
        start: Minimum corner of the bounding box (voxels, inclusive).
        end: Maximum corner of the bounding box (voxels, exclusive).
        compute: ``(window_start, window_size) -> mask`` over the cells
            ``window_start <= c < window_start + window_size``.
    """

    start: Vec3
    end: Vec3
    compute: MaskFunction

    def mask(self, start: Vec3, size: Vec3) -> Mask:
        """Mask of the shape over a window of model-frame cells."""
        return self.compute(start, size)


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _limited(values: Sequence[float], what: str) -> None:
    if any(abs(v) > MAX_COORDINATE for v in values):
        raise VoxcoreError(f"{what} must stay within +-{MAX_COORDINATE} voxels, got {values}")


def _region(start: object, end: object) -> tuple[Vec3, Vec3]:
    s = as_vec3(start, "start")
    e = as_vec3(end, "end")
    _limited(s, "start")
    _limited(e, "end")
    if any(a >= b for a, b in zip(s, e, strict=True)):
        raise VoxcoreError(f"start {s} must be below end {e} on every axis (end is exclusive)")
    return s, e


def box_shape(start: object, end: object) -> Shape:
    """Block of cells ``start <= c < end``."""
    s, e = _region(start, end)
    return Shape(s, e, lambda w, size: vs.box(size, _sub(s, w), _sub(e, w)))


def wedge_shape(start: object, end: object, faces: object) -> Shape:
    """Ramp: the block ``start..end`` cut diagonally from the edge between ``faces``."""
    s, e = _region(start, end)
    face_pair = _faces(faces)
    vs.wedge((1, 1, 1), s, e, face_pair)  # validate now, not inside a later computation
    return Shape(s, e, lambda w, size: vs.wedge(size, _sub(s, w), _sub(e, w), face_pair))


def edge_cut_shape(start: object, end: object, faces: object, depths: object) -> Shape:
    """Triangular prism along the edge between two faces of the block ``start..end``."""
    s, e = _region(start, end)
    face_pair = _faces(faces)
    d0, d1 = as_pair(depths, "depths")
    depth_pair = (as_number(d0, "depth", positive=True), as_number(d1, "depth", positive=True))
    vs.edge_cut((1, 1, 1), s, e, face_pair, depth_pair)  # validate now
    return Shape(
        s, e, lambda w, size: vs.edge_cut(size, _sub(s, w), _sub(e, w), face_pair, depth_pair)
    )


def _face(face: object) -> Face:
    if not isinstance(face, str) or face not in _FACE_NAMES:
        raise VoxcoreError(f"face must be one of {', '.join(_FACE_NAMES)}, got {face!r}")
    return _FACE_NAMES[face]


def _faces(faces: object) -> tuple[Face, Face]:
    a, b = as_pair(faces, "faces")
    return _face(a), _face(b)


def cylinder_shape(axis: object, center: object, radius: object, span: object) -> Shape:
    """Cylinder along ``axis`` (see ``buildup.voxcore.cylinder``), in model coordinates."""
    if not isinstance(axis, str) or axis not in _AXIS_NAMES:
        raise VoxcoreError(f"axis must be 'x', 'y' or 'z', got {axis!r}")
    along = _AXIS_NAMES[axis]
    a = axis_number(along)
    r = as_number(radius, "radius", positive=True)
    c0, c1 = as_pair(center, "center")
    c = (as_number(c0, "center"), as_number(c1, "center"))
    s0, s1 = as_pair(span, "span")
    lo, hi = as_int(s0, "span start"), as_int(s1, "span end")
    _limited((*c, r, lo, hi), "cylinder center, radius and span")
    if lo >= hi:
        raise VoxcoreError(f"span {lo}..{hi} is empty: the first value must be below the second")
    others = [i for i in range(3) if i != a]
    start = [0, 0, 0]
    end = [0, 0, 0]
    start[a], end[a] = lo, hi
    for k, i in enumerate(others):
        start[i] = math.floor(c[k] - r)
        end[i] = math.ceil(c[k] + r)
    s = (start[0], start[1], start[2])
    e = (end[0], end[1], end[2])

    def compute(w: Vec3, size: Vec3) -> Mask:
        local = (c[0] - w[others[0]], c[1] - w[others[1]])
        return vs.cylinder(size, along, local, r, (lo - w[a], hi - w[a]))

    return Shape(s, e, compute)


def ellipsoid_shape(center: object, radii: object) -> Shape:
    """Ellipsoid (a sphere when the radii are equal), in model coordinates."""
    c = as_float3(center, "center")
    r = as_float3(radii, "radii", positive=True)
    _limited((*c, *r), "ellipsoid center and radii")
    s = (
        math.floor(c[0] - r[0]),
        math.floor(c[1] - r[1]),
        math.floor(c[2] - r[2]),
    )
    e = (math.ceil(c[0] + r[0]), math.ceil(c[1] + r[1]), math.ceil(c[2] + r[2]))
    return Shape(
        s, e, lambda w, size: vs.ellipsoid(size, (c[0] - w[0], c[1] - w[1], c[2] - w[2]), r)
    )


def clip_to_world(start: Vec3, end: Vec3) -> tuple[Vec3, Vec3] | None:
    """Part of the box ``start..end`` inside model space, or ``None`` if nothing is inside."""
    lo = tuple(max(WORLD_MIN, v) for v in start)
    hi = tuple(min(WORLD_MAX, v) for v in end)
    if any(a >= b for a, b in zip(lo, hi, strict=True)):
        return None
    return (lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2])


def inside_world(points: Sequence[float]) -> bool:
    """Whether a point (continuous coordinates) is inside model space."""
    return all(WORLD_MIN <= p <= WORLD_MAX for p in points)


#: Most points of a polygon, rows of a drawing and characters per row.
MAX_PROFILE_POINTS: Final = 256
MAX_DRAWING: Final = 256


def _profile_points(points: object) -> list[tuple[float, float]]:
    if not isinstance(points, tuple | list) or not points:
        raise VoxcoreError("points must be a list of [h, v] pairs")
    if len(points) < vp.MIN_POLYGON_POINTS:
        raise VoxcoreError(f"a polygon needs at least 3 points, got {len(points)}")
    if len(points) > MAX_PROFILE_POINTS:
        raise VoxcoreError(f"a profile has at most {MAX_PROFILE_POINTS} points, got {len(points)}")
    pairs = []
    for point in points:
        h, v = as_pair(point, "each point")
        pairs.append((as_number(h, "point coordinate"), as_number(v, "point coordinate")))
    _limited([c for pair in pairs for c in pair], "profile points")
    return pairs


def _drawing_rows(rows: object) -> list[str]:
    if (
        not isinstance(rows, tuple | list)
        or not rows
        or not all(isinstance(row, str) for row in rows)
    ):
        raise VoxcoreError("rows must be a list of strings, the top row first")
    if len(rows) > MAX_DRAWING or any(len(row) > MAX_DRAWING for row in rows):
        raise VoxcoreError(f"a drawing has at most {MAX_DRAWING} rows of {MAX_DRAWING} characters")
    return [str(row) for row in rows]


def _profile_shape(
    plane: vp.Plane, section: vp.Section, start_hv: tuple[int, int], span: object, bevel: vp.Bevel
) -> Shape:
    h_axis, v_axis, e_axis = vp.plane_axes(plane)
    s0, s1 = as_pair(span, "span")
    lo, hi = as_int(s0, "span start"), as_int(s1, "span end")
    _limited((lo, hi), "span")
    profile = vp.Profile(plane, section, start_hv, (lo, hi), bevel)
    start = [0, 0, 0]
    end = [0, 0, 0]
    start[h_axis], end[h_axis] = start_hv[0], start_hv[0] + section.shape[0]
    start[v_axis], end[v_axis] = start_hv[1], start_hv[1] + section.shape[1]
    start[e_axis], end[e_axis] = lo, hi
    s = (start[0], start[1], start[2])
    e = (end[0], end[1], end[2])
    return Shape(s, e, lambda w, size: vp.extrude(size, profile, w))


def _plane(plane: object) -> vp.Plane:
    if not isinstance(plane, str) or plane not in _PLANE_NAMES:
        raise VoxcoreError(f"plane must be one of {', '.join(_PLANE_NAMES)}, got {plane!r}")
    return _PLANE_NAMES[plane]


def polygon_profile(plane: object, points: object, span: object, bevel: vp.Bevel) -> Shape:
    """A polygon silhouette extruded across the model (see ``buildup.voxcore.profile``).

    Args:
        plane: ``side`` (points ``[z, y]``, extruded along X), ``front`` (``[x, y]``, along Z)
            or ``top`` (``[x, z]``, along Y).
        points: Polygon corners in voxels (continuous coordinates), at least 3.
        span: First cell and the cell after the last one along the extrusion axis.
        bevel: Bevel of the edges at both ends of the extrusion.

    Raises:
        VoxcoreError: Bad plane, points or span; a polygon that covers no cell.
    """
    name = _plane(plane)
    corners = _profile_points(points)
    # The section is computed over model space plus a margin, so bevels at the limits stay right.
    low, high = WORLD_MIN - vp.MAX_BEVEL - 1, WORLD_MAX + vp.MAX_BEVEL + 1
    h_lo = max(low, math.floor(min(c[0] for c in corners)))
    h_hi = min(high, math.ceil(max(c[0] for c in corners)))
    v_lo = max(low, math.floor(min(c[1] for c in corners)))
    v_hi = min(high, math.ceil(max(c[1] for c in corners)))
    if h_lo >= h_hi or v_lo >= v_hi:
        raise VoxcoreError("the polygon is flat or outside model space: it covers no cell")
    section = vp.polygon_section(corners, (h_lo, v_lo), (h_hi - h_lo, v_hi - v_lo))
    if not section.any():
        raise VoxcoreError("the polygon covers no cell center: make it at least 1 voxel wide")
    return _profile_shape(name, section, (h_lo, v_lo), span, bevel)


def drawn_profile(
    plane: object, rows: object, origin: object, span: object, bevel: vp.Bevel
) -> Shape:
    """An ASCII silhouette extruded across the model (see ``buildup.voxcore.profile``).

    Args:
        plane: ``side`` (characters along +Z, the front on the left as in the left view;
            rows from the top down), ``front`` (characters along +X, as seen from the back) or
            ``top`` (seen from above with the front at the top: characters along +X, rows
            towards +Z).
        rows: The drawing, top row first; spaces and dots are empty, other characters filled.
        origin: Model cell ``[h, v]`` of the bottom-left character (first character of the
            last row), in the plane's coordinates (``side``: ``[z, y]``).
        span: First cell and the cell after the last one along the extrusion axis.
        bevel: Bevel of the edges at both ends of the extrusion.

    Raises:
        VoxcoreError: Bad plane, drawing, origin or span.
    """
    name = _plane(plane)
    section = vp.ascii_section(_drawing_rows(rows))
    o0, o1 = as_pair(origin, "origin")
    h_lo, v_lo = as_int(o0, "origin"), as_int(o1, "origin")
    _limited((h_lo, v_lo), "origin")
    if name == "top":  # the drawing's up is -Z: its last row is the rearmost
        section = section[:, ::-1].copy()
        v_lo -= section.shape[1] - 1
    return _profile_shape(name, section, (h_lo, v_lo), span, bevel)
