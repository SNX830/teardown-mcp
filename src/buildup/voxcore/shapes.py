"""Shapes as boolean masks over a grid.

Every function takes the ``size`` of the target grid and returns a boolean array of that shape
(``True`` = inside the shape), so shapes combine with numpy operators: ``a | b`` (union),
``a & b`` (intersection), ``a & ~b`` (difference). Paint them with ``voxcore.ops``.

Coordinates are grid voxel units in the Teardown frame (X right, Y up, front is -Z). Voxel
``(i, j, k)`` occupies ``[i, i + 1) x [j, j + 1) x [k, k + 1)``; round shapes test voxel centers
``(i + 0.5, j + 0.5, k + 0.5)``. Parts of a shape outside the grid are clipped.

Box faces are named from the Teardown frame: ``left`` (-X), ``right`` (+X), ``bottom`` (-Y),
``top`` (+Y), ``front`` (-Z), ``back`` (+Z).
"""

from collections.abc import Sequence
from typing import Final, Literal

import numpy as np
import numpy.typing as npt

from buildup.voxcore.grid import (
    Axis,
    Mask,
    Vec3,
    VoxcoreError,
    as_float3,
    as_int,
    as_number,
    as_pair,
    as_vec3,
    axis_number,
)

Face = Literal["left", "right", "bottom", "top", "front", "back"]

#: Face name -> (array axis, +1 for the high side or -1 for the low side).
FACES: Final[dict[str, tuple[int, int]]] = {
    "left": (0, -1),
    "right": (0, 1),
    "bottom": (1, -1),
    "top": (1, 1),
    "front": (2, -1),
    "back": (2, 1),
}

FloatArray = npt.NDArray[np.float64]


def _check_size(size: Vec3) -> Vec3:
    return as_vec3(size, "grid size", minimum=1)


def _centers(size: Vec3) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Voxel center coordinates, broadcastable to ``size``."""
    sx, sy, sz = _check_size(size)
    return (
        (np.arange(sx, dtype=np.float64) + 0.5)[:, None, None],
        (np.arange(sy, dtype=np.float64) + 0.5)[None, :, None],
        (np.arange(sz, dtype=np.float64) + 0.5)[None, None, :],
    )


def _check_region(start: Vec3, end: Vec3) -> tuple[Vec3, Vec3]:
    start = as_vec3(start, "start")
    end = as_vec3(end, "end")
    if any(s >= e for s, e in zip(start, end, strict=True)):
        raise VoxcoreError(f"region start {start} must be below end {end} on every axis")
    return start, end


def _face(name: object) -> tuple[int, int]:
    if name not in FACES:
        raise VoxcoreError(f"face must be one of {', '.join(FACES)}, got {name!r}")
    return FACES[name]


def box(size: Vec3, start: Vec3, end: Vec3) -> Mask:
    """Rectangular block of voxels ``start <= index < end`` on each axis.

    Example: ``box((20, 10, 40), (2, 0, 4), (18, 6, 36))`` is a 16 x 6 x 32 voxel block
    (1.6 x 0.6 x 3.2 m).

    Raises:
        VoxcoreError: If ``start`` is not below ``end`` on every axis.
    """
    size = _check_size(size)
    start, end = _check_region(start, end)
    mask = np.zeros(size, dtype=np.bool_)
    # Clamp both bounds into the grid: a box entirely outside gives an empty mask (a negative
    # slice bound would otherwise count from the end of the array).
    lo = [min(max(0, s), n) for n, s in zip(size, start, strict=True)]
    hi = [min(max(0, e), n) for n, e in zip(size, end, strict=True)]
    mask[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] = True
    return mask


def cylinder(
    size: Vec3, axis: Axis, center: tuple[float, float], radius: float, span: tuple[int, int]
) -> Mask:
    """Cylinder along ``axis``, covering indices ``span[0] <= i < span[1]`` along that axis.

    Args:
        size: Grid size.
        axis: ``"x"`` for a wheel (axle along X), ``"y"`` for a vertical post, ``"z"`` for a
            pipe along the vehicle.
        center: Position of the cylinder's axis on the two other axes, in their x, y, z order
            (for ``axis="x"``: ``(y, z)``). Use a whole number for an even diameter,
            ``n + 0.5`` for an odd one.
        radius: In voxels; voxels whose center is within ``radius`` of the axis are inside.
        span: First index along ``axis`` and the index after the last one.

    Example: a wheel 8 voxels high and 2 wide in a (2, 8, 8) grid:
    ``cylinder((2, 8, 8), "x", (4, 4), 4, (0, 2))``.

    Raises:
        VoxcoreError: If the axis is unknown, ``radius <= 0`` or the span is empty.
    """
    along = axis_number(axis)
    radius = as_number(radius, "radius", positive=True)
    c0, c1 = as_pair(center, "center")
    center = (as_number(c0, "center"), as_number(c1, "center"))
    s0, s1 = as_pair(span, "span")
    start, end = as_int(s0, "span start"), as_int(s1, "span end")
    if start >= end:
        raise VoxcoreError(f"cylinder span {span} is empty: start must be below end")
    coords = _centers(size)
    a, b = (coords[i] for i in range(3) if i != along)
    inside = (a - center[0]) ** 2 + (b - center[1]) ** 2 <= radius**2
    index = coords[along] - 0.5
    within = (index >= start) & (index < end)
    return np.broadcast_to(inside & within, size).copy()


def ellipsoid(
    size: Vec3, center: tuple[float, float, float], radii: tuple[float, float, float]
) -> Mask:
    """Ellipsoid with semi-axes ``radii`` (voxels) along X, Y, Z around ``center``.

    Raises:
        VoxcoreError: If a radius is not positive.
    """
    radii = as_float3(radii, "radii", positive=True)
    center = as_float3(center, "center")
    x, y, z = _centers(size)
    value = (
        ((x - center[0]) / radii[0]) ** 2
        + ((y - center[1]) / radii[1]) ** 2
        + ((z - center[2]) / radii[2]) ** 2
    )
    return np.broadcast_to(value <= 1.0, size).copy()


def sphere(size: Vec3, center: tuple[float, float, float], radius: float) -> Mask:
    """Sphere of ``radius`` voxels around ``center`` (voxel centers within the radius).

    Example: a ball 6 voxels across in a 6-voxel cube: ``sphere((6, 6, 6), (3, 3, 3), 3)``.
    """
    return ellipsoid(size, center, (radius, radius, radius))


def half_space(
    size: Vec3, point: tuple[float, float, float], normal: tuple[float, float, float]
) -> Mask:
    """Voxels whose center lies on the side of a plane opposite to ``normal`` (or on it).

    The plane goes through ``point``. Intersect with a box to cut it at any angle.

    Raises:
        VoxcoreError: If ``normal`` is zero.
    """
    normal = as_float3(normal, "normal")
    point = as_float3(point, "point")
    if not any(normal):
        raise VoxcoreError("normal must not be zero")
    x, y, z = _centers(size)
    value = (x - point[0]) * normal[0] + (y - point[1]) * normal[1] + (z - point[2]) * normal[2]
    return np.broadcast_to(value <= 0.0, size).copy()


def _face_distance(size: Vec3, start: Vec3, end: Vec3, face: str) -> FloatArray:
    """Distance from voxel centers to a face plane of the box, positive inside the box."""
    axis, side = _face(face)
    coord = _centers(size)[axis]
    return end[axis] - coord if side > 0 else coord - start[axis]


def edge_cut(
    size: Vec3,
    start: Vec3,
    end: Vec3,
    faces: tuple[Face, Face],
    depths: tuple[float, float],
) -> Mask:
    """Triangular prism along the edge where two faces of a box meet (the part a cut removes).

    A voxel of the box is in the cut when ``d_a / depth_a + d_b / depth_b < 1``, where ``d`` is
    the distance from its center to each face. Remove it with ``box(...) & ~edge_cut(...)``.

    Args:
        size: Grid size.
        start: Box start (as in ``box``).
        end: Box end (as in ``box``).
        faces: Two faces on different axes, for example ``("top", "front")``.
        depths: How far the cut goes into the box from each face, in voxels.

    Example: a windshield slope on a 16 x 10 x 40 cab, 6 voxels down from the top and 10 back
    from the front: ``edge_cut(size, start, end, ("top", "front"), (6, 10))``.

    Raises:
        VoxcoreError: If the faces share an axis or a depth is not positive.
    """
    start, end = _check_region(start, end)
    face_a, face_b = as_pair(faces, "faces")
    (axis_a, _), (axis_b, _) = _face(face_a), _face(face_b)
    depth_a, depth_b = as_pair(depths, "depths")
    depths = (
        as_number(depth_a, "depth", positive=True),
        as_number(depth_b, "depth", positive=True),
    )
    if axis_a == axis_b:
        raise VoxcoreError(f"faces {faces[0]!r} and {faces[1]!r} must be on different axes")
    da = _face_distance(size, start, end, str(face_a))
    db = _face_distance(size, start, end, str(face_b))
    inside = np.broadcast_to(da / depths[0] + db / depths[1] < 1.0, size)
    return box(size, start, end) & inside


def chamfer(
    size: Vec3, start: Vec3, end: Vec3, amount: int, edges: Sequence[tuple[Face, Face]]
) -> Mask:
    """Box with 45-degree bevels of ``amount`` voxels on the given edges.

    ``amount=1`` removes the single row of voxels along each edge; ``amount=2`` a 2-step stair.

    Example: a body with rounded-looking top edges:
    ``chamfer(size, start, end, 2, [("top", "left"), ("top", "right")])``.

    Raises:
        VoxcoreError: If ``amount`` is not an integer of at least 1.
    """
    amount = as_int(amount, "chamfer amount", minimum=1)
    mask = box(size, start, end)
    for edge in edges:
        mask &= ~edge_cut(size, start, end, edge, (amount + 1, amount + 1))
    return mask


def wedge(size: Vec3, start: Vec3, end: Vec3, faces: tuple[Face, Face]) -> Mask:
    """Box cut diagonally across its whole extent: a ramp.

    The edge between ``faces[0]`` and ``faces[1]`` is cut off as deep as the box goes, so the
    remaining half slopes from the opposite of ``faces[0]`` down to ``faces[1]``.

    Example: ``wedge(size, start, end, ("top", "front"))`` keeps a ramp that is full height at
    the back and one voxel high at the front.
    """
    start, end = _check_region(start, end)
    face_a, face_b = as_pair(faces, "faces")
    (axis_a, _), (axis_b, _) = _face(face_a), _face(face_b)
    depth_a = float(end[axis_a] - start[axis_a])
    depth_b = float(end[axis_b] - start[axis_b])
    return box(size, start, end) & ~edge_cut(size, start, end, faces, (depth_a, depth_b))
