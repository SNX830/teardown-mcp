"""Reference texts for the AI that writes a mod's XML and text files.

Every statement here comes from docs/TEARDOWN_REFERENCE.md, with its verification status in
words: "verified in game" (status GAME), "official documentation" (DOC), "seen in official game
files" (FILES), "not verified" (DEDUCED/UNVERIFIED). Keep both in sync: never add a fact here that
is not in the reference document (AGENTS.md rule 3).
"""

from typing import Final

from buildup.palette import MATERIAL_INDICES

_FRAME = """\
COORDINATES AND PLACEMENT (Teardown)

Frame used by every Buildup tool and by Teardown XML positions (verified in game):
- X = right, Y = up, front of a vehicle = -Z (driving forward moves towards -Z; +X is the
  driver's right).
- 1 voxel = 0.1 m. Buildup tools take voxels; XML takes meters.
- Buildup convention (not a game rule): the model frame origin is where the vehicle body sits;
  put the ground at Y = 0 (wheel bottoms at Y = 0), the center line at X = 0, front at negative Z.

Where a vox element's pos points (verified in game): for an object of size (sx, sy, sz) voxels,
pos designates the point (floor(sx/2), 0, sz - floor(sz/2)) voxels from the object's minimum
corner: centered on X and Z (rounded), at the bottom on Y. With whole-voxel positions every voxel
stays on the 0.1 m grid. Buildup's manifest gives this point for every object (vox_pos_m).

Other facts verified in game:
- object="name" places the object by the XML pos only; its position inside the .vox is ignored.
- rot="x y z" (degrees) works like QuatEuler: the X turn is applied first, then Y (the place of
  the Z turn in the order is not verified). Buildup bakes rotations into the voxels and writes
  no rot.
- Children of a vox (location elements) are positioned from the vox's pos point (measured on a
  vox without rot; whether children also follow a vox rot is not verified).
- A wheel element's pos is the axle center; the wheel's own vox inside it is positioned from the
  axle (an object whose pos point is at the bottom of the wheel has pos "0 -radius 0").
"""

_VEHICLE_XML = """\
VEHICLE PREFAB XML

Structure written by export_model's skeleton (each part verified in game with Buildup's
calibration car, except the absence of a script wrapper, which follows official prefabs):

<prefab version="2.0.0">
  <group name="...">
    <vehicle spring="0.5" damping="0.7" topspeed="60">
      <body dynamic="true">
        <vox pos="..." file="MOD/vox/NAME.vox" object="body">
          <location tags="player" pos="..."/>   (driver position; relative to the vox pos)
          <location tags="vital" pos="..."/>    (official tag; its meaning is not documented)
          <location tags="exhaust" pos="..."/>  (exhaust smoke; verified in game)
        </vox>
        <wheel name="fl" pos="AXLE" drive="0" steer="1" travel="-0.1 0.1">
          <vox pos="..." file="MOD/vox/NAME.vox" object="wheel_fl"/>
        </wheel>
        ... one wheel element per wheel ...
      </body>
    </vehicle>
  </group>
</prefab>

Rules:
- Keep the pos values of the skeleton unless you move parts; they come from the manifest.
- Official wheel names: fl/bl on the left (-X), fr/br on the right (+X) (official files).
- Vehicle parameters seen in official files: spring, damping, topspeed, acceleration, strength,
  antispin, antiroll, difflock, steerassist, friction, smokeintensity, brokenthreshold. Ranges over
  official vehicles: topspeed 3-120 (typically 60-90), spring 0.2-25 (typically 0.5), damping
  0.4-25 (typically 0.7). Wheel attributes: drive, steer, travel (typically "-0.1 0.1").
- Verified in game: a vehicle without a sound attribute still has an engine sound; without
  driver rig locations the driver is shown near the player location.
- Official vehicles also use light elements, rig elements (driver animation) and scripts;
  Buildup does not generate them.
"""

_PROP_XML = """\
PROP PREFAB XML

Structure written by export_model's skeleton for a prop (verified in game with Buildup's
calibration prop, except the absence of a script wrapper, which follows official prefabs):

<prefab version="2.0.0">
  <group name="...">
    <body dynamic="true">
      <vox pos="..." file="MOD/vox/NAME.vox" object="part_name"/>
      ... one vox element per part ...
    </body>
  </group>
</prefab>

Static objects become dynamic when spawned from the spawn menu (official documentation).
"""

_MOD_FILES = """\
MOD FILES

A mod is a folder (official documentation). Buildup exports into workspace/mods/<Mod Name>/:
  vox/NAME.vox          written by export_model (do not edit; re-export instead)
  prefab/NAME.xml       skeleton, written by export_model only if missing (you own it)
  info.txt              you write it
  spawn.txt             you write it (for spawnable objects)
Then the user copies the folder into Documents\\Teardown\\mods\\ (Buildup never writes there).

info.txt (official documentation), one "key = value" per line:
  name = My Car
  author = ...
  description = ...
  tags = Vehicle
Tags are comma-separated, among Map, Gameplay, Asset, Vehicle, Tool. Use only Latin letters,
digits and spaces in mod names (official documentation).

spawn.txt (official files; a plain-text category verified in game), one line per object:
  prefab/NAME.xml : Category/Display name
Paths inside the mod start at the mod folder in spawn.txt; in XML they start with MOD/.

Game log (official files): %LOCALAPPDATA%\\Teardown\\log.txt; loading errors appear as lines
containing ERROR, for example "File not found".
"""


def _materials_text() -> str:
    rows = "\n".join(
        f"  {material.value:<13} indices {r.start}-{r.stop - 1} ({len(r)} colors)"
        for material, r in MATERIAL_INDICES.items()
    )
    return f"""\
MATERIALS

In Teardown the palette index of a voxel decides its physical material, never its color
(official documentation). Buildup picks the index for you: define_color(material=...) allocates
one in the right range.

{rows}
  (indices 185-224 and 241-255 are reserved)

Hardness (official documentation; sledgehammer / blowtorch / guns / explosives):
  soft: glass, grass, dirt, plastic, wood, plaster
  medium: concrete, brick, weak metal
  hard (explosives only): hard masonry, hard metal
  unbreakable: heavy metal, rock
Avoid enclosing soft material inside hard material (it gets stuck, official documentation).

Finishes (rendering only, never the physical material): matte, metal, glass, emissive
(glows). Buildup's glass finish uses the material setting of official car windows; it renders
transparent in MagicaVoxel, its look in game is not verified yet. Official cars: body paint in
weak metal, windows in glass with a glass finish, lights emissive (official files).
"""


_WORKFLOW = """\
WORKFLOW FOR A VEHICLE

1. create_project(name, kind="vehicle").
2. define_color for each color (material + RGB): body paint (weak metal), windows (glass),
   tires, lights (finish emissive)...
3. add_part("body"), then draw it with draw_box / draw_wedge / cut_edges / draw_cylinder /
   draw_ellipsoid. Coordinates are model-frame voxels; ground at Y = 0, front at -Z.
   For scale, the official saloon car body is 21 voxels wide, 13 high and 44 long (official
   files). Use mirror_part to make the model symmetric.
4. add_wheels: wheels outside the body with a 1-voxel gap (inner_x = half the body width + 1,
   as on Buildup's calibration car, verified in game), or under wheel arches carved into the
   body. Wheels must not overlap the body.
5. set_anchor for player (driver position: official cars put it on the left, negative X),
   vital (official tag, meaning not documented; the calibration car had it in the front part of
   the body) and exhaust (smoke comes out there, verified in game; the calibration car had it
   at the rear).
6. preview and inspect after each step; check that there is a single part per object
   (voxels touching only by edges may fall apart when damaged) and no overlaps.
7. export_model, then write info.txt and spawn.txt (teardown_reference("mod_files")) and adjust
   prefab/NAME.xml if needed (teardown_reference("vehicle_xml")).
8. The user copies the mod folder into Documents\\Teardown\\mods\\ and tests it.
"""

TOPICS: Final[dict[str, str]] = {
    "workflow": _WORKFLOW,
    "frame": _FRAME,
    "materials": _materials_text(),
    "vehicle_xml": _VEHICLE_XML,
    "prop_xml": _PROP_XML,
    "mod_files": _MOD_FILES,
}


def reference(topic: str) -> str:
    """Text of one reference topic.

    Raises:
        KeyError: If the topic is unknown (the message lists the topics).
    """
    if topic not in TOPICS:
        raise KeyError(f"unknown topic {topic!r}; topics: {', '.join(TOPICS)}")
    return TOPICS[topic]
