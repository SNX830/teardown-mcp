"""Vehicle templates: complete starting models that the AI then customizes.

A template builds a body (shell, cabin, windows, seats, lights), wheels and anchors with the
same operations as the drawing tools. The shapes are Buildup's own simple designs. Sizes
follow the official vehicles of the same kind (docs/TEARDOWN_REFERENCE.md §6, body sizes);
seats follow the official driver rig layout (§5, ``buildup.teardown.anchors``). Every template
is built from a ``Design``: a side profile and a few boxes in design voxels, the front at -Z,
scaled along Z and X to the requested length and width (heights never scale).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from buildup.project.model import Axle, Project, WheelLayout
from buildup.project.names import ProjectError
from buildup.project.shapes import box_shape, cylinder_shape, polygon_profile
from buildup.teardown.anchors import suggested_player
from buildup.voxcore.profile import Bevel

Polygon = tuple[tuple[float, float], ...]
#: A box in the side plane: (z start, z end, y start, y end), design voxels, end exclusive.
SideBox = tuple[float, float, int, int]

#: Most a template's length or width can change (fraction of its design size).
MAX_SCALE_CHANGE: Final = 0.2


@dataclass(frozen=True)
class SeatRow:
    """A row of seats: a cushion and a backrest per seat, and the seated hip points.

    Attributes:
        z: Hip point Z (design voxels); the cushion spans ``z - 3`` to ``z + 3`` and the
            backrest ``z + 3`` to ``z + 5``, behind the head point (3 voxels behind the hip).
        y: Hip point Y = top of the cushion.
        anchors: Anchor name of each seat, left seat first (``driver_seat`` on the left).
    """

    z: float
    y: int
    anchors: tuple[str, str]


@dataclass(frozen=True)
class Design:
    """A vehicle template in design voxels (Teardown frame: X right, Y up, front at -Z).

    Attributes:
        title: One line for the AI.
        length: Body length (even); the body spans Z ``-length / 2`` to ``length / 2``.
        width: Body width (even); X ``-width / 2`` to ``width / 2``.
        bottom: Y of the body's underside.
        wall: Thickness of the cabin walls along X.
        wheel_diameter: Default wheel diameter (even).
        wheel_width: Wheel width along X.
        wheel_inset: Gap between a wheel's outer face and the body side.
        axles: Axle Z positions, front first; the first axle steers, the others drive.
        shell: Side profile of the body, points ``(z, y)``.
        cabin: Side profile carved inside the walls (the cabin, open spaces).
        cargo: Side profile carved inside thin 1-voxel walls (a pickup bed, a cargo box).
        dashboard: Box under the windshield, across the cabin.
        windshield: Box painted glass across the cabin (inner X): the windshield slope.
        rear_window: Box painted glass across the cabin, or ``None``.
        side_windows: Side profiles painted glass on the side walls.
        seats: Seat rows, front first.
        lights_y: Y range of the headlights and of the rear lights.
        paint: Default body color.
        handling: Driving preset (``buildup.teardown.handling``).
        lift: Voxels added to every height of the design (shapes, seats, lights), so that the
            body's underside is ``bottom + lift`` above the ground.
        hollows: Side profiles carved inside the walls to lighten closed volumes.
    """

    title: str
    length: int
    width: int
    bottom: int
    wall: int
    wheel_diameter: int
    wheel_width: int
    wheel_inset: int
    axles: tuple[float, ...]
    shell: Polygon
    cabin: Polygon
    cargo: Polygon | None
    dashboard: SideBox
    windshield: SideBox
    rear_window: SideBox | None
    side_windows: tuple[Polygon, ...]
    seats: tuple[SeatRow, ...]
    lights_y: tuple[tuple[int, int], tuple[int, int]]
    paint: tuple[int, int, int]
    handling: str = "car"
    lift: int = 0
    hollows: tuple[Polygon, ...] = ()


DESIGNS: Final[dict[str, Design]] = {
    "sedan": Design(
        title="4-door saloon car, 4.4 x 2.0 x 1.4 m (like the official saloon car)",
        length=44,
        width=20,
        bottom=1,
        wall=2,
        wheel_diameter=6,
        wheel_width=3,
        wheel_inset=1,
        axles=(-13, 13),
        shell=(
            (-22, 1),
            (-22, 6),
            (-21, 7),
            (-19, 8),
            (-8, 9),
            (-2, 14),
            (9, 14),
            (15, 10),
            (21, 10),
            (22, 9),
            (22, 1),
        ),
        cabin=((-11, 3), (12, 3), (12, 10), (8, 13), (-1, 13), (-6.5, 8), (-11, 8)),
        cargo=None,
        dashboard=(-11, -7, 5, 8),
        windshield=(-9, 0, 10, 13),
        rear_window=(6, 16, 10, 13),
        side_windows=(
            ((-4.5, 10), (3, 10), (3, 13), (-1.5, 13)),
            ((5, 10), (11.5, 10), (9, 13), (5, 13)),
        ),
        seats=(SeatRow(1, 5, ("driver_seat", "passenger_seat")),),
        lights_y=((6, 8), (7, 9)),
        paint=(170, 30, 30),
        lift=1,
    ),
    "suv": Design(
        title="SUV, 4.8 x 2.2 x 1.8 m, high body and big wheels (like the official SUV)",
        length=48,
        width=22,
        bottom=2,
        wall=2,
        wheel_diameter=8,
        wheel_width=3,
        wheel_inset=1,
        axles=(-15, 15),
        shell=(
            (-24, 2),
            (-24, 9),
            (-23, 10),
            (-21, 11),
            (-11, 12),
            (-6, 18),
            (20, 18),
            (23, 17),
            (24, 15),
            (24, 2),
        ),
        cabin=((-14, 4), (22, 4), (22, 16), (21, 17), (-4.6, 17), (-9, 11), (-14, 11)),
        cargo=None,
        dashboard=(-14, -10, 7, 11),
        windshield=(-12, -3, 12, 17),
        rear_window=(21, 25, 12, 17),
        side_windows=(
            ((-6.8, 12), (2, 12), (2, 17), (-3.2, 17)),
            ((4, 12), (11, 12), (11, 17), (4, 17)),
            ((13, 12), (20, 12), (20, 17), (13, 17)),
        ),
        seats=(
            SeatRow(-4, 7, ("driver_seat", "passenger_seat")),
            SeatRow(11, 7, ("passenger_seat_2", "passenger_seat_3")),
        ),
        lights_y=((8, 10), (11, 14)),
        paint=(40, 70, 120),
        handling="offroad",
        lift=1,
    ),
    "pickup": Design(
        title="pickup truck with an open bed, 5.4 x 2.4 x 1.8 m (like the official Taskmaster)",
        length=54,
        width=24,
        bottom=3,
        wall=2,
        wheel_diameter=8,
        wheel_width=4,
        wheel_inset=1,
        axles=(-16, 16),
        shell=(
            (-27, 3),
            (-27, 9),
            (-26, 10),
            (-24, 11),
            (-12, 12),
            (-8, 18),
            (3, 18),
            (4, 17),
            (4, 12),
            (27, 12),
            (27, 3),
        ),
        cabin=((-15, 5), (2, 5), (2, 17), (-6.3, 17), (-10, 12), (-15, 12)),
        cargo=((6, 6), (26, 6), (26, 13), (6, 13)),
        dashboard=(-15, -11, 8, 12),
        windshield=(-13, -5, 13, 17),
        rear_window=(1, 5, 13, 17),
        side_windows=(((-8.3, 13), (0, 13), (0, 17), (-5.5, 17)),),
        seats=(SeatRow(-4, 8, ("driver_seat", "passenger_seat")),),
        lights_y=((8, 10), (8, 11)),
        paint=(60, 110, 60),
        handling="offroad",
        lift=1,
    ),
    "van": Design(
        title="delivery van with a closed cargo area, 5.6 x 2.6 x 2.4 m (like the official van)",
        length=56,
        width=26,
        bottom=2,
        wall=2,
        wheel_diameter=8,
        wheel_width=3,
        wheel_inset=1,
        axles=(-18, 18),
        shell=(
            (-28, 2),
            (-28, 10),
            (-27, 11),
            (-23, 12),
            (-20, 14),
            (-14, 23),
            (-13, 24),
            (27, 24),
            (28, 23),
            (28, 2),
        ),
        cabin=((-24, 4), (26, 4), (26, 22), (-12.7, 22), (-18, 14), (-24, 14)),
        cargo=None,
        dashboard=(-24, -17, 9, 14),
        windshield=(-21, -11, 15, 22),
        rear_window=None,
        side_windows=(((-15.4, 15), (-6, 15), (-6, 21), (-12.7, 21)),),
        seats=(SeatRow(-10, 9, ("driver_seat", "passenger_seat")),),
        lights_y=((9, 11), (10, 14)),
        paint=(225, 225, 220),
        handling="van",
        lift=1,
    ),
    "truck": Design(
        title="box truck: high cab and a closed cargo box, 6.4 x 2.4 x 2.7 m, three axles",
        length=64,
        width=24,
        bottom=3,
        wall=2,
        wheel_diameter=10,
        wheel_width=4,
        wheel_inset=1,
        axles=(-22, 11, 24),
        shell=(
            (-32, 3),
            (-32, 14),
            (-31, 15),
            (-27, 16),
            (-24, 25),
            (-23, 26),
            (-12, 26),
            (-12, 8),
            (-10, 8),
            (-10, 27),
            (32, 27),
            (32, 3),
        ),
        cabin=((-26, 13), (-14, 13), (-14, 24), (-22.3, 24), (-24.3, 18), (-26, 18)),
        cargo=((-9, 9), (31, 9), (31, 26), (-9, 26)),
        dashboard=(-26, -22, 15, 19),
        windshield=(-27, -21, 19, 24),
        rear_window=None,
        side_windows=(((-24, 19), (-15, 19), (-15, 24), (-22.3, 24)),),
        seats=(SeatRow(-19, 16, ("driver_seat", "passenger_seat")),),
        lights_y=((9, 11), (8, 11)),
        paint=(200, 140, 30),
        handling="truck",
        lift=1,
        hollows=(
            ((-30, 6), (-14, 6), (-14, 12), (-30, 12)),  # engine bay under the cab
            ((-9, 4), (31, 4), (31, 8), (-9, 8)),  # chassis under the cargo box
        ),
    ),
}

#: Colors every template defines: name -> (material, rgb, finish). "paint" comes from the design.
COLORS: Final[dict[str, tuple[str, tuple[int, int, int], str]]] = {
    "trim": ("plastic", (35, 35, 38), "matte"),
    "glass": ("glass", (150, 190, 215), "glass"),
    "seat": ("plastic", (70, 60, 55), "matte"),
    "tire": ("plastic", (25, 25, 25), "matte"),
    "rim": ("hard metal", (165, 165, 170), "metal"),
    "headlight": ("glass", (255, 245, 210), "emissive"),
    "taillight": ("glass", (220, 30, 25), "emissive"),
}


@dataclass(frozen=True)
class _Scale:
    """Design voxels to model voxels along Z (X spans follow the width, Y never scales)."""

    kz: float

    def z(self, value: float) -> float:
        return value * self.kz

    def zi(self, value: float) -> int:
        return round(value * self.kz)

    def polygon(self, points: Polygon) -> list[tuple[float, float]]:
        return [(self.z(z), float(y)) for z, y in points]


def _even(value: float) -> int:
    return 2 * round(value / 2)


def _size(given: float | None, design: int, what: str) -> int:
    """Model size in voxels from meters, even, within ``MAX_SCALE_CHANGE`` of the design."""
    if given is None:
        return design
    low, high = design * (1 - MAX_SCALE_CHANGE), design * (1 + MAX_SCALE_CHANGE)
    if not low - 1e-9 <= given * 10 <= high + 1e-9:  # float meters
        raise ProjectError(
            f"{what} must be within {MAX_SCALE_CHANGE:.0%} of the template's "
            f"{design / 10:g} m ({low / 10:.2f} to {high / 10:.2f} m), got {given:g} m"
        )
    # Even, and still within the range after rounding.
    return min(max(_even(given * 10), 2 * math.ceil(low / 2)), 2 * math.floor(high / 2))


def _up(points: Polygon, lift: int) -> Polygon:
    return tuple((z, y + lift) for z, y in points)


def _box_up(box: SideBox, lift: int) -> SideBox:
    z0, z1, y0, y1 = box
    return (z0, z1, y0 + lift, y1 + lift)


def _lifted(d: Design) -> Design:
    """The design with every height raised by ``d.lift`` (and ``lift`` reset to 0)."""
    k = d.lift
    (fy0, fy1), (ry0, ry1) = d.lights_y
    return replace(
        d,
        bottom=d.bottom + k,
        shell=_up(d.shell, k),
        cabin=_up(d.cabin, k),
        cargo=None if d.cargo is None else _up(d.cargo, k),
        hollows=tuple(_up(h, k) for h in d.hollows),
        dashboard=_box_up(d.dashboard, k),
        windshield=_box_up(d.windshield, k),
        rear_window=None if d.rear_window is None else _box_up(d.rear_window, k),
        side_windows=tuple(_up(w, k) for w in d.side_windows),
        seats=tuple(replace(row, y=row.y + k) for row in d.seats),
        lights_y=((fy0 + k, fy1 + k), (ry0 + k, ry1 + k)),
        lift=0,
    )


def template_names() -> list[str]:
    """Names of the templates."""
    return list(DESIGNS)


def apply_template(
    project: Project,
    template: str,
    *,
    length_m: float | None = None,
    width_m: float | None = None,
    paint_rgb: Sequence[int] | None = None,
) -> list[str]:
    """Build a template into an empty vehicle project.

    Args:
        project: A vehicle project without parts.
        template: One of ``DESIGNS``.
        length_m: Body length (default: the template's), within 20 % of it.
        width_m: Body width (default: the template's), within 20 % of it.
        paint_rgb: Body color (default: the template's).

    Returns:
        Lines describing what was built, for the AI.

    Raises:
        ProjectError: Not a vehicle, parts already present, unknown template, size out of
            range, a template color name already used with another material.
    """
    if project.kind != "vehicle":
        raise ProjectError("templates build vehicles: create the project with kind 'vehicle'")
    if project.parts:
        raise ProjectError(
            "templates start from an empty project: this one has parts "
            f"({', '.join(project.parts)}); create a new project"
        )
    if template not in DESIGNS:
        raise ProjectError(f"unknown template {template!r}; templates: {', '.join(DESIGNS)}")
    d = _lifted(DESIGNS[template])
    length = _size(length_m, d.length, "length_m")
    width = _size(width_m, d.width, "width_m")
    s = _Scale(length / d.length)
    project.define_color("paint", "weak metal", tuple(paint_rgb or d.paint), "matte")
    for name, (material, rgb, finish) in COLORS.items():
        project.define_color(name, material, rgb, finish)
    project.set_handling(d.handling)
    project.add_part("body")
    half_w = width // 2
    inner = half_w - d.wall
    _body(project, d, s, half_w, inner)
    seats = _seats(project, d, s, inner, half_w - d.wheel_inset - d.wheel_width)
    lights = _lights(project, d, half_w, length)
    radius = d.wheel_diameter / 2
    inner_x = half_w - d.wheel_inset - d.wheel_width
    axle_y = d.wheel_diameter // 2  # wheels touch the ground
    axle_z: list[int] = []
    for z in d.axles:  # scaled, but never closer than a wheel and a 1-voxel gap
        axle_z.append(max(s.zi(z), axle_z[-1] + d.wheel_diameter + 1) if axle_z else s.zi(z))
    centers = [(float(axle_y), float(z)) for z in axle_z]
    _wheel_wells(project, centers, radius, inner_x, half_w)
    axles = [Axle(z, steer=k == 0, drive=k > 0) for k, z in enumerate(axle_z)]
    layout = WheelLayout(d.wheel_diameter, d.wheel_width, inner_x, axle_y)
    project.add_wheels(axles, layout, "tire", "rim")
    project.set_anchor("vital", (0.0, d.bottom + 4.0, -length / 2 + 6.0))
    project.set_anchor("exhaust", (-half_w / 2, d.bottom + 1.0, length / 2 + 0.5))
    return [
        f"Built template {template!r}: {d.title}.",
        f"Body {width} x {max(y for _, y in d.shell) - d.bottom} x {length} voxels "
        f"(X -{half_w}..{half_w}, Z {-length // 2}..{length // 2}, ground at Y = 0, wheels "
        f"{d.wheel_diameter} voxels at Z {', '.join(str(a.z) for a in axles)}).",
        "Parts: body (shell, cabin, windows, seats, dashboard, lights), "
        + ", ".join(p for p in project.parts if p != "body")
        + ".",
        "Colors: paint, trim, glass, seat, tire, rim, headlight, taillight (redefine them with "
        "define_color to recolor).",
        "Anchors: " + ", ".join(seats + lights + ["vital", "exhaust"]) + ".",
        "Next: preview it, then customize with draw_profile / draw_box (carve, paint, add) and "
        "export_model.",
    ]


def _body(project: Project, d: Design, s: _Scale, half_w: int, inner: int) -> None:
    """Shell, carved cabin and cargo space, dashboard, windows, bumpers and exhaust."""
    round_sides = Bevel(2, "round")
    project.draw(
        "body",
        polygon_profile("side", s.polygon(d.shell), (-half_w, half_w), round_sides),
        "add",
        "paint",
    )
    project.draw(
        "body", polygon_profile("side", s.polygon(d.cabin), (-inner, inner), Bevel()), "carve", None
    )
    if d.cargo is not None:
        cargo = polygon_profile("side", s.polygon(d.cargo), (1 - half_w, half_w - 1), Bevel())
        project.draw("body", cargo, "carve", None)
    for hollow in d.hollows:
        shape = polygon_profile("side", s.polygon(hollow), (-inner, inner), Bevel())
        project.draw("body", shape, "carve", None)
    z0, z1, y0, y1 = d.dashboard
    project.draw("body", box_shape((-inner, y0, s.zi(z0)), (inner, y1, s.zi(z1))), "add", "trim")
    pane = inner - 1  # pillars stay painted
    for box in (d.windshield, d.rear_window):
        if box is None:
            continue
        z0, z1, y0, y1 = box
        project.draw(
            "body", box_shape((-pane, y0, s.zi(z0)), (pane, y1, s.zi(z1))), "paint", "glass"
        )
    for window in d.side_windows:
        shape = polygon_profile("side", s.polygon(window), (-half_w, half_w), Bevel())
        project.draw("body", shape, "paint", "glass")
    front, back = -s.zi(d.length / 2), s.zi(d.length / 2)
    project.draw(
        "body",
        box_shape((-half_w, d.bottom, front), (half_w, d.bottom + 2, front + 2)),
        "paint",
        "trim",
    )
    project.draw(
        "body",
        box_shape((-half_w, d.bottom, back - 2), (half_w, d.bottom + 2, back)),
        "paint",
        "trim",
    )
    pipe_x = -half_w / 2
    project.draw(
        "body",
        cylinder_shape("z", (pipe_x, d.bottom + 1.0), 1, (back - 3, back + 1)),
        "add",
        "trim",
    )


def _seats(project: Project, d: Design, s: _Scale, inner: int, inner_x: int) -> list[str]:
    """Seats (cushion and backrest), steering wheel, and the seat and player anchors."""
    names: list[str] = []
    # Centered in each half of the cabin, but inside the wheel wells' walls (at inner_x - 2).
    seat_x = min(round(inner / 2), inner_x - 3)
    floor = d.bottom + 2
    for row_index, row in enumerate(d.seats):
        z = float(s.zi(row.z))
        for side, name in zip((-1, 1), row.anchors, strict=True):
            x0, x1 = (-inner + 1, -1) if side < 0 else (1, inner - 1)
            cz = round(z)
            project.draw("body", box_shape((x0, floor, cz - 3), (x1, row.y, cz + 3)), "add", "seat")
            project.draw(
                "body", box_shape((x0, floor, cz + 3), (x1, row.y + 5, cz + 5)), "add", "seat"
            )
            point = (float(side * seat_x), float(row.y), z)
            project.set_anchor(name, point)
            names.append(name)
            if name == "driver_seat":
                project.set_anchor("player", suggested_player(point))
                names.append("player")
        if row_index == 0:
            # Steering wheel at the rig's steering point, on a column from the dashboard.
            sx = -seat_x
            wy, wz = row.y + 1, round(z) - 2
            dash_end = s.zi(d.dashboard[1])
            project.draw(
                "body", box_shape((sx - 2, wy, wz), (sx + 2, wy + 3, wz + 1)), "add", "trim"
            )
            if dash_end < wz:  # column from the dashboard to the wheel
                column = box_shape((sx, wy + 1, dash_end), (sx + 1, wy + 2, wz))
                project.draw("body", column, "add", "trim")
    return names


def _arc(center: tuple[float, float], radius: float, steps: int = 12) -> list[tuple[float, float]]:
    """Points ``(z, y)`` of the upper half circle, from the front to the back."""
    y, z = center
    return [
        (z - radius * math.cos(math.pi * k / steps), y + radius * math.sin(math.pi * k / steps))
        for k in range(steps + 1)
    ]


def _wheel_wells(
    project: Project,
    centers: Sequence[tuple[float, float]],
    radius: float,
    inner_x: int,
    half_w: int,
) -> None:
    """Carve wheel arches open to the sides, lined with a 1-voxel trim fender.

    The lining (an upper half ring around each arch in the body color, and a trim wall on the
    wheel's inner side) closes the well towards the cabin or a pickup bed. Every
    lining is drawn before any arch is carved, so close axles do not fill each other's arch.
    """
    arch = radius + 1
    sides = [
        ((-half_w, 1 - inner_x), (1 - inner_x, 2 - inner_x)),
        ((inner_x - 1, half_w), (inner_x - 2, inner_x - 1)),
    ]
    for center in centers:
        ring = _arc(center, arch + 1) + _arc(center, arch)[::-1]
        disk = _arc(center, arch + 1)
        for span, wall in sides:
            project.draw("body", polygon_profile("side", ring, span, Bevel()), "add", "paint")
            project.draw("body", polygon_profile("side", disk, wall, Bevel()), "add", "trim")
    for center in centers:
        for span, _ in sides:
            project.draw("body", cylinder_shape("x", center, arch, span), "carve", None)


def _lights(project: Project, d: Design, half_w: int, length: int) -> list[str]:
    """Emissive lamps on the front and rear faces, with headlight and taillight anchors."""
    names = []
    front, back = -length // 2, length // 2
    (fy0, fy1), (ry0, ry1) = d.lights_y
    x_out, x_in = half_w - 2, half_w - 6
    for side, suffix in ((-1, "l"), (1, "r")):
        xa, xb = sorted((side * x_in, side * x_out))
        project.draw(
            "body", box_shape((xa, fy0, front), (xb, fy1, front + 1)), "paint", "headlight"
        )
        project.draw("body", box_shape((xa, ry0, back - 1), (xb, ry1, back)), "paint", "taillight")
        center = side * (x_in + x_out) / 2
        project.set_anchor(f"headlight_{suffix}", (center, (fy0 + fy1) / 2, front + 1.0))
        project.set_anchor(f"taillight_{suffix}", (center, (ry0 + ry1) / 2, back - 1.0))
        names += [f"headlight_{suffix}", f"taillight_{suffix}"]
    return names
