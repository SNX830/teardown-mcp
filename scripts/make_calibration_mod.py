"""Generate the 0.2.0 calibration mod (docs/TESTING_IN_GAME.md, protocol C).

The mod has two spawnable prefabs. Their XML is written by hand below from the conventions of
docs/TEARDOWN_REFERENCE.md, on purpose without any generator logic, so that the in-game test checks
those conventions and nothing else:

- "Calibration prop": four blocks with one marker voxel at the origin corner and at the +X, +Y and
  +Z ends of their grid (odd sizes, even sizes, and the even block with ``rot="0 90 0"`` and
  ``rot="90 90 0"``).
- "Calibration car": a box car with four cylinder wheels, white lights at the front (-Z), red
  lights at the rear (+Z) and a green stripe on its right side (+X).

Each prefab carries a read-only Lua probe (templates in ``scripts/calibration/``) that shows on
screen what the engine did: grid sizes, shape positions, axis directions, marker positions, wheel
positions and ground contact.

Usage:
    uv run python scripts/make_calibration_mod.py [output folder]

Default output: workspace/calibration/BuildupCalibration (copy that folder into
Documents/Teardown/mods to test).
"""

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from string import Template

import numpy as np
import numpy.typing as npt

from buildup.palette import Finish, Material, Palette
from buildup.voxio import VoxObject, write_vox

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).resolve().parent / "calibration"
DEFAULT_OUTPUT = ROOT / "workspace" / "calibration" / "BuildupCalibration"

#: Shown by the probes, to make sure Nathan runs the latest generated files.
CALIBRATION_VERSION = "v1"
PREFAB_VERSION = "2.0.0"  # docs/TEARDOWN_REFERENCE.md: current scenes/prefabs use 2.0.0
VOX_PATH = "vox/calibration.vox"
VOX_FILE = f"MOD/{VOX_PATH}"

Vec3 = tuple[int, int, int]
Grid = npt.NDArray[np.uint8]

# --- Prop -------------------------------------------------------------------------------------

#: Grid sizes (Teardown frame, voxels). All three axes differ, so a swapped axis is visible.
ODD_SIZE: Vec3 = (5, 7, 9)
EVEN_SIZE: Vec3 = (6, 8, 10)


@dataclass(frozen=True)
class ProbedVox:
    """A vox element of prop.xml (positions in voxels, body frame; rotation in degrees)."""

    tag: str
    label: str
    object_name: str
    size: Vec3
    pos_vox: Vec3
    rot_deg: Vec3 = (0, 0, 0)


PROP_ELEMENTS = (
    ProbedVox("cal_odd", "ODD", "cal_odd", ODD_SIZE, (-8, 0, 0)),
    ProbedVox("cal_even", "EVEN", "cal_even", EVEN_SIZE, (8, 0, 0)),
    # One-axis turn: sign and pivot of XML rot.
    ProbedVox("cal_rot", "ROT", "cal_even", EVEN_SIZE, (0, 0, 15), (0, 90, 0)),
    # Two-axis turn: order in which the XML Euler angles are applied (the result differs).
    ProbedVox("cal_rot2", "ROT2", "cal_even", EVEN_SIZE, (0, 6, -20), (90, 90, 0)),
)


def marker_cells(size: Vec3) -> dict[str, Vec3]:
    """Marker voxels of a prop block: origin corner, then the far end along +X, +Y and +Z."""
    sx, sy, sz = size
    return {"O": (0, 0, 0), "X": (sx - 1, 0, 0), "Y": (0, sy - 1, 0), "Z": (0, 0, sz - 1)}


# --- Car --------------------------------------------------------------------------------------

#: Every car size is even, so that no half-voxel question applies to the car.
BODY_SIZE: Vec3 = (16, 6, 36)
BODY_VOX_POS: Vec3 = (0, 3, 0)  # body bottom 0.3 m above the ground
WHEEL_DIAMETER = 8
WHEEL_WIDTH = 2
VEHICLE_TAG = "cal_car"
BODY_TAG = "cal_car_body"


@dataclass(frozen=True)
class Wheel:
    """A wheel of car.xml: ``center_vox`` is the axle center in the body frame, in voxels."""

    name: str
    center_vox: Vec3
    steer: bool
    drive: bool

    @property
    def tag(self) -> str:
        """Tag of the wheel's vox, used by the probe."""
        return f"cal_wheel_{self.name}"

    @property
    def object_name(self) -> str:
        """Object name in the .vox file."""
        return f"wheel_{self.name}"


# Wheels outside the body (1 voxel gap), axle at the wheel radius above the ground (y = 0).
WHEELS = (
    Wheel("fl", (-10, 4, -12), steer=True, drive=False),
    Wheel("fr", (10, 4, -12), steer=True, drive=False),
    Wheel("bl", (-10, 4, 12), steer=False, drive=True),
    Wheel("br", (10, 4, 12), steer=False, drive=True),
)

#: Locations in the body frame (voxels). The driver sits on the left (-X), as in official cars.
LOCATIONS: dict[str, Vec3] = {
    "player": (-4, 11, 2),
    "vital": (0, 6, -14),
    "exhaust": (5, 4, 19),
}


# --- Models -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Colors:
    """Palette indices used by the calibration models."""

    prop_base: int
    marker: dict[str, int]
    body: int
    front_light: int
    rear_light: int
    right_stripe: int
    tire: int
    spoke: int


def make_palette() -> tuple[Palette, Colors]:
    """Allocate the palette entries of the calibration mod."""
    palette = Palette()
    plastic = Material.PLASTIC
    colors = Colors(
        prop_base=palette.index_for(Material.CONCRETE, (160, 160, 160)),
        marker={
            "O": palette.index_for(plastic, (20, 20, 20)),
            "X": palette.index_for(plastic, (230, 30, 30)),
            "Y": palette.index_for(plastic, (30, 200, 30)),
            "Z": palette.index_for(plastic, (30, 60, 230)),
        },
        body=palette.index_for(Material.WEAK_METAL, (90, 110, 150), Finish.metal(0.4)),
        front_light=palette.index_for(Material.HARD_METAL, (255, 250, 220), Finish.emissive()),
        rear_light=palette.index_for(Material.HARD_METAL, (255, 30, 20), Finish.emissive()),
        right_stripe=palette.index_for(plastic, (30, 200, 30)),
        tire=palette.index_for(plastic, (35, 35, 35)),
        spoke=palette.index_for(plastic, (230, 230, 230)),
    )
    return palette, colors


def prop_grid(size: Vec3, colors: Colors) -> Grid:
    """A full block of the base color with the four marker voxels."""
    grid = np.full(size, colors.prop_base, dtype=np.uint8)
    for name, cell in marker_cells(size).items():
        grid[cell] = colors.marker[name]
    return grid


def body_grid(colors: Colors) -> Grid:
    """Box body: front lights on the -Z face, rear lights on the +Z face, stripe on the +X face."""
    sx, _, sz = BODY_SIZE
    grid = np.full(BODY_SIZE, colors.body, dtype=np.uint8)
    for x0 in (1, sx - 4):
        grid[x0 : x0 + 3, 3:5, 0] = colors.front_light
        grid[x0 : x0 + 3, 3:5, sz - 1] = colors.rear_light
    grid[sx - 1, 4, :] = colors.right_stripe
    return grid


def wheel_grid(colors: Colors) -> Grid:
    """Disc of ``WHEEL_DIAMETER`` voxels in the (y, z) plane, axle along X, with a white spoke."""
    radius = WHEEL_DIAMETER / 2
    centers = np.arange(WHEEL_DIAMETER) + 0.5 - radius
    disc = centers[:, None] ** 2 + centers[None, :] ** 2 <= radius**2
    plane = np.where(disc, colors.tire, 0).astype(np.uint8)
    middle = WHEEL_DIAMETER // 2
    plane[middle - 1 : middle + 1, :] = np.where(disc[middle - 1 : middle + 1, :], colors.spoke, 0)
    return np.repeat(plane[None, :, :], WHEEL_WIDTH, axis=0)


def build_objects(colors: Colors) -> list[VoxObject]:
    """All objects of calibration.vox.

    Their origins only lay them out in MagicaVoxel: a prefab places an object by its XML ``pos``,
    not by its position in the file (docs/TEARDOWN_REFERENCE.md §5, DEDUCED; a large ``pos-xml``
    reading in game would reveal the contrary).
    """
    objects = [
        VoxObject("cal_odd", prop_grid(ODD_SIZE, colors), (-30, 0, -40)),
        VoxObject("cal_even", prop_grid(EVEN_SIZE, colors), (-20, 0, -40)),
        VoxObject("car_body", body_grid(colors), (-8, 3, -18)),
    ]
    for wheel in WHEELS:
        cx, cy, cz = wheel.center_vox
        origin = (cx - WHEEL_WIDTH // 2, cy - WHEEL_DIAMETER // 2, cz - WHEEL_DIAMETER // 2)
        objects.append(VoxObject(wheel.object_name, wheel_grid(colors), origin))
    return objects


# --- Text files -------------------------------------------------------------------------------


def meters(value_vox: int) -> str:
    """Format a length in voxels as meters for XML/Lua (1 voxel = 0.1 m), e.g. -12 -> "-1.2"."""
    return f"{value_vox / 10:g}"


def xml_vec(vox: Vec3) -> str:
    """Format a voxel vector as an XML "x y z" string in meters."""
    return " ".join(meters(v) for v in vox)


def lua_vec(vox: Vec3) -> str:
    """Format a voxel vector as a Lua table in meters (plain tables are Teardown vectors)."""
    return "{ " + ", ".join(meters(v) for v in vox) + " }"


def lua_ints(values: Vec3) -> str:
    """Format three integers as a Lua table."""
    return "{ " + ", ".join(str(v) for v in values) + " }"


def sub(a: Vec3, b: Vec3) -> Vec3:
    """Component-wise ``a - b``."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _xml_text(root: ET.Element) -> str:
    ET.indent(root, space="\t")
    return ET.tostring(root, encoding="unicode") + "\n"


def prop_xml() -> str:
    """The prop prefab: one dynamic body holding the three probed blocks."""
    prefab = ET.Element("prefab", version=PREFAB_VERSION)
    group = ET.SubElement(prefab, "group", name="Buildup calibration prop")
    script = ET.SubElement(group, "script", file="MOD/script/prop.lua")
    body = ET.SubElement(script, "body", dynamic="true")
    for element in PROP_ELEMENTS:
        ET.SubElement(
            body,
            "vox",
            tags=element.tag,
            pos=xml_vec(element.pos_vox),
            rot=" ".join(str(r) for r in element.rot_deg),
            file=VOX_FILE,
            object=element.object_name,
        )
    return _xml_text(prefab)


def car_xml() -> str:
    """The car prefab: vehicle > body > (body vox with locations, four wheels with their vox)."""
    prefab = ET.Element("prefab", version=PREFAB_VERSION)
    group = ET.SubElement(prefab, "group", name="Buildup calibration car")
    script = ET.SubElement(group, "script", file="MOD/script/car.lua")
    vehicle = ET.SubElement(
        script, "vehicle", tags=VEHICLE_TAG, spring="0.5", damping="0.7", topspeed="60"
    )
    body = ET.SubElement(vehicle, "body", dynamic="true")
    body_vox = ET.SubElement(
        body, "vox", tags=BODY_TAG, pos=xml_vec(BODY_VOX_POS), file=VOX_FILE, object="car_body"
    )
    # Children of a vox are placed relative to the vox origin (TEARDOWN_REFERENCE.md §5).
    for tag, pos in LOCATIONS.items():
        ET.SubElement(body_vox, "location", tags=tag, pos=xml_vec(sub(pos, BODY_VOX_POS)))
    for wheel in WHEELS:
        element = ET.SubElement(
            body,
            "wheel",
            name=wheel.name,
            pos=xml_vec(wheel.center_vox),
            drive="1" if wheel.drive else "0",
            steer="1" if wheel.steer else "0",
            travel="-0.1 0.1",
        )
        # Bottom-center origin: the vox origin is one radius below the axle.
        ET.SubElement(
            element,
            "vox",
            tags=wheel.tag,
            pos=xml_vec((0, -WHEEL_DIAMETER // 2, 0)),
            file=VOX_FILE,
            object=wheel.object_name,
        )
    return _xml_text(prefab)


def prop_lua(colors: Colors) -> str:
    """Fill the prop probe template."""
    shapes = []
    for element in PROP_ELEMENTS:
        markers = ", ".join(
            f"{name} = {lua_ints(cell)}" for name, cell in marker_cells(element.size).items()
        )
        shapes.append(
            f'\t{{ tag = "{element.tag}", label = "{element.label}", '
            f"pos = {lua_vec(element.pos_vox)}, rot = {lua_ints(element.rot_deg)}, "
            f"size = {lua_ints(element.size)},\n\t\tmarkers = {{ {markers} }} }},"
        )
    template = Template((TEMPLATES / "prop.lua").read_text(encoding="utf-8"))
    return template.substitute(
        version=CALIBRATION_VERSION,
        marker_o=colors.marker["O"],
        marker_x=colors.marker["X"],
        marker_y=colors.marker["Y"],
        marker_z=colors.marker["Z"],
        shapes="\n".join(shapes),
    )


def car_lua() -> str:
    """Fill the car probe template."""
    wheels = "\n".join(
        f'\t{{ tag = "{w.tag}", label = "{w.name}", pos = {lua_vec(w.center_vox)} }},'
        for w in WHEELS
    )
    template = Template((TEMPLATES / "car.lua").read_text(encoding="utf-8"))
    return template.substitute(
        version=CALIBRATION_VERSION,
        vehicle_tag=VEHICLE_TAG,
        body_tag=BODY_TAG,
        body_vox_pos=lua_vec(BODY_VOX_POS),
        wheels=wheels,
        wheel_radius=meters(WHEEL_DIAMETER // 2),
        locations="\n".join(
            f'\t{{ tag = "{tag}", pos = {lua_vec(pos)} }},' for tag, pos in LOCATIONS.items()
        ),
    )


INFO_TXT = """\
name = Buildup Calibration
author = Buildup
description = Calibration objects for the Buildup MCP server. Spawn them, read the values on screen.
tags = Asset
"""

SPAWN_TXT = """\
prefab/prop.xml : Buildup/Calibration prop
prefab/car.xml : Buildup/Calibration car
"""


def build_mod(output: Path) -> list[Path]:
    """Write the whole calibration mod into ``output`` and return the written files."""
    palette, colors = make_palette()
    files = {
        "info.txt": INFO_TXT,
        "spawn.txt": SPAWN_TXT,
        "prefab/prop.xml": prop_xml(),
        "prefab/car.xml": car_xml(),
        "script/prop.lua": prop_lua(colors),
        "script/car.lua": car_lua(),
    }
    written = []
    for relative, text in files.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)
    vox_path = output / VOX_PATH
    vox_path.parent.mkdir(parents=True, exist_ok=True)
    write_vox(vox_path, build_objects(colors), palette)
    written.append(vox_path)
    return written


def main() -> int:
    """Write the calibration mod and print where it is."""
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    written = build_mod(output)
    print(f"Wrote {len(written)} files to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
