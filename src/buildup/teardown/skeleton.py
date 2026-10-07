"""Minimal, known-good XML prefab skeleton generated from an assembly (decision D-006).

Only structures and attributes verified in game by the 0.2.0 calibration are written
(docs/TEARDOWN_REFERENCE.md §5-7): ``prefab > group > vehicle > body > vox (+ location) + wheel >
vox`` for vehicles and ``prefab > group > body > vox`` for props, positions in meters, no
rotations. The user's AI then tunes parameters and adds lights, sounds and scripts.
"""

import xml.etree.ElementTree as ET
from typing import Final

from buildup.teardown.assembly import VEHICLE_LOCATIONS, Assembly, Point

#: Prefab version of current official scenes and prefabs (docs/TEARDOWN_REFERENCE.md, header).
PREFAB_VERSION: Final = "2.0.0"

#: Vehicle parameters of the calibration car, which drove correctly in game (§5). Official
#: typical values: spring 0.5, damping 0.7, topspeed 60-90 (§6).
VEHICLE_DEFAULTS: Final = {"spring": "0.5", "damping": "0.7", "topspeed": "60"}

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


def skeleton_xml(assembly: Assembly, group_name: str) -> str:
    """Write the prefab skeleton of an assembly.

    Body objects are ``vox`` elements of the body at their measured ``pos``; anchors named like
    vehicle locations (``player``, ``vital``, ``exhaust``) become ``location`` children of the
    first body object, positioned from its origin. Wheels are ``wheel`` elements at their axle
    with the wheel object inside.

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
        vehicle = ET.SubElement(group, "vehicle", VEHICLE_DEFAULTS)
        body = ET.SubElement(vehicle, "body", dynamic="true")
    else:
        body = ET.SubElement(group, "body", dynamic="true")
    for k, obj in enumerate(assembly.body):
        vox = ET.SubElement(body, "vox", pos=xml_vec(obj.vox_pos), file=vox_file, object=obj.name)
        if k == 0 and assembly.kind == "vehicle":
            for tag in VEHICLE_LOCATIONS:
                if tag in assembly.anchors:
                    x, y, z = assembly.anchors[tag]
                    px, py, pz = obj.vox_pos
                    ET.SubElement(vox, "location", tags=tag, pos=xml_vec((x - px, y - py, z - pz)))
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
    ET.indent(prefab, space="\t")
    return ET.tostring(prefab, encoding="unicode") + "\n"
