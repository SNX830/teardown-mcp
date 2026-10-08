"""Named anchor points: what each name means and what the skeleton writes for it.

An anchor is a named model-frame point. Some names have a role in the XML skeleton
(docs/TEARDOWN_REFERENCE.md §5-6): vehicle locations (``player``, ``vital``, ``exhaust``), seats
(a ``rig`` with the driver's or a passenger's pose), lights (``headlight*``, ``taillight*``).
Every other name, ``hinge_*`` included, is only exported in the manifest.

Rig offsets and light attributes are the medians and typical values of the official cars
(reference §5-6, ``FILES``); how a rig and lights built this way look in game is ``DEDUCED``
and checked by protocol G (docs/TESTING_IN_GAME.md).
"""

import re
from dataclasses import dataclass
from typing import Final, Literal

Point = tuple[float, float, float]

#: Location tags read by vehicles (docs/TEARDOWN_REFERENCE.md §6, FILES; effect verified in
#: game for our calibration car, §5).
VEHICLE_LOCATIONS: Final = ("player", "vital", "exhaust")

XmlUse = Literal["location", "driver_rig", "passenger_rig", "headlight", "taillight", "manifest"]


@dataclass(frozen=True)
class AnchorRole:
    """What an anchor name means.

    Attributes:
        role: Role name (``player``, ``driver_seat``, ``headlight``, ``hinge``, ``custom``...).
        xml: What the vehicle skeleton writes for it (``manifest``: nothing, manifest only).
        meaning: One line for the AI, worded with the fact's verification status.
    """

    role: str
    xml: XmlUse
    meaning: str


_LOCATION_MEANINGS: Final = {
    "player": "driver position: the view point and where the driver is shown (verified in game)",
    "vital": "official vehicle location tag; its meaning is not documented",
    "exhaust": "exhaust smoke comes out there (verified in game)",
}
_PATTERNS: Final[tuple[tuple[re.Pattern[str], AnchorRole], ...]] = (
    (
        re.compile(r"driver_seat"),
        AnchorRole(
            "driver_seat",
            "driver_rig",
            "the driver's hip point: the skeleton writes a driver rig (seated pose) there, "
            "following official cars (not verified in game)",
        ),
    ),
    (
        re.compile(r"passenger_seat(_\d+)?"),
        AnchorRole(
            "passenger_seat",
            "passenger_rig",
            "a passenger's hip point: the skeleton writes a passenger rig there, following "
            "official cars (not verified in game)",
        ),
    ),
    (
        re.compile(r"headlight(_\w+)?"),
        AnchorRole(
            "headlight",
            "headlight",
            "a headlight: the skeleton writes a cone light shining forward, like official cars "
            "(not verified in game)",
        ),
    ),
    (
        re.compile(r"taillight(_\w+)?"),
        AnchorRole(
            "taillight",
            "taillight",
            "a red rear light: the skeleton writes an area light facing back, like official "
            "cars (not verified in game)",
        ),
    ),
    (
        re.compile(r"hinge_\w+"),
        AnchorRole(
            "hinge",
            "manifest",
            "a hinge point for a moving part (doors, ramps): exported in the manifest only",
        ),
    ),
)
CUSTOM: Final = AnchorRole("custom", "manifest", "exported in the manifest only")


def anchor_role(name: str) -> AnchorRole:
    """Role of an anchor name (``CUSTOM`` for names without a role)."""
    if name in VEHICLE_LOCATIONS:
        return AnchorRole(name, "location", _LOCATION_MEANINGS[name])
    for pattern, role in _PATTERNS:
        if pattern.fullmatch(name):
            return role
    return CUSTOM


#: Rig locations relative to the seat point, in voxels (x right, y up, z back), with their XML
#: rotations: medians of the five official cars with a reclined seat (reference §5), rounded
#: to half a voxel (the head's 0.57 m median becomes 5.5 voxels).
DRIVER_RIG: Final[tuple[tuple[str, Point, str], ...]] = (
    ("seat", (0.0, 0.0, 0.0), "80 0 0"),
    ("ik_head", (0.0, 5.5, 3.0), "0 90 0"),
    ("ik_hand_l", (-2.5, 1.5, -2.0), "0 90 0"),
    ("ik_hand_r", (2.5, 1.5, -2.0), "0 90 0"),
    ("ik_foot_l", (-1.5, -1.5, -6.0), "0 90 50"),
    ("ik_foot_r", (1.5, -1.5, -6.0), "0 90 50"),
    ("steeringwheel", (0.0, 1.5, -1.5), "0 -180 0"),
)
PASSENGER_RIG: Final = tuple(
    item for item in DRIVER_RIG if item[0] in ("seat", "ik_head", "ik_foot_l", "ik_foot_r")
)
#: Where official cars put the ``player`` location relative to the driver's seat point (median,
#: voxels), and how far from it a player location is still within the official range.
PLAYER_FROM_SEAT: Final[Point] = (0.0, 6.0, 3.0)
PLAYER_RANGE: Final[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]] = (
    (-1.0, 1.0),
    (5.0, 9.0),
    (-3.0, 3.5),
)

#: Light attributes of the official cars (reference §6); rotations for a vox without ``rot``.
HEADLIGHT: Final[dict[str, str]] = {
    "rot": "0 180 0",
    "type": "cone",
    "color": "1 .9 .8",
    "scale": "20",
    "angle": "90",
    "penumbra": "30",
    "size": "0.1",
    "unshadowed": "0.2",
    "glare": "0.3",
}
TAILLIGHT: Final[dict[str, str]] = {
    "type": "area",
    "color": "1 .1 .1",
    "size": "0.2 0.1",
    "unshadowed": "0.3",
    "glare": "0.2",
}


def suggested_player(seat: Point) -> Point:
    """Player location for a driver seat point, as in official cars."""
    return (
        seat[0] + PLAYER_FROM_SEAT[0],
        seat[1] + PLAYER_FROM_SEAT[1],
        seat[2] + PLAYER_FROM_SEAT[2],
    )


def player_in_range(seat: Point, player: Point) -> bool:
    """Whether the player location sits where official cars put it relative to the seat."""
    return all(lo <= player[i] - seat[i] <= hi for i, (lo, hi) in enumerate(PLAYER_RANGE))


def rig_points(seat: Point, *, driver: bool) -> dict[str, Point]:
    """Model-frame points of a rig's locations for a seat point."""
    layout = DRIVER_RIG if driver else PASSENGER_RIG
    return {name: (seat[0] + dx, seat[1] + dy, seat[2] + dz) for name, (dx, dy, dz), _ in layout}
