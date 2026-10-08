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

Structure written by export_model's skeleton. The vox, location and wheel parts are verified
in game with Buildup's calibration car; the absence of a script wrapper follows official
prefabs; the light and driver rig elements follow official cars and work in game (verified
with Buildup vehicles; passenger rigs are not verified):

<prefab version="2.0.0">
  <group name="...">
    <vehicle sound="..." spring="..." topspeed="..." ...>   (the project's handling preset)
      <body dynamic="true">
        <vox pos="..." file="MOD/vox/NAME.vox" object="body">
          <light pos="..." rot="0 180 0" type="cone" .../>  (headlight_* anchor; shines forward)
          <light pos="..." type="area" color="1 .1 .1" .../> (taillight_* anchor; faces back)
          <location tags="player" pos="..."/>   (driver view point; relative to the vox pos)
          <location tags="vital" pos="..."/>    (official tag; its meaning is not documented)
          <location tags="exhaust" pos="..."/>  (exhaust smoke; verified in game)
        </vox>
        <wheel name="fl" pos="AXLE" drive="0" steer="1" travel="-0.1 0.1">
          <vox pos="..." file="MOD/vox/NAME.vox" object="wheel_fl"/>
        </wheel>
        ... one wheel element per wheel ...
        <rig name="driver" tags="driver sort=0" pos="SEAT">   (driver_seat anchor)
          <location name="seat" tags="seat" pos="0 0 0" rot="80 0 0"/>
          <location name="ik_head" tags="ik_head" pos="0 0.55 0.3" rot="0 90 0"/>
          ... ik_hand_l, ik_hand_r, ik_foot_l, ik_foot_r, steeringwheel ...
        </rig>
        <rig name="passenger" tags="sort=1" pos="SEAT"> ... </rig>  (passenger_seat anchors)
      </body>
    </vehicle>
  </group>
</prefab>

Rules:
- Keep the pos values of the skeleton unless you move parts; they come from the manifest.
- Official wheel names: fl/bl on the left (-X), fr/br on the right (+X) (official files).
- Vehicle parameters: the skeleton writes the project's handling preset (set_handling):
  'car', 'sports', 'offroad', 'van' and 'truck' are the parameter sets of an official
  saloon car, Crownzygot, Taskmaster pickup, van and semi truck (official files), 'basic' the
  calibration car's (spring 0.5, damping 0.7, topspeed 60). In game, Buildup vehicles with
  the basic values (and low bodies) all sat nearly on the ground, steered
  badly and reached the same speed, slower when heavier. With 'car' and 'sports' Buildup
  cars steer normally and reach about 90 and 120 km/h (verified in game: topspeed reads as
  km/h); 'offroad', 'van' and 'truck' are not verified on Buildup models yet. Parameters
  seen in official files: sound, spring, damping, topspeed, acceleration, strength,
  antispin, antiroll, difflock, steerassist, friction, smokeintensity, brokenthreshold; their
  effects are not documented. Wheel attributes: drive, steer, travel (typically "-0.1 0.1").
- Ground clearance (official files): official cars have their lowest body voxel 0.1-0.3 m
  above the bottom of the wheels, vans and pickups 0.3 m, trucks and off-road vehicles
  0.4-0.6 m. In game, a Buildup car with 0.2 m under the body looked right.
- Verified in game: a vehicle without a sound attribute still has an engine sound; without
  driver rig the driver is shown hanging below the player location (feet out under the car);
  with Buildup's driver rig the driver sits inside, and the view is at the player location.
- Rigs (official files): a rig gives a seated character its pose; its locations are
  relative to the rig pos. Official cars put the rig's head 0.57 m (Buildup: 0.55 m, half a
  voxel grid) above and 0.3 m behind
  the seat location, the feet 0.6 m in front and 0.15 m below, the hands 0.2 m in front, and
  the player location 0.6 m above and 0.3 m behind the seat. Trucks and machines use an
  upright seat (rot "0 0 0").
- Lights (official files): headlights are cone lights (color "1 .9 .8", scale 20, angle 90,
  penumbra 30), rear lights red area lights; both sit about 0.1 m inside the lamp surface.
  A light without rot shines towards +Z: a headlight in a vox without rot needs
  rot="0 180 0" (verified in game: Buildup's headlights light the ground in front).
- Official vehicles also use sounds and scripts; Buildup does not generate them.
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
containing ERROR, for example "File not found". It holds the latest game run only (verified
in game). Use read_game_log(mod="<Mod Name>") after the user has played; a local mod appears
there as local-<mod name in lower case with dashes>.

Lua runtime errors are not in the log: the game shows them on screen only (verified in
game). Ask the user for that text after a test.

Check the mod with validate_mod before the user tests it.
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
(glows). Glass material with the glass finish is see-through in game and breaks when shot
(verified in game); previews draw it see-through too. Glass material with the emissive finish
glows and breaks (verified in game): use it for lamps. Official cars: body paint in weak
metal, windows in glass with a glass finish, lights emissive (official files).
"""


_WORKFLOW = """\
WORKFLOW FOR A VEHICLE

0. If the user can, ask for a reference picture of the vehicle (a photo or a drawing) and
   follow its proportions and details: a Buildup car built from a photo was judged much more
   realistic than ones built from a short description.
1. create_project(name, kind="vehicle").
2. Fastest: start_from_template (sedan, suv, pickup, van, truck) builds a complete vehicle
   (cabin, windows, seats, lights, wheels, anchors); then customize it and go to step 7.
   Otherwise:
3. define_color for each color (material + RGB): body paint (weak metal), windows (glass),
   tires, lights (glass with finish emissive)...
4. add_part("body"), then draw it: draw_profile (a side silhouette extruded across the width,
   with rounded sides) for the body, then draw_box / cut_edges / draw_wedge / draw_cylinder /
   draw_ellipsoid to carve the cabin and windows and add details. Coordinates are model-frame
   voxels; ground at Y = 0, front at -Z. Official sizes (width x height x length): saloon car
   21 x 13 x 44 voxels, SUV 23 x 16 x 49, pickup 25 x 16 x 53, van 27 x 23 x 55 (official
   files). Use mirror_part to make the model symmetric.
   Keep the underbody off the ground like official vehicles: 2-3 voxels for cars, 3 for
   vans and pickups, 4-6 for trucks and off-road vehicles (official files; in game, a
   Buildup car with 2 voxels under the body looked right).
5. add_wheels: under wheel arches carved into the body (official cars have their wheels
   inside the body width), or outside the body with a 1-voxel gap (inner_x = half the body
   width + 1, as on Buildup's calibration car, verified in game). Wheels must not overlap the
   body.
6. set_anchor: driver_seat (the driver's hip point, on the left, negative X, with room for
   the head 5.5 voxels above and a floor under the feet 6 voxels in front), player (the view
   point, 6 voxels above and 3 behind the seat point in official cars), vital (official tag,
   meaning not documented; in the front part of the body), exhaust (smoke comes out there,
   verified in game; at the rear), headlight_l/r and taillight_l/r at the lamp voxels,
   passenger_seat for passengers. set_handling picks the driving parameters of the vehicle's
   kind ('sports' for a racing car, 'truck' for heavy vehicles).
7. preview and inspect after each step: glass is drawn see-through, as in game; check that
   there is a single part per object (voxels touching only by edges may fall apart when
   damaged) and no overlaps.
8. export_model (fix its warnings: they name the seat, overlap or loose-piece problem), then
   write info.txt and spawn.txt (teardown_reference("mod_files")) and adjust prefab/NAME.xml
   if needed (teardown_reference("vehicle_xml"); lookup_api for Lua scripts). Run
   validate_mod and fix every error.
9. The user copies the mod folder into Documents\\Teardown\\mods\\ and tests it; then
   read_game_log(mod=...) shows the game's errors for the mod.
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
