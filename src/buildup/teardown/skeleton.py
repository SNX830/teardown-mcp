"""Minimal, known-good XML prefab skeleton generated from an assembly (decision D-006).

The structure verified in game by the 0.2.0 calibration (docs/TEARDOWN_REFERENCE.md §5-7):
``prefab > group > vehicle > body > vox (+ location) + wheel > vox`` for vehicles and
``prefab > group > body > vox`` for props, positions in meters, no rotations of objects. For
seat and light anchors (``buildup.teardown.anchors``) it also writes driver and passenger
``rig`` elements and ``light`` elements as official cars do (reference §5-6; driver rig and
lights verified in game), and the project's handling preset on the ``vehicle`` element
(``buildup.teardown.handling``). The user's AI then tunes it and adds scripts.
"""

import re
import xml.etree.ElementTree as ET
from typing import Final

from buildup.teardown.anchors import (
    DRIVER_RIG,
    HEADLIGHT,
    PASSENGER_RIG,
    TAILLIGHT,
    anchor_role,
)
from buildup.teardown.assembly import VEHICLE_LOCATIONS, Assembly, Point
from buildup.teardown.handling import handling

#: Prefab version of current official scenes and prefabs (docs/TEARDOWN_REFERENCE.md, header).
PREFAB_VERSION: Final = "2.0.0"


#: Wheel suspension travel used by most official vehicles and by the calibration car (§6).
WHEEL_TRAVEL: Final = "-0.1 0.1"


def meters(value_vox: float) -> str:
    """Format voxels as meters for XML (1 voxel = 0.1 m): ``-12`` -> ``"-1.2"``.

    Positions in this project are multiples of half a voxel, so three decimals are exact.
    """
    text = f"{value_vox / 10:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def xml_vec(point: Point | tuple[int, int, int]) -> str:
    """Format a point in voxels as an XML ``"x y z"`` string in meters."""
    return " ".join(meters(v) for v in point)


def vox_file_path(name: str) -> str:
    """Path of the model's ``.vox`` file as the XML references it (``MOD/`` is the mod folder)."""
    return f"MOD/vox/{name}.vox"


def _relative(point: Point, origin: Point | tuple[int, int, int]) -> Point:
    return (point[0] - origin[0], point[1] - origin[1], point[2] - origin[2])


def _seat_order(name: str) -> int:
    """``passenger_seat`` first, then ``passenger_seat_2``, ``_3``... in number order."""
    found = re.search(r"_(\d+)$", name)
    return int(found.group(1)) if found else 1


def _add_rig(body: ET.Element, name: str, tags: str, seat: Point, *, driver: bool) -> None:
    rig = ET.SubElement(body, "rig", name=name, tags=tags, pos=xml_vec(seat))
    for location, offset, rot in DRIVER_RIG if driver else PASSENGER_RIG:
        ET.SubElement(rig, "location", name=location, tags=location, pos=xml_vec(offset), rot=rot)


def _vehicle_anchors(vox: ET.Element, assembly: Assembly, vox_pos: Point) -> None:
    """Lights and locations inside the first body vox, positioned from its pos point."""
    for name, point in assembly.anchors.items():
        use = anchor_role(name).xml
        if use in ("headlight", "taillight"):
            attributes = HEADLIGHT if use == "headlight" else TAILLIGHT
            ET.SubElement(vox, "light", {"pos": xml_vec(_relative(point, vox_pos)), **attributes})
    for tag in VEHICLE_LOCATIONS:
        if tag in assembly.anchors:
            relative = _relative(assembly.anchors[tag], vox_pos)
            ET.SubElement(vox, "location", tags=tag, pos=xml_vec(relative))


def _rigs(body: ET.Element, assembly: Assembly) -> None:
    if "driver_seat" in assembly.anchors:
        _add_rig(body, "driver", "driver sort=0", assembly.anchors["driver_seat"], driver=True)
    passengers = sorted(
        (n for n in assembly.anchors if anchor_role(n).xml == "passenger_rig"), key=_seat_order
    )
    for number, name in enumerate(passengers, start=1):
        _add_rig(body, "passenger", f"sort={number}", assembly.anchors[name], driver=False)


def skeleton_xml(assembly: Assembly, group_name: str) -> str:
    """Write the prefab skeleton of an assembly.

    Body objects are ``vox`` elements of the body at their measured ``pos``; anchors named like
    vehicle locations (``player``, ``vital``, ``exhaust``) become ``location`` children of the
    first body object, positioned from its origin, and ``headlight*`` / ``taillight*`` anchors
    ``light`` children. Wheels are ``wheel`` elements at their axle with the wheel object
    inside. ``driver_seat`` and ``passenger_seat*`` anchors become ``rig`` elements of the body,
    after the wheels, positioned at the seat point.

    Args:
        assembly: The checked model (see ``check_assembly``).
        group_name: Name of the prefab's ``group``.

    Returns:
        The XML text, tab-indented, ending with a newline.
    """
    vox_file = vox_file_path(assembly.name)
    prefab = ET.Element("prefab", version=PREFAB_VERSION)
    group = ET.SubElement(prefab, "group", name=group_name)
    if assembly.kind == "vehicle":
        vehicle = ET.SubElement(group, "vehicle", handling(assembly.handling).attributes)
        body = ET.SubElement(vehicle, "body", dynamic="true")
    else:
        body = ET.SubElement(group, "body", dynamic="true")
    for k, obj in enumerate(assembly.body):
        vox = ET.SubElement(body, "vox", pos=xml_vec(obj.vox_pos), file=vox_file, object=obj.name)
        if k == 0 and assembly.kind == "vehicle":
            px, py, pz = obj.vox_pos
            _vehicle_anchors(vox, assembly, (float(px), float(py), float(pz)))
    for wheel in assembly.wheels:
        element = ET.SubElement(
            body,
            "wheel",
            name=wheel.name,
            pos=xml_vec(wheel.axle),
            drive="1" if wheel.drive else "0",
            steer="1" if wheel.steer else "0",
            travel=WHEEL_TRAVEL,
        )
        ET.SubElement(
            element, "vox", pos=xml_vec(wheel.vox_offset), file=vox_file, object=wheel.obj.name
        )
    if assembly.kind == "vehicle":
        _rigs(body, assembly)
    ET.indent(prefab, space="\t")
    return ET.tostring(prefab, encoding="unicode") + "\n"
