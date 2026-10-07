# Teardown and .vox reference

Facts the code relies on. **Every fact has a status and a source.** Do not rely on anything that is not
here; add new facts with their source (rule 3 in `AGENTS.md`).

| Status | Meaning |
|---|---|
| `DOC` | Stated in the official modding documentation (https://www.teardowngame.com/modding/) |
| `FILES` | Observed in official game files (Teardown install: `data/`, `mods/` built-in mods, `dlcs/`) |
| `SPEC` | Stated in the official .vox specification (github.com/ephtracy/voxel-model) |
| `REF` | Documented by the open-source reference implementation `ogt_vox` (MIT, opengametools) |
| `MV` | Verified visually in MagicaVoxel 0.99.7.2 with a file written by our code (says nothing about Teardown itself) |
| `GAME` | Measured in Teardown by the 0.2.0 calibration probes (Nathan, 2026-10-06, game as installed that day), or observed by Nathan in the 0.4.0 acceptance test (2026-10-07, "Petite Rouge" car built by a fresh Claude Code session) |
| `DEDUCED` | Inferred from official files, consistent but not directly stated; must be confirmed in game |
| `UNVERIFIED` | Hypothesis; must not be relied on without a test |

Game version at the time of analysis: scenes/prefabs use `version="2.0.0"` (2026-09-30).

## 1. MagicaVoxel and file versions

- `DOC` Teardown is "tested with models created in MagicaVoxel up to version 0.99.6.4".
- `FILES` The game ships 2 697 `.vox` files in version 150 and 701 in version 200; both load.
  Official vehicle `.vox` files are version 150.
- `FILES` MagicaVoxel 0.99.7.2 (the version Nathan uses) saves version 200. In version 200, `MATL`
  dictionaries omit default keys (for example no `_type` for diffuse).
- Decision D-003: our writer produces **version 150 with explicit `MATL` entries**, like official files.

## 2. .vox chunk layout (as found in official files)

`VOX ` + version (int32), then `MAIN` containing:

- per model: `SIZE` (x, y, z as int32) then `XYZI` (count, then x, y, z, colorIndex bytes);
- scene graph: `nTRN` (transform: node attributes such as `_name`; frame dict with `_t` translation
  "x y z" and `_r` packed rotation byte), `nGRP` (group), `nSHP` (shape -> model id);
- `LAYR` (layers), `RGBA` (256 colors), 256 × `MATL`, `IMAP` (palette display order),
  `NOTE` (palette row names), `rOBJ`, `rCAM` (renderer settings).

Details:
- `FILES` The object name used by XML `object="..."` is the `_name` attribute of the `nTRN` node.
- `FILES` Several named objects may point to the same model (official wheels share one model).
- `FILES` Color index 0 means empty. In `RGBA`, the color of index *i* is stored at position *i − 1*.
- `SPEC` Binary layout of `nTRN`, `nGRP`, `nSHP`, `MATL`, `LAYR`, `NOTE`, `IMAP` and of the packed
  rotation byte `_r` (bits 0-1 / 2-3: column of the non-zero entry of rows 0 / 1; bits 4, 5, 6: signs
  of rows 0, 1, 2). Identity is `_r = 4`. In `RGBA`, "color [0-254] are mapped to palette index
  [1-255]".
- `REF` Rotation convention: the rows stored in `_r` act on column vectors, `v' = R · v` (ogt_vox
  swizzles the stored rows into the columns of its row-vector matrices). Transforms compose from
  parent to child: world rotation `R_parent · R_child`, world translation `R_parent · t_child +
  t_parent`.
- `REF` A model's position `_t` is the position of its **pivot**, located at `floor(size / 2)` in model
  coordinates (so the minimum corner is at `_t - floor(size / 2)` for an unrotated model).
  `MV` 2026-10-04 (0.1.0 sample): a 3×3×3 and a 4×4×4 object written with this rule touch exactly,
  sit on the same plate and are flush on their −Z faces; axis bars meet exactly where placed.
- `FILES` Official files rotate objects in the scene graph (for example `_r` = 17 or 33, and `_r = 1`
  on saloon car wheels, which is a *reflection*: determinant −1), including whole car
  bodies: the Castanet body model is 57 × 24 × 13 (length along MagicaVoxel X) with `_r = 17`, while
  the saloon car body is 21 × 44 × 13 unrotated. Both cars look right in game, so `DEDUCED` Teardown
  applies `_r`. Our writer still writes identity rotations only (decision D-003) and bakes rotations
  into the voxels; our reader refuses to convert rotated named objects until 0.8.0.
- `FILES` Root `nTRN` has layer -1 and no frame attributes; named object transforms mostly use layer 0
  (other layers occur, e.g. the saloon car wheels use layer 1); `MATL` ids are 1 to 256; official
  version-150 car files have 8 `LAYR` chunks named "0" to "7".
- `FILES` Shape nodes can be shared: several transforms may point to the same `nSHP` (instancing), and
  a group may list the same child several times (11 official files). The reader yields one instance
  per transform path and visits a group's duplicate children once.
- `FILES` Object names often contain spaces ("window 1"): 1 001 of 17 670 named objects; a few use
  other characters (`,` `:` `'` `\` and non-ASCII). See decision D-018 for the names we accept.
- `FILES` Variants in official game files (3 398 `.vox` files under `data/`, `mods/`, `dlcs/`, read
  2026-10-04):
  - some `RGBA` chunks hold 255 colors (1020 bytes) instead of 256; the reader accepts both.
  - 15 files (Cratertown, Cullington, ...) replace `XYZI` with a Teardown-specific `TDCZ` chunk:
    3 × int32 size followed by a zlib stream that inflates to `size_x × size_y × size_z` bytes (a dense
    grid of palette indices). `UNVERIFIED` order of the axes in that grid, so the reader refuses these
    files explicitly (`TeardownCompressedError`) instead of guessing. We never write `TDCZ`.

## 3. Palette: the index decides the material

- `DOC` The material of a voxel depends only on its **palette index**, not on its color.
  Examples given: index 9 is grass; indices 57–72 are wood.
- `FILES` Full table, from the `NOTE` chunk of the official `data/built-in/palette.vox`
  (row *r* covers indices `(31 − r) × 8 + 1` to `(31 − r) × 8 + 8`), consistent with the doc examples:

| Indices | Material | Slots | Indices | Material | Slots |
|---|---|---|---|---|---|
| 1–8 | glass | 8 | 121–136 | weak metal | 16 |
| 9–24 | grass | 16 | 137–152 | heavy metal | 16 |
| 25–40 | dirt | 16 | 153–168 | plastic | 16 |
| 41–56 | rock | 16 | 169–176 | hard metal | 8 |
| 57–72 | wood | 16 | 177–184 | hard masonry | 8 |
| 73–88 | concrete | 16 | 185–224 | reserved | — |
| 89–104 | brick | 16 | 225–240 | unphysical | 16 |
| 105–120 | plaster | 16 | 241–255 | reserved | — |

- `DOC` Hardness (sledge / blowtorch / guns / explosives):
  soft = glass, grass, dirt, plastic, wood, plaster; medium = concrete, brick, weak metal;
  hard = hard masonry, hard metal (explosives only); unbreakable = heavy metal, rock.
- `FILES` `MATL` key sets in official version-150 files: the most common one (58 % of entries) is
  `_type _weight _rough _spec _spec_p _ior _att _g0 _g1 _gw _flux _ldr` with defaults `_weight 1`,
  `_rough 0.1`, `_spec 0.5`, `_spec_p 0.5`, `_ior 0.3`, `_att 0`, `_g0 -0.5`, `_g1 0.8`, `_gw 0.7`,
  `_flux 0`, `_ldr 0`. Our writer uses this set. Other entries use shorter sets (`_g _ior _rough ...`).
- `FILES` Emissive `_flux` values in official files range from 0 to 4 (2 is the most common).
- `DEDUCED` `MATL` keys (spec lists `_type`, `_weight`, `_rough`, ... without semantics): `_weight` is
  the main slider of each type: metallic for `_metal`, transparency for `_glass` (official windows use
  0.5), emission for `_emit`; `_flux` is the emissive power.
- `UNVERIFIED` Which glass `_weight` makes glass opaque: the doc says only "100 or not" matters but
  not which side is opaque, and official files use 1 on many glass entries. We only write 0.5
  (transparent windows) and offer no "opaque glass" option.
  `MV` 2026-10-04: glass written with `_weight 0.5` renders transparent and `_emit` voxels glow in
  MagicaVoxel's renderer; the palette row names written in `NOTE` are displayed next to the rows.
  `GAME` 2026-10-07 (0.4.0 acceptance car): glass-material voxels with our glass finish
  (`_glass`, `_weight 0.5`) are see-through in game and break when shot; glass voxels with an
  emissive finish (`_emit`, `_weight 0.5`, `_flux 2`) glow and break too.
- `DOC` Rendering type comes from the MagicaVoxel material (`MATL _type`): metal (the normal case;
  diffuse = metal with max roughness, also fine), glass, emissive. Glass transparency: only "100 or not"
  matters. The appearance never changes the physical material.
- `FILES` Official cars: body paint in weak metal (121–136, `_plastic`/`_diffuse` look), windows glass
  (1–8, `_glass`), light voxels emissive (`_emit`), several in the 169–176 range.

## 4. Geometry

- `FILES` **1 voxel = 0.1 m** (for example `voxbox size="2500 1 2500"` spans 250 m). The XML `vox`
  element accepts `scale` (the Leclerc tank uses `scale=".5"`, i.e. 5 cm voxels).
- `DOC` Maximum object size 256 × 256 × 256; 128³ recommended; flat 256 × 256 × 10 is fine.
  Split objects containing a lot of empty space.
- `DOC` Voxels only hold together through **faces**; edge/corner contacts fall apart when damaged.
- `DOC` Do not enclose soft material inside hard material (it gets stuck and breaks physics).
- `DOC` When objects overlap in one `.vox` loaded as a whole, the newest object wins.
  `MV` MagicaVoxel's outline lists the last object written by us at the top, i.e. as the newest.
  `DEDUCED` therefore later objects in our files win overlaps in Teardown. Avoid overlaps until
  confirmed in game.

## 5. Axes, origin, orientation

Calibration results (2026-10-06, protocol C of `docs/TESTING_IN_GAME.md`, screenshots by Nathan).
"Teardown frame" is the body/vehicle frame: X right, Y up, front is −Z.

- `GAME` **MagicaVoxel (x, y, z) -> Teardown (x, z, −y)**, signs included. The engine keeps the
  MagicaVoxel grid as stored (`GetShapeSize` returns the MagicaVoxel sizes, e.g. `5 9 7` for our
  5 × 7 × 9 block) and rotates the shape: its local axes map x -> +x, y -> −z, z -> +y. Marker
  voxels were found at the predicted grid corners (`corners` lines) and world positions (`probe OK`
  on the even and rotated blocks; the odd block's probe points fall on voxel boundaries, so its
  `OK` is not evidence).
- `GAME` **Origin of a `vox` element** (the point its XML `pos` refers to), on a grid of
  Teardown-frame size (sx, sy, sz) voxels, measured from the grid's minimum corner:
  `(floor(sx / 2), 0, sz − floor(sz / 2))` voxels, i.e. the MagicaVoxel pivot `floor(size / 2)` on
  MagicaVoxel x and y, and the bottom on MagicaVoxel z. Odd sizes therefore have **no half-voxel
  offset**: with integer positions every voxel stays on the 0.1 m grid. Measured: 5 × 7 × 9 block,
  shape corner at `pos + (−0.2, 0, +0.4)` (MagicaVoxel corner, = Teardown x min, y min, z max), so
  x spans [−0.2, 0.3] and z [−0.5, 0.4]; 6 × 8 × 10 block: x [−0.3, 0.3], z [−0.5, 0.5].
  This settles the `FILES` hint below (saloon car body `pos` x 0.05).
- `GAME` A `GetShapeLocalTransform` position is the minimum corner of the engine's (MagicaVoxel)
  grid, in body space (consistent with `data/script/wheels.lua`).
- `GAME` A prefab places an object loaded with `object="..."` by its XML `pos` only; the object's
  translation `_t` inside the `.vox` is ignored (our objects sit far from the file origin, the
  readings were the expected small offsets).
- `GAME` The engine keeps our palette indices (marker voxels read back as entries 153–156, the
  concrete base as 73).
- `GAME` XML `rot="x y z"` (degrees) behaves exactly like `QuatEuler(x, y, z)` and turns the shape
  around its origin: `rot="0 90 0"` is a right-handed +90° turn about Y (+X -> −Z), and with
  `rot="90 90 0"` the X turn is applied first, then the Y turn (+X -> −Z, +Y -> +X, +Z -> −Y).
  Not measured: where the Z angle comes in the order (`script_defs.lua` documents Y, Z, X for
  `QuatEuler`, i.e. q = qY · qZ · qX, consistent with the measurement).
- `GAME` Vehicles face **−Z**: driving forward moves the car towards its −Z face. +X is the
  driver's right (green stripe on the +X face seen on the right from the driver's seat).
  `FILES` official wheels `fl`/`bl` at −X, `fr`/`br` at +X, `player`/`seat` at X ≈ −0.35; official
  prefabs put `rot="0 180 0"` on body `vox` elements modelled with the front at +Z.
- `GAME` The `wheel` `pos` is the axle center and the wheel `vox` origin is at the bottom: wheel
  vox `pos` = (0, −radius, 0) gives a visible wheel that touches the ground (measured gap 0 cm on
  all 4 wheels, axle 2–3 cm above its XML position at rest, within `travel="-0.1 0.1"`).
- `GAME` Children of a `vox` (`location`) are positioned relative to the vox origin: the location
  entities and the vehicle's own driver, exhaust and vital positions read exactly the intended
  body-frame positions. Only the translation was measured (our body vox has no `rot`);
  `DEDUCED` from `salooncar.xml` (rear lights at local z −2.1 in a vox with `rot="0 180 0"`) that
  children also follow the vox rotation.
- `GAME` The exhaust smoke came out at the rear right, where the `exhaust` location was (x +0.5,
  z +1.9) with an identity rotation.
- `GAME` A vehicle without a `sound` attribute still has an engine sound; without rig locations
  the driver is shown near the `player` location (our calibration driver sat on the roof, the
  location being above the body; the exact offset was not measured).
- `GAME` 2026-10-07: a vehicle prefab `prefab > group > vehicle > body > (vox with locations,
  wheels)` without any `script` wrapper (Buildup's skeleton) spawns from `spawn.txt`, drives
  forward and backward, steers, its wheels touch the ground and turn; no log error.
- `GAME` 2026-10-07: without driver `rig`, with the `player` location 0.9 m above the cabin floor
  (1.2 m above the ground), the driver's view is at about that height and the driver's body is
  shown hanging below it: its feet stick out under the car.
- `FILES` Every official land vehicle of `mods/assetpack/assets/vehicles/land` has `rig` elements
  (children of `body`): a `rig` tagged `driver` and passenger rigs, each with `location`s tagged
  `seat`, `ik_head`, `ik_hand_l`, `ik_hand_r`, `ik_foot_l`, `ik_foot_r` (and `steeringwheel`
  for the driver), positioned relative to the rig `pos`. In the saloon car the `player`
  location is about 0.1 m above the driver rig's `ik_head`. `DEDUCED`: `player` is the driver's
  view point and the rig gives the seated pose; unverified until a rig is tested in game.
- `FILES` (historical hint, now explained by the origin rule) The saloon car body is 21 voxels wide
  and its vox has `pos` x `0.05` with `rot="0 180 0"`: with the floor origin and the 180° turn the
  0.05 centers the body between its wheels.

## 6. XML (for manifests, reference tools and validators)

- `FILES` Minimal official car (`assetpack/.../salooncar.xml`): `prefab` > `group` > `vehicle` > `body`
  > (`vox object="body"` with `light` / `location` children) + 4 × `wheel` (each containing a `vox`) +
  `rig` elements (driver/passenger IK `location`s, format v2).
- `FILES` (`data/script_defs.lua`) vehicle params: spring, damping, topspeed, acceleration, strength,
  antispin, antiroll, difflock, steerassist, friction (+ smokeintensity, brokenthreshold);
  wheel: drive, steer, travel; joint types: ball, hinge, prismatic, rope.
- `FILES` Location tags on vehicles: `player`, `vital`, `exhaust`.
- `FILES` Observed ranges over 135 official vehicle prefabs: 1 body in 99/143 vehicles; 4 wheels most
  common; topspeed 3–120 (typ. 60–90); spring 0.2–25 (typ. 0.5); damping 0.4–25 (typ. 0.7);
  wheel travel typically `-0.1 0.1`.

## 7. Mods

- `DOC` A mod is a folder: `info.txt`, optional `main.xml`, `main.lua`, `options.lua`, `preview.jpg`
  (Workshop, max 1 MB). Use only Latin alphanumeric characters and spaces in names.
- `DOC` Paths: `MOD/...` inside the mod; `FILES` `BUILT-IN/...` references game assets (allowed,
  used by many mods; nothing is redistributed).
- `FILES` `spawn.txt`: one `path/to/prefab.xml : Category/Name` per line.
  `GAME` A plain-text category works: our objects were spawned from `Buildup/Calibration prop`
  and `Buildup/Calibration car` of a local mod in `Documents\Teardown\mods`.
- `FILES` Local mods folder: `%USERPROFILE%\Documents\Teardown\mods`.
- `FILES` Game log: `%LOCALAPPDATA%\Teardown\log.txt`, lines like
  `... ERROR <id> [NoTag|Loading] File not found ...`.
- `FILES` Lua API definitions: `<install>/data/script_defs.lua` (and `voxscript_defs.lua`). API v2 splits
  client/server; the log warns about deprecated patterns ("won't work in v2").

- `DOC` `info.txt` keys: `name`, `author`, `description`, `tags` (comma-separated, among Map,
  Gameplay, Asset, Vehicle, Tool). `FILES` official mods also use localized keys (`en_name`, ...),
  the tag `Spawn` (`proppack`, `vehiclepack`) and many have `version = 2` (meaning not documented).
  Spawn packs without a `version` line: `proppack`, `vehiclepack`, and `merlin`, whose spawnable
  prefab runs a `#version 2` script.
- `DOC` Static objects become dynamic when spawned from the spawn menu.
- `FILES` Spawn packs: `spawn.txt` lines point to prefab XML files relative to the mod folder; the
  prefab root is `<prefab version="...">` > `<group>`.

## 7b. Lua scripts (for probes and, later, the reference tools)

- `FILES` A script file whose first line is `#version 2` uses API v2: callbacks are
  `client.init()`, `client.tick()`, `server.init()`, ... (official `firehydrant.lua`, `doors.lua`).
  Files without the line use API v1 (`init()`, `tick()`, `draw()`, official `debuginfo` mod).
  The log warns when v1 scripts call API functions before `init` ("won't work in v2").
- `FILES` A `<script file="MOD/...">` element can wrap `vox`, `body` and `vehicle` elements
  (official prefabs); `FindShape(tag)` / `FindVehicle(tag)` without the `global` argument search
  the script's scope (`script_defs.lua`).
- `FILES` (`data/script/wheels.lua`) A shape's local transform is the minimum corner of its voxel
  grid: the official script computes a shape's center as
  `st.pos + rotate(st, (size_x, size_y, size_z) × 0.05)`.
- `FILES` (`data/level/factory/script/paintboat.lua`) `GetShapeMaterialAtIndex` returns the
  material type first (empty string for an empty voxel) and the color as components 0 to 1.
- `FILES` Vectors are plain Lua tables indexed 1 to 3 (`debuginfo` reads `hitPoint[1]`);
  transforms are `{pos = vec, rot = quat}`.
- `FILES` (`data/level/carib/script/turret.lua`) The official turret script converts location
  transforms to body space once, at init. `UNVERIFIED` whether location entities follow their body
  afterwards. `script_defs.lua`: `GetVehicleDriverPos`, `GetVehicleExhaustTransforms` and
  `GetVehicleVitalTransforms` return positions "in local space of the vehicle" (the driver
  position is documented "in vehicle space").
- `FILES` (`script_defs.lua`) Functions used by the calibration probes: `GetShapeSize` (voxels and
  voxel scale), `GetShapeLocalTransform` (in body space), `GetShapeBody`, `GetBodyTransform`,
  `GetShapeBounds` (world AABB), `GetShapeMaterialAtIndex` (0-based grid index; last return value
  is the palette entry), `GetShapeMaterialAtPosition`, `QueryRejectVehicle` + `QueryRaycast`,
  `QuatEuler(x, y, z)` (degrees), `QuatRotateVec`, `TransformToParentPoint`,
  `TransformToLocalPoint`, `DebugWatch` (up to 32 values on screen), `DebugTransform`.

## 8. Open questions (need in-game tests)

- Handling of `nTRN _r` for named objects (§2).
- Whether wheel `vox` should use `collide="false"` (official files are inconsistent).
- Hinge axis convention of `joint rot`.
- XML `rot`: position of the Z angle in the order (X before Y is measured, §5).
- Whether children of a `vox` follow the vox rotation (translation measured, §5).
- Whether location entities follow their body after spawn (`turret.lua` hint, §7b).
- What `teardown_modtest.exe` (in the install folder) does; could it load a mod from the command line?
- Whether the engine reads wheel `name` values (Buildup writes `fl`, `fr`, `bl`, `br` like official
  files, and `ml`/`mr`, `m1l`... for middle axles).
