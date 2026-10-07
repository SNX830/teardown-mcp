"""Compile a project into its outputs: ``.vox`` file, manifest and XML prefab skeleton."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from buildup import __version__
from buildup.project.model import Project
from buildup.project.names import ProjectError, check_mod_name
from buildup.teardown import (
    Assembly,
    AssemblyError,
    PlacedObject,
    Wheel,
    build_manifest,
    check_assembly,
    skeleton_xml,
)
from buildup.voxio import VoxObject, write_vox

SkeletonMode = Literal["if_missing", "overwrite", "never"]
SKELETON_MODES: Final = ("if_missing", "overwrite", "never")
GENERATOR: Final = f"buildup-mcp {__version__}"


def build_assembly(project: Project) -> tuple[Assembly, list[str]]:
    """Turn a project into an assembly.

    Returns:
        The assembly and notes about parts left out (empty body parts).

    Raises:
        AssemblyError: If a wheel part is empty.
    """
    notes: list[str] = []
    body: list[PlacedObject] = []
    wheels: list[Wheel] = []
    for part in project.parts.values():
        if part.grid is None:
            if part.wheel is not None:
                raise AssemblyError(f"wheel part {part.name!r} is empty: remove it")
            notes.append(f"part {part.name!r} is empty and was left out")
            continue
        obj = PlacedObject(part.name, part.grid, part.origin)
        if part.wheel is None:
            body.append(obj)
        else:
            w = part.wheel
            wheels.append(Wheel(w.position, obj, w.axle, w.steer, w.drive))
    assembly = Assembly(
        name=project.name,
        kind=project.kind,
        body=tuple(body),
        wheels=tuple(wheels),
        anchors=dict(project.anchors),
        palette=project.palette(),
        color_names=project.color_names(),
    )
    return assembly, notes


@dataclass
class ExportResult:
    """What ``export_project`` wrote.

    Attributes:
        mod_folder: The mod folder (copy it into the game's mods folder).
        vox_path: The ``.vox`` file.
        manifest_path: The manifest (JSON).
        skeleton_path: The freshly generated skeleton (always rewritten).
        prefab_path: The prefab inside the mod folder.
        prefab_written: Whether the skeleton was copied to ``prefab_path`` this time.
        warnings: Problems to fix or to know about before testing in game.
        manifest: The manifest data.
        skeleton: The skeleton XML.
    """

    mod_folder: Path
    vox_path: Path
    manifest_path: Path
    skeleton_path: Path
    prefab_path: Path
    prefab_written: bool
    warnings: list[str] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)
    skeleton: str = ""


def export_project(
    project: Project,
    *,
    project_folder: Path,
    mods_dir: Path,
    mod_name: str,
    skeleton: object = "if_missing",
) -> ExportResult:
    """Write the ``.vox`` file, the manifest and the XML skeleton of a project.

    - ``<mods_dir>/<mod_name>/vox/<project>.vox``: every part as a named object, placed in the
      MagicaVoxel scene as in the model (always rewritten: it is a compiled output).
    - ``<project_folder>/export/manifest.json`` and ``skeleton.xml`` (always rewritten).
    - ``<mods_dir>/<mod_name>/prefab/<project>.xml``: a copy of the skeleton, written according
      to ``skeleton``: ``"if_missing"`` (default; the AI then owns the file), ``"overwrite"``
      or ``"never"``.

    Raises:
        ProjectError: Invalid mod name or skeleton mode.
        AssemblyError: If the model cannot be exported (no body, vehicle without wheels...).
    """
    mod_name = check_mod_name(mod_name)
    if skeleton not in SKELETON_MODES:
        raise ProjectError(f"skeleton must be one of {', '.join(SKELETON_MODES)}, got {skeleton!r}")
    assembly, notes = build_assembly(project)
    warnings = notes + check_assembly(assembly)
    manifest = build_manifest(assembly, GENERATOR)
    xml = skeleton_xml(assembly, project.name)

    mod_folder = mods_dir / mod_name
    vox_path = mod_folder / "vox" / f"{project.name}.vox"
    objects = [VoxObject(o.name, o.grid, o.origin) for o in assembly.objects]
    write_vox(vox_path, objects, assembly.palette)

    export_dir = project_folder / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    skeleton_path = export_dir / "skeleton.xml"
    previous = skeleton_path.read_text(encoding="utf-8") if skeleton_path.is_file() else None
    skeleton_path.write_text(xml, encoding="utf-8")

    prefab_path = mod_folder / "prefab" / f"{project.name}.xml"
    write_prefab = skeleton == "overwrite" or (
        skeleton == "if_missing" and not prefab_path.exists()
    )
    if write_prefab:
        prefab_path.parent.mkdir(parents=True, exist_ok=True)
        prefab_path.write_text(xml, encoding="utf-8")
    elif prefab_path.exists() and previous is not None and previous != xml:
        warnings.append(
            f"the skeleton changed since the last export but {prefab_path.name} was kept: "
            "update its positions from the new skeleton (or export with skeleton='overwrite')"
        )
    return ExportResult(
        mod_folder=mod_folder,
        vox_path=vox_path,
        manifest_path=manifest_path,
        skeleton_path=skeleton_path,
        prefab_path=prefab_path,
        prefab_written=write_prefab,
        warnings=warnings,
        manifest=manifest,
        skeleton=xml,
    )
