"""A model ready for export: placed objects, wheels, anchors and palette, plus coherence checks.

Positions are in the model frame: the Teardown frame (X right, Y up, front is -Z) in voxels
(1 voxel = 0.1 m), with the vehicle body placed at the frame origin (the skeleton gives the
``body`` element no ``pos``). Points such as wheel axles and anchors are continuous coordinates:
voxel ``i`` spans ``i`` to ``i + 1``.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np

from buildup.palette import Palette
from buildup.teardown.anchors import (
    VEHICLE_LOCATIONS,
    Point,
    anchor_role,
    player_in_range,
    rig_points,
    suggested_player,
)
from buildup.teardown.handling import DEFAULT_HANDLING, HANDLING
from buildup.voxcore import EMPTY, Grid, Vec3, components
from buildup.voxio import MAX_MODEL_SIZE, xml_origin

Kind = Literal["vehicle", "prop"]
KINDS: Final = ("vehicle", "prop")

__all__ = [
    "KINDS",
    "VEHICLE_LOCATIONS",
    "Assembly",
    "AssemblyError",
    "Kind",
    "PlacedObject",
    "Point",
    "Wheel",
    "check_assembly",
]


class AssemblyError(ValueError):
    """The model cannot be exported as it is (no body, no wheels on a vehicle...)."""


@dataclass(frozen=True, eq=False)
class PlacedObject:
    """One named voxel object at its place in the model frame.

    Attributes:
        name: Object name in the ``.vox`` file (XML ``object="..."``).
        grid: Non-empty grid, cropped to its voxels, at most 256 per edge.
        origin: Model-frame position of the grid's minimum corner, in voxels.
    """

    name: str
    grid: Grid
    origin: Vec3

    def __post_init__(self) -> None:
        if not np.any(self.grid != EMPTY):
            raise AssemblyError(f"object {self.name!r} is empty")
        if any(not 1 <= s <= MAX_MODEL_SIZE for s in self.grid.shape):
            raise AssemblyError(f"object {self.name!r} is larger than {MAX_MODEL_SIZE} voxels")

    @property
    def size(self) -> Vec3:
        """Grid size in voxels."""
        x, y, z = self.grid.shape
        return (x, y, z)

    @property
    def end(self) -> Vec3:
        """Model-frame position just past the grid's maximum corner."""
        return (
            self.origin[0] + self.size[0],
            self.origin[1] + self.size[1],
            self.origin[2] + self.size[2],
        )

    @property
    def vox_pos(self) -> Vec3:
        """Model-frame point that a Teardown XML ``vox`` ``pos`` designates for this object.

        ``origin + xml_origin(size)``: the rule measured in game (docs/TEARDOWN_REFERENCE.md §5),
        always whole voxels.
        """
        ox, oy, oz = self.origin
        dx, dy, dz = xml_origin(self.size)
        return (ox + dx, oy + dy, oz + dz)


@dataclass(frozen=True)
class Wheel:
    """A vehicle wheel.

    Attributes:
        name: Wheel name in the XML (``fl``, ``fr``, ``bl``, ``br``...).
        obj: The wheel's voxel object.
        axle: Model-frame center of the wheel (axle), continuous voxel coordinates.
        steer: Whether the wheel steers.
        drive: Whether the engine drives the wheel.
    """

    name: str
    obj: PlacedObject
    axle: Point
    steer: bool
    drive: bool

    @property
    def vox_offset(self) -> Point:
        """Position of the wheel object's ``vox`` inside its ``wheel`` element (voxels).

        The ``wheel`` ``pos`` is the axle and children are placed from it
        (docs/TEARDOWN_REFERENCE.md §5, GAME).
        """
        px, py, pz = self.obj.vox_pos
        ax, ay, az = self.axle
        return (px - ax, py - ay, pz - az)


@dataclass(frozen=True)
class Assembly:
    """Everything an export writes.

    Attributes:
        name: Model name (also the ``.vox`` file name).
        kind: ``"vehicle"`` (a body with wheels) or ``"prop"`` (one dynamic body).
        body: Objects attached to the main body, in file order.
        wheels: Wheels (vehicles only).
        anchors: Named points (continuous voxel coordinates).
        palette: Palette with an entry for every index the objects use.
        color_names: Name of each palette index, for the manifest.
        handling: Driving preset of a vehicle (``buildup.teardown.handling``).
    """

    name: str
    kind: Kind
    body: tuple[PlacedObject, ...]
    wheels: tuple[Wheel, ...]
    anchors: Mapping[str, Point]
    palette: Palette
    color_names: Mapping[int, str]
    handling: str = DEFAULT_HANDLING

    @property
    def objects(self) -> list[PlacedObject]:
        """Every object: body objects first, then wheels."""
        return [*self.body, *(w.obj for w in self.wheels)]


def check_assembly(assembly: Assembly) -> list[str]:
    """Check that the model can be exported and list what may go wrong in game.

    Returns:
        Warnings (export still possible): missing vehicle locations, seats that do not fit
        the body, overlapping objects, objects made of several face-connected parts.

    Raises:
        AssemblyError: If the model has no body object, if a vehicle has no wheel, or if a
            prop has wheels.
    """
    if not assembly.body:
        raise AssemblyError("the model has no body part with voxels: draw at least one part")
    if assembly.kind == "vehicle" and not assembly.wheels:
        raise AssemblyError("a vehicle needs wheels: add them with add_wheels")
    if assembly.kind == "prop" and assembly.wheels:
        raise AssemblyError("a prop cannot have wheels")
    if assembly.handling not in HANDLING:
        raise AssemblyError(f"unknown handling preset {assembly.handling!r}")
    warnings: list[str] = []
    if assembly.kind == "vehicle":
        missing = [tag for tag in VEHICLE_LOCATIONS if tag not in assembly.anchors]
        if missing:
            warnings.append(
                "missing vehicle anchors: "
                + ", ".join(missing)
                + " (every drivable official vehicle has a player location and most official cars "
                "have vital and exhaust; set them with set_anchor)"
            )
        warnings += _seat_warnings(assembly)
    objects = assembly.objects
    for i, a in enumerate(objects):
        for b in objects[i + 1 :]:
            overlap = _overlap(a, b)
            if overlap:
                warnings.append(
                    f"objects {a.name!r} and {b.name!r} share {overlap} voxel positions: "
                    "how the game handles overlapping objects is not verified; avoid overlaps "
                    "by carving one of them"
                )
    for obj in objects:
        parts = components(obj.grid)
        if len(parts) > 1:
            warnings.append(
                f"object {obj.name!r} is made of {len(parts)} separate pieces (voxels that "
                "touch only by an edge or a corner do not hold together): inspect it and join "
                "or remove the small pieces"
            )
    return warnings


def _fmt(point: Point) -> str:
    return "[" + ", ".join(f"{v:g}" for v in point) + "]"


def _solid(objects: tuple[PlacedObject, ...], cell: Vec3) -> bool:
    """Whether a body object has a voxel at a model-frame cell."""
    for obj in objects:
        local = [cell[i] - obj.origin[i] for i in range(3)]
        inside = all(0 <= local[i] < obj.size[i] for i in range(3))
        if inside and obj.grid[local[0], local[1], local[2]] != EMPTY:
            return True
    return False


def _cell(point: Point) -> Vec3:
    return (math.floor(point[0]), math.floor(point[1]), math.floor(point[2]))


def _floor_below(objects: tuple[PlacedObject, ...], point: Point) -> bool:
    """Whether a body voxel is at a point or under it, in its column (feet rest on a floor)."""
    x, y, z = _cell(point)
    lowest = min(obj.origin[1] for obj in objects)
    return any(_solid(objects, (x, h, z)) for h in range(y, lowest - 1, -1))


def _seat_warnings(assembly: Assembly) -> list[str]:
    """Seats (rigs) that would show the character through the body or hanging below it."""
    anchors = assembly.anchors
    warnings: list[str] = []
    seat = anchors.get("driver_seat")
    if seat is None:
        warnings.append(
            "no driver_seat anchor: without a driver rig the driver is shown hanging below the "
            "player location (verified in game: feet out under the car); set driver_seat at "
            "the driver's hip point, about 0 to 3 voxels above the seat or floor voxels"
        )
    elif "player" not in anchors:
        warnings.append(
            f"driver_seat is set but not player: official cars put player at "
            f"{_fmt(suggested_player(seat))} for this seat (0.6 m above, 0.3 m behind)"
        )
    elif not player_in_range(seat, anchors["player"]):
        warnings.append(
            f"player {_fmt(anchors['player'])} is far from where official cars put it for the "
            f"driver_seat: about {_fmt(suggested_player(seat))} (0.5 to 0.9 m above the seat "
            "point, -0.3 to +0.35 m along Z); the view and the seated driver may not match"
        )
    seats = sorted(n for n in anchors if anchor_role(n).xml in ("driver_rig", "passenger_rig"))
    for name in seats:
        points = rig_points(anchors[name], driver=name == "driver_seat")
        inside = [
            part for part in ("seat", "ik_head") if _solid(assembly.body, _cell(points[part]))
        ]
        if inside:
            warnings.append(
                f"{name}: the character's {' and '.join(p.removeprefix('ik_') for p in inside)} "
                f"point ({', '.join(_fmt(points[p]) for p in inside)}) is inside the body's "
                "voxels: carve the cabin or move the seat (the head point is 5.5 voxels above "
                "and 3 behind the seat point)"
            )
        hanging = [
            foot
            for foot in ("ik_foot_l", "ik_foot_r")
            if not _floor_below(assembly.body, points[foot])
        ]
        if hanging:
            feet = ", ".join(_fmt(points[f]) for f in hanging)
            warnings.append(
                f"{name}: no body voxel under the feet ({feet}, 1.5 voxels below and 6 in front "
                "of the seat point): the legs would hang below the body; add a cabin floor or "
                "move the seat"
            )
    return warnings


def _overlap(a: PlacedObject, b: PlacedObject) -> int:
    """Number of model-frame cells filled in both objects."""
    lo = [max(a.origin[i], b.origin[i]) for i in range(3)]
    hi = [min(a.end[i], b.end[i]) for i in range(3)]
    if any(lo[i] >= hi[i] for i in range(3)):
        return 0

    def window(obj: PlacedObject) -> Grid:
        s = [slice(lo[i] - obj.origin[i], hi[i] - obj.origin[i]) for i in range(3)]
        return obj.grid[s[0], s[1], s[2]]

    return int(np.count_nonzero((window(a) != EMPTY) & (window(b) != EMPTY)))
