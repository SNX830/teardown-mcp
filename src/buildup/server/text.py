"""Plain-text answers of the tools, written for an AI that cannot see the model."""

from pathlib import Path

from buildup.project import ExportResult, Part, Project
from buildup.render import meters
from buildup.teardown import Point


def span(start: int, end: int) -> str:
    """``-8..8`` voxels, as continuous coordinates (end exclusive)."""
    return f"{start}..{end}"


def point_text(point: Point) -> str:
    """A point in voxels and meters: ``(-4, 9, 2) vox = (-0.4, 0.9, 0.2) m``."""
    vox = ", ".join(f"{v:g}" for v in point)
    m = ", ".join(meters(v) for v in point)
    return f"({vox}) vox = ({m}) m"


def part_line(part: Part) -> str:
    """One line about a part: role, extent, size and voxel count."""
    bounds = part.bounds()
    role = f"wheel {part.wheel.position}" if part.wheel is not None else part.role
    if bounds is None:
        return f"{part.name} ({role}): empty"
    start, end = bounds
    size = [end[i] - start[i] for i in range(3)]
    extent = ", ".join(f"{axis} {span(start[i], end[i])}" for i, axis in enumerate("XYZ"))
    size_m = " x ".join(meters(s) for s in size)
    text = f"{part.name} ({role}): {extent} voxels; {size_m} m; {part.voxels} voxels"
    if part.wheel is not None:
        w = part.wheel
        text += (
            f"; axle {point_text(w.axle)}, steer {'yes' if w.steer else 'no'}, "
            f"drive {'yes' if w.drive else 'no'}"
        )
    return text


def edit_result(part: Part, changed: int) -> str:
    """Answer of a drawing tool."""
    if changed == 0:
        return (
            f"Nothing changed: the shape does not touch any voxel of {part.name!r} that this "
            f"mode can change. Part now: {part_line(part)}."
        )
    return f"{changed} voxels changed. Part now: {part_line(part)}."


def project_summary(project: Project, folder: Path, undo_steps: int) -> str:
    """Everything about a project except the voxels."""
    lines = [
        f"Project {project.name!r} ({project.kind}), folder {folder}.",
        f"Description: {project.description or '(none)'}",
        "Frame: X right, Y up, front is -Z; voxels (1 voxel = 0.1 m); ground at Y = 0.",
        "Colors:" if project.colors else "Colors: none (use define_color).",
    ]
    lines += [
        f"  {c.name}: {c.material.value}, rgb{c.rgb}, {c.finish.kind.value} (palette index "
        f"{c.index})"
        for c in project.colors.values()
    ]
    lines.append("Parts:" if project.parts else "Parts: none (use add_part / add_wheels).")
    lines += [f"  {part_line(p)}" for p in project.parts.values()]
    lines.append("Anchors:" if project.anchors else "Anchors: none (use set_anchor).")
    lines += [f"  {name}: {point_text(pt)}" for name, pt in project.anchors.items()]
    lines.append(f"Undo steps available: {undo_steps}.")
    return "\n".join(lines)


def color_legend(project: Project) -> str:
    """Which color name each palette index of the project is."""
    items = [
        f"{c.index} = {c.name}" for c in sorted(project.colors.values(), key=lambda c: c.index)
    ]
    return "Color names by palette index: " + (", ".join(items) if items else "none")


def export_summary(result: ExportResult) -> str:
    """Answer of ``export_model``."""
    manifest = result.manifest
    objects = manifest["objects"]
    lines = [
        f"Exported {manifest['name']!r} into the mod folder {result.mod_folder}",
        f"- {result.vox_path.relative_to(result.mod_folder).as_posix()}: "
        f"{len(objects)} objects ({', '.join(o['name'] for o in objects)})",
    ]
    prefab = result.prefab_path.relative_to(result.mod_folder).as_posix()
    if result.prefab_written:
        lines.append(f"- {prefab}: written from the skeleton below")
    elif result.prefab_path.exists():
        lines.append(f"- {prefab}: already exists, kept (yours to edit)")
    else:
        lines.append(f"- {prefab}: not written (skeleton='never')")
    lines += [
        f"- manifest (JSON, read it for exact positions): {result.manifest_path}",
        f"- skeleton (regenerated on every export): {result.skeleton_path}",
        "",
        "Objects (vox pos = where XML pos points, meters):",
    ]
    lines += [
        f"  {o['name']} ({o['role']}): size {' x '.join(map(str, o['size_vox']))} voxels, "
        f"vox pos {' '.join(f'{v:g}' for v in o['vox_pos_m'])}, materials "
        f"{', '.join(o['materials'])}"
        for o in objects
    ]
    if manifest["wheels"]:
        lines.append("Wheels (XML wheel pos = axle, meters):")
        lines += [
            f"  {w['name']}: object {w['object']}, axle {' '.join(f'{v:g}' for v in w['axle_m'])}, "
            f"diameter {w['diameter_m']:g} m, steer {int(w['steer'])}, drive {int(w['drive'])}"
            for w in manifest["wheels"]
        ]
    if manifest["anchors"]:
        lines.append("Anchors (meters):")
        lines += [
            f"  {a['name']}: {' '.join(f'{v:g}' for v in a['position_m'])}"
            + (" (location in the skeleton)" if a["location_tag"] else "")
            for a in manifest["anchors"]
        ]
    lines.append("Warnings:" if result.warnings else "Warnings: none.")
    lines += [f"  - {w}" for w in result.warnings]
    lines += [
        "",
        "Next steps: write info.txt and spawn.txt in the mod folder (teardown_reference "
        "'mod_files'), adjust the prefab if needed (teardown_reference 'vehicle_xml' or "
        "'prop_xml'), then the user copies the mod folder into Documents\\Teardown\\mods.",
        "",
        "Skeleton XML:",
        result.skeleton.rstrip(),
    ]
    return "\n".join(lines)
