"""Coherence checks of a mod folder: files, XML references, ``.vox`` objects, manifest positions.

Every rule comes from docs/TEARDOWN_REFERENCE.md (§5-7): mod and ``info.txt`` conventions
(official documentation), ``spawn.txt`` lines (official files, verified in game), ``MOD/`` paths,
vehicle structure and location tags (official files, verified in game), and the positions the
Buildup manifest gives (verified rules). Official usages found in the game's own mods are
accepted (decision D-027). Problems are reported as findings, never fixed.
"""

import json
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from buildup.teardown.assembly import VEHICLE_LOCATIONS
from buildup.teardown.manifest import MANIFEST_VERSION
from buildup.voxio import VoxDocument, VoxFormatError, read_vox
from buildup.voxio.axes import size_to_magica

Level = Literal["error", "warning", "info"]

#: ``info.txt`` tags listed by the official documentation, plus ``Spawn`` (official spawn packs).
KNOWN_TAGS: Final = ("Map", "Gameplay", "Asset", "Vehicle", "Tool", "Spawn")
#: Official documentation: Latin letters, digits and spaces in mod names.
MOD_FOLDER_PATTERN: Final = re.compile(r"[A-Za-z0-9 ]+")
#: Official documentation: the Workshop preview image is at most 1 MB.
MAX_PREVIEW_BYTES: Final = 1024 * 1024
#: Positions are compared to the manifest with this tolerance (meters).
POSITION_TOLERANCE: Final = 0.0011
#: More XML files than this are not checked (a whole level, or a wrong folder).
MAX_XML_FILES: Final = 2000
MOD_PREFIX: Final = "MOD/"
#: Path prefixes of official files whose targets this check cannot locate.
OTHER_PREFIXES: Final = ("LEVEL/", "BUILT-IN/", "RAW:")
#: Lines starting with this are comments in official info.txt and spawn.txt files.
COMMENT: Final = "#"
BOM: Final = b"\xef\xbb\xbf"
#: Files that make a mod do something (official documentation, reference §7).
CONTENT_FILES: Final = ("main.xml", "main.lua")


@dataclass(frozen=True)
class Finding:
    """One problem or remark.

    Attributes:
        level: ``error`` (will not work as written: missing file or object, broken XML, no
            name), ``warning`` (may not work, or differs from official usage) or ``info``
            (not checked, or unusual but seen in official files).
        file: Path relative to the mod folder (``""`` for the folder itself).
        message: What is wrong and how to fix it.
    """

    level: Level
    file: str
    message: str


@dataclass
class _Context:
    folder: Path
    manifests: Mapping[str, Mapping[str, Any]]
    findings: list[Finding] = field(default_factory=list)
    documents: dict[Path, VoxDocument | None] = field(default_factory=dict)
    stale: set[str] = field(default_factory=set)

    def add(self, level: Level, file: str, message: str) -> None:
        self.findings.append(Finding(level, file, message))

    def relative(self, path: Path) -> str:
        try:
            return path.relative_to(self.folder).as_posix()
        except ValueError:
            return str(path)


def validate_mod(
    folder: Path, manifests: Mapping[str, Mapping[str, Any]] | None = None
) -> list[Finding]:
    """Check a mod folder.

    Args:
        folder: The mod folder (containing ``info.txt``).
        manifests: Buildup manifests by their ``vox_file`` (``MOD/vox/<name>.vox``, see
            ``manifests_in``); objects of those files get their XML positions compared.

    Returns:
        Findings, errors first.
    """
    ctx = _Context(folder.resolve(), manifests or {})
    if not ctx.folder.is_dir():
        ctx.add("error", "", f"mod folder not found: {folder}")
        return ctx.findings
    if not MOD_FOLDER_PATTERN.fullmatch(ctx.folder.name):
        ctx.add(
            "warning",
            "",
            f"folder name {ctx.folder.name!r}: use only Latin letters, digits and spaces in mod "
            "names (official documentation)",
        )
    _check_info(ctx)
    prefabs = _check_spawn(ctx)
    preview = ctx.folder / "preview.jpg"
    if preview.is_file() and preview.stat().st_size > MAX_PREVIEW_BYTES:
        ctx.add("warning", "preview.jpg", "larger than 1 MB, the Workshop limit")
    xml_files = sorted(p for p in ctx.folder.rglob("*.xml") if p.is_file())
    if len(xml_files) > MAX_XML_FILES:
        ctx.add(
            "info",
            "",
            f"{len(xml_files)} XML files: only the first {MAX_XML_FILES} (sorted by path) and "
            "those in spawn.txt were checked",
        )
        xml_files = sorted(set(xml_files[:MAX_XML_FILES]) | prefabs)
    for path in xml_files:
        _check_xml(ctx, path, spawned=path in prefabs)
    if not prefabs and not any((ctx.folder / f).is_file() for f in CONTENT_FILES):
        ctx.add(
            "info",
            "",
            "no spawn.txt entry, no main.xml and no main.lua: if this mod should add something "
            "to spawn, write spawn.txt (official mods also add content in other ways)",
        )
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(ctx.findings, key=lambda f: order[f.level])


def _read_text(ctx: _Context, path: Path) -> str:
    """Text of a mod text file; a UTF-8 byte order mark is reported, then ignored."""
    data = path.read_bytes()
    if data.startswith(BOM):
        ctx.add(
            "warning",
            ctx.relative(path),
            "starts with a UTF-8 byte order mark (BOM): official files have none and whether "
            "Teardown reads it is not verified; save the file as UTF-8 without BOM",
        )
    return data.decode("utf-8-sig", errors="replace")


def _check_info(ctx: _Context) -> None:
    path = ctx.folder / "info.txt"
    if not path.is_file():
        ctx.add(
            "error", "info.txt", "missing: every mod needs an info.txt (official documentation)"
        )
        return
    values: dict[str, str] = {}
    for number, raw in enumerate(_read_text(ctx, path).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(COMMENT):
            continue
        if "=" not in line:
            ctx.add("warning", "info.txt", f"line {number} is not 'key = value': {line!r}")
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        values[key] = value

    def has(key: str) -> bool:  # official mods also use localized keys such as en_name
        return any(v for k, v in values.items() if k == key or k.endswith("_" + key))

    if not has("name"):
        ctx.add("error", "info.txt", "no 'name = ...' line")
    for key in ("author", "description"):
        if not has(key):
            ctx.add("warning", "info.txt", f"no '{key} = ...' line")
    # Official files separate tags with commas or spaces, in any case ("Map Gameplay").
    tags = [t for t in re.split(r"[,\s]+", values.get("tags", "")) if t]
    known = {t.lower() for t in KNOWN_TAGS}
    if not tags:
        ctx.add("info", "info.txt", f"no tags; documented tags: {', '.join(KNOWN_TAGS)}")
    for tag in tags:
        if tag.lower() not in known:
            ctx.add(
                "info",
                "info.txt",
                f"tag {tag!r} is not a documented tag ({', '.join(KNOWN_TAGS)})",
            )


def _check_spawn(ctx: _Context) -> set[Path]:
    """Check spawn.txt; return the prefab files it points to."""
    path = ctx.folder / "spawn.txt"
    prefabs: set[Path] = set()
    if not path.is_file():
        return prefabs
    for number, raw in enumerate(_read_text(ctx, path).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(COMMENT):
            continue
        if ":" not in line:
            ctx.add(
                "error",
                "spawn.txt",
                f"line {number}: expected 'path/to/prefab.xml : Category/Name', got {line!r}",
            )
            continue
        target, label = (part.strip() for part in line.split(":", 1))
        if "/" not in label:
            ctx.add(
                "info",
                "spawn.txt",
                f"line {number}: the name {label!r} has no category ('Category/Name'); official "
                "spawn files mostly use one",
            )
        prefab = _inside(ctx, target)
        if not target.lower().endswith(".xml"):
            ctx.add("error", "spawn.txt", f"line {number}: {target!r} is not an .xml prefab")
        elif prefab is None or not prefab.is_file():
            ctx.add(
                "error",
                "spawn.txt",
                f"line {number}: {target!r} not found (paths start at the mod folder)",
            )
        else:
            prefabs.add(prefab)
    return prefabs


def _inside(ctx: _Context, relative: str) -> Path | None:
    """``relative`` resolved in the mod folder, or ``None`` if it points outside it."""
    try:
        target = (ctx.folder / relative.lstrip("/\\")).resolve()
    except (OSError, ValueError):  # NUL characters, invalid names
        return None
    return target if target == ctx.folder or ctx.folder in target.parents else None


def _check_xml(ctx: _Context, path: Path, *, spawned: bool) -> None:
    name = ctx.relative(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        ctx.add("error", name, f"XML syntax error: {error}")
        return
    except (LookupError, OSError, ValueError) as error:  # unknown encoding, unreadable file
        ctx.add("error", name, f"cannot read this XML file: {error}")
        return
    if spawned and root.tag != "prefab":
        ctx.add("warning", name, f"root element is <{root.tag}>, official prefabs use <prefab>")
    parents = {child: parent for parent in root.iter() for child in parent}
    for element in root.iter():
        where = _describe(element)
        for attribute in ("pos", "rot"):
            if attribute in element.attrib and _vector(element.get(attribute)) is None:
                ctx.add(
                    "warning",
                    name,
                    f"{where}: {attribute}={element.get(attribute)!r} is not 1 to 3 numbers "
                    "separated by spaces",
                )
        if "file" in element.attrib:
            _check_file_reference(ctx, name, element, where)
    for vehicle in root.iter("vehicle"):
        _check_vehicle(ctx, name, vehicle)
    _check_positions(ctx, name, root, parents)


def _describe(element: ET.Element) -> str:
    keys = ("name", "object", "tags", "file")
    detail = " ".join(f'{k}="{element.get(k)}"' for k in keys if element.get(k))
    return f"<{element.tag}{' ' + detail if detail else ''}>"


def _vector(text: str | None) -> tuple[float, float, float] | None:
    """Parse ``"x y z"``; official files also write 1 or 2 numbers (the rest read as 0 here)."""
    if text is None:
        return None
    parts = text.split()
    if not 1 <= len(parts) <= 3:
        return None
    parts += ["0"] * (3 - len(parts))
    try:
        values = tuple(float(p) for p in parts)
    except ValueError:
        return None
    if not all(math.isfinite(v) for v in values):
        return None
    return (values[0], values[1], values[2])


def _rotated(element: ET.Element) -> bool:
    """Whether the element has a non-zero ``rot`` (``rot="0 0 0"``, common, changes nothing)."""
    rot = element.get("rot")
    if rot is None:
        return False
    vector = _vector(rot)
    return vector is None or any(v != 0 for v in vector)


def _check_file_reference(ctx: _Context, name: str, element: ET.Element, where: str) -> None:
    reference = element.get("file", "")
    if not reference.startswith(MOD_PREFIX):
        if not reference.startswith(OTHER_PREFIXES):
            ctx.add(
                "info",
                name,
                f"{where}: {reference!r} not checked (only MOD/ paths, from the mod folder, are)",
            )
        return
    target = _inside(ctx, reference[len(MOD_PREFIX) :])
    if target is None:
        ctx.add("error", name, f"{where}: {reference} points outside the mod folder")
        return
    if not target.is_file():
        ctx.add("error", name, f"{where}: file {reference} not found in the mod folder")
        return
    if element.tag == "vox" and element.get("object"):
        document = _document(ctx, target)
        if document is None:
            return
        objects = {i.name for i in document.instances if i.name is not None}
        obj = element.get("object", "")
        if obj not in objects:
            known = ", ".join(sorted(objects)) or "none"
            ctx.add(
                "error",
                name,
                f"{where}: {reference} has no object {obj!r}; its objects: {known}",
            )


def _document(ctx: _Context, vox: Path) -> VoxDocument | None:
    if vox not in ctx.documents:
        try:
            ctx.documents[vox] = read_vox(vox)
        except (OSError, VoxFormatError) as error:
            ctx.add("warning", ctx.relative(vox), f"cannot read this .vox file: {error}")
            ctx.documents[vox] = None
    return ctx.documents[vox]


def _check_vehicle(ctx: _Context, name: str, vehicle: ET.Element) -> None:
    if vehicle.find(".//instance") is not None:
        ctx.add(
            "info",
            name,
            f"{_describe(vehicle)} is built from <instance> elements: its structure is not checked",
        )
        return
    if next(vehicle.iter("body"), None) is None:
        ctx.add("error", name, f"{_describe(vehicle)} has no <body>")
    wheels = list(vehicle.iter("wheel"))
    if not wheels:
        ctx.add("info", name, f"{_describe(vehicle)} has no <wheel> (official boats have none)")
    for wheel in wheels:
        if wheel.find("vox") is None:
            ctx.add("error", name, f"{_describe(wheel)} has no <vox>: the wheel has no shape")
    tags = {t for loc in vehicle.iter("location") for t in loc.get("tags", "").split()}
    if "player" not in tags and "nodrive" not in vehicle.get("tags", "").split():
        ctx.add(
            "warning",
            name,
            f"{_describe(vehicle)}: no location tagged player (official vehicles without one are "
            "tagged nodrive)",
        )
    missing = [t for t in VEHICLE_LOCATIONS if t != "player" and t not in tags]
    if missing:
        ctx.add(
            "info",
            name,
            f"{_describe(vehicle)}: no location tagged {', '.join(missing)} (most official cars "
            "have vital and exhaust; some boats and machines do not)",
        )


def _manifest_for(ctx: _Context, name: str, vox: ET.Element) -> Mapping[str, Any] | None:
    """The manifest of a vox element's file, if it exists and matches the mod's ``.vox``."""
    reference = vox.get("file", "")
    manifest = ctx.manifests.get(reference)
    if manifest is None or reference in ctx.stale:
        return None
    target = _inside(ctx, reference[len(MOD_PREFIX) :])
    document = _document(ctx, target) if target is not None and target.is_file() else None
    if document is None:
        return None
    sizes = {
        i.name: tuple(int(v) for v in document.models[i.model_index].shape)
        for i in document.instances
        if i.name is not None
    }
    for obj in manifest["objects"]:
        x, y, z = obj["size_vox"]
        if sizes.get(obj["name"]) != size_to_magica((x, y, z)):
            ctx.stale.add(reference)
            ctx.add(
                "warning",
                name,
                f"{reference} does not match the manifest of project {manifest['name']!r} "
                f"(object {obj['name']!r} differs): the mod holds another export; export again "
                "and copy the new files, positions were not compared",
            )
            return None
    return manifest


def _check_positions(
    ctx: _Context, name: str, root: ET.Element, parents: Mapping[ET.Element, ET.Element]
) -> None:
    """Compare vox, wheel and location positions with the Buildup manifests."""
    for vox in root.iter("vox"):
        obj = vox.get("object")
        manifest = _manifest_for(ctx, name, vox) if obj else None
        if manifest is None:
            continue
        objects = {o["name"]: o for o in manifest["objects"]}
        if obj not in objects:
            continue
        parent = parents.get(vox)
        # Positions are relative to the parent body or wheel (reference §5); a rotated object or
        # another parent is a deliberate change that this check cannot follow.
        if parent is None or parent.tag not in ("body", "wheel"):
            ctx.add("info", name, f"{_describe(vox)}: not inside a body or wheel, not compared")
            continue
        if _rotated(vox) or (parent.tag == "wheel" and _rotated(parent)):
            ctx.add("info", name, f"{_describe(vox)}: rotated, position not compared")
            continue
        project = manifest["name"]
        if parent.tag == "wheel":
            _compare_wheel(ctx, name, vox, parent, manifest)
            continue
        expected = tuple(objects[obj]["vox_pos_m"])
        _compare(ctx, name, vox, expected, f"project {project!r}: vox_pos_m")
        # A location is relative to its vox (reference §5): it must sit at the anchor relative
        # to the model's geometry, whatever the vox pos (a wrong vox pos is reported above).
        anchors = {a["name"]: a for a in manifest["anchors"] if a["location_tag"]}
        for location in vox.iter("location"):
            for tag in location.get("tags", "").split():
                if tag in anchors:
                    point = anchors[tag]["position_m"]
                    want = tuple(point[i] - expected[i] for i in range(3))
                    _compare(ctx, name, location, want, f"project {project!r}: anchor minus vox")
    for body in root.iter("body"):
        _compare_body_locations(ctx, name, body)


def _compare_body_locations(ctx: _Context, name: str, body: ET.Element) -> None:
    """Locations directly in a body are in the body frame: compare them with the anchors."""
    locations = [e for e in body if e.tag == "location"]
    if not locations:
        return
    found = [_manifest_for(ctx, name, v) for v in body if v.tag == "vox" and v.get("object")]
    manifests = {m["name"]: m for m in found if m is not None}
    if len(manifests) != 1:
        return
    (manifest,) = manifests.values()
    anchors = {a["name"]: a for a in manifest["anchors"] if a["location_tag"]}
    for location in locations:
        for tag in location.get("tags", "").split():
            if tag in anchors:
                want = tuple(anchors[tag]["position_m"])
                _compare(ctx, name, location, want, f"project {manifest['name']!r}: anchor")


def _compare_wheel(
    ctx: _Context, name: str, vox: ET.Element, wheel: ET.Element, manifest: Mapping[str, Any]
) -> None:
    by_object = {w["object"]: w for w in manifest["wheels"]}
    data = by_object.get(vox.get("object", ""))
    if data is None:
        return
    project = manifest["name"]
    _compare(ctx, name, wheel, tuple(data["axle_m"]), f"project {project!r}: axle_m")
    _compare(
        ctx, name, vox, tuple(data["vox_pos_in_wheel_m"]), f"project {project!r}: wheel vox pos"
    )


def _compare(
    ctx: _Context, name: str, element: ET.Element, expected: tuple[float, ...], what: str
) -> None:
    pos = _vector(element.get("pos")) or (0.0, 0.0, 0.0)
    if any(abs(pos[i] - expected[i]) > POSITION_TOLERANCE for i in range(3)):
        want = " ".join(f"{v:g}" for v in expected)
        ctx.add(
            "warning",
            name,
            f"{_describe(element)}: pos {' '.join(f'{v:g}' for v in pos)} differs from the "
            f"manifest ({what} = {want}); the model will not sit where it was built",
        )


def _is_vec3(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(v, int | float) and not isinstance(v, bool) for v in value)
    )


def _valid_manifest(data: object) -> bool:
    """Whether ``data`` is a manifest of the current version with every field this check reads."""
    if not isinstance(data, dict) or data.get("manifest_version") != MANIFEST_VERSION:
        return False
    if not isinstance(data.get("name"), str) or not isinstance(data.get("vox_file"), str):
        return False
    lists = [data.get(key) for key in ("objects", "wheels", "anchors")]
    if not all(isinstance(v, list) for v in lists):
        return False
    objects, wheels, anchors = (v if isinstance(v, list) else [] for v in lists)
    return (
        all(
            isinstance(o, dict)
            and isinstance(o.get("name"), str)
            and _is_vec3(o.get("size_vox"))
            and _is_vec3(o.get("vox_pos_m"))
            for o in objects
        )
        and all(
            isinstance(w, dict)
            and isinstance(w.get("object"), str)
            and _is_vec3(w.get("axle_m"))
            and _is_vec3(w.get("vox_pos_in_wheel_m"))
            for w in wheels
        )
        and all(
            isinstance(a, dict)
            and isinstance(a.get("name"), str)
            and _is_vec3(a.get("position_m"))
            and "location_tag" in a
            for a in anchors
        )
    )


def manifests_in(folders: Iterable[Path]) -> dict[str, dict[str, Any]]:
    """Read ``export/manifest.json`` files by ``vox_file``.

    Unreadable files, other manifest versions and manifests missing a field are skipped.
    """
    found: dict[str, dict[str, Any]] = {}
    for folder in folders:
        path = folder / "export" / "manifest.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if _valid_manifest(data):
            found[data["vox_file"]] = data
    return found
