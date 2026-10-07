"""The manifest: the contract between an exported model and the AI that writes the mod's XML.

Plain JSON-ready data. ``MANIFEST_VERSION`` is bumped on every incompatible change, because other
people's AIs read it (docs/VERSIONING.md).
"""

from typing import Any, Final

import numpy as np

from buildup.palette import MATERIAL_INDICES
from buildup.teardown.assembly import VEHICLE_LOCATIONS, Assembly, PlacedObject
from buildup.teardown.skeleton import meters, vox_file_path

MANIFEST_VERSION: Final = 1

FRAME: Final = (
    "Teardown body frame: X right, Y up, front is -Z; 1 voxel = 0.1 m. *_vox values are voxels, "
    "*_m values meters. Points are continuous coordinates (voxel i spans i to i + 1). The "
    "vehicle body element sits at the frame origin (no pos)."
)


def _m(values: tuple[float, ...]) -> list[float]:
    return [float(meters(v)) for v in values]


def _object_entry(obj: PlacedObject, role: str, assembly: Assembly) -> dict[str, Any]:
    used = [int(i) for i in np.unique(obj.grid) if i]
    entries = assembly.palette.entries
    materials = sorted({entries[i].material.value for i in used if i in entries})
    return {
        "name": obj.name,
        "role": role,
        "size_vox": list(obj.size),
        "size_m": _m(obj.size),
        "min_corner_vox": list(obj.origin),
        "max_corner_vox": list(obj.end),
        "vox_pos_vox": list(obj.vox_pos),
        "vox_pos_m": _m(obj.vox_pos),
        "voxels": int(np.count_nonzero(obj.grid)),
        "materials": materials,
        "palette_indices": used,
    }


def build_manifest(assembly: Assembly, generator: str) -> dict[str, Any]:
    """Describe an exported model.

    Args:
        assembly: The exported model.
        generator: Name and version of the program that wrote it.

    Returns:
        A JSON-ready dictionary: frame, ``.vox`` path, objects with sizes and XML positions,
        wheels with axle positions, anchors, palette.
    """
    objects = [_object_entry(obj, "body", assembly) for obj in assembly.body]
    objects += [_object_entry(w.obj, "wheel", assembly) for w in assembly.wheels]
    wheels = [
        {
            "name": w.name,
            "object": w.obj.name,
            "axle_vox": list(w.axle),
            "axle_m": _m(w.axle),
            "diameter_m": float(meters(w.obj.size[1])),
            "width_m": float(meters(w.obj.size[0])),
            "steer": w.steer,
            "drive": w.drive,
            "vox_pos_in_wheel_m": _m(w.vox_offset),
        }
        for w in assembly.wheels
    ]
    anchors = [
        {
            "name": name,
            "position_vox": list(point),
            "position_m": _m(point),
            "location_tag": (
                name if assembly.kind == "vehicle" and name in VEHICLE_LOCATIONS else None
            ),
        }
        for name, point in assembly.anchors.items()
    ]
    palette = [
        {
            "index": index,
            "name": assembly.color_names.get(index),
            "material": entry.material.value,
            "rgb": list(entry.color),
            "finish": entry.finish.kind.value,
        }
        for index, entry in sorted(assembly.palette.entries.items())
    ]
    return {
        "manifest_version": MANIFEST_VERSION,
        "generator": generator,
        "name": assembly.name,
        "kind": assembly.kind,
        "frame": FRAME,
        "vox_file": vox_file_path(assembly.name),
        "objects": objects,
        "wheels": wheels,
        "anchors": anchors,
        "palette": palette,
        "material_index_ranges": {
            material.value: [r.start, r.stop - 1] for material, r in MATERIAL_INDICES.items()
        },
    }
