"""A model ready for export: placed objects, wheels, anchors and palette, plus coherence checks.

Positions are in the model frame: the Teardown frame (X right, Y up, front is -Z) in voxels
(1 voxel = 0.1 m), with the vehicle body placed at the frame origin (the skeleton gives the
``body`` element no ``pos``). Points such as wheel axles and anchors are continuous coordinates:
voxel ``i`` spans ``i`` to ``i + 1``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np

from buildup.palette import Palette
from buildup.voxcore import EMPTY, Grid, Vec3, components
from buildup.voxio import MAX_MODEL_SIZE, xml_origin

Kind = Literal["vehicle", "prop"]
KINDS: Final = ("vehicle", "prop")
Point = tuple[float, float, float]

#: Location tags read by vehicles (docs/TEARDOWN_REFERENCE.md §6, FILES; effect verified in
#: game for our calibration car, §5).
VEHICLE_LOCATIONS: Final = ("player", "vital", "exhaust")


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
    """

    name: str
    kind: Kind
    body: tuple[PlacedObject, ...]
    wheels: tuple[Wheel, ...]
    anchors: Mapping[str, Point]
    palette: Palette
    color_names: Mapping[int, str]

    @property
    def objects(self) -> list[PlacedObject]:
        """Every object: body objects first, then wheels."""
        return [*self.body, *(w.obj for w in self.wheels)]


def check_assembly(assembly: Assembly) -> list[str]:
    """Check that the model can be exported and list what may go wrong in game.

    Returns:
        Warnings (export still possible): missing vehicle locations, overlapping objects,
        objects made of several face-connected parts.

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
    warnings: list[str] = []
    if assembly.kind == "vehicle":
        missing = [tag for tag in VEHICLE_LOCATIONS if tag not in assembly.anchors]
        if missing:
            warnings.append(
                "missing vehicle anchors: "
                + ", ".join(missing)
                + " (official vehicles use player, vital and exhaust locations; set them with "
                "set_anchor)"
            )
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
