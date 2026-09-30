# Teardown and .vox reference

Facts the code relies on. **Every fact has a status and a source.** Do not rely on anything that is not
here; add new facts with their source (rule 3 in `AGENTS.md`).

| Status | Meaning |
|---|---|
| `DOC` | Stated in the official modding documentation (https://www.teardowngame.com/modding/) |
| `FILES` | Observed in official game files (Teardown install: `data/`, `mods/vehiclepack`, `mods/assetpack`) |
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
- `FILES` Official files sometimes rotate objects in the scene graph (`_r` = 17 or 33 on wheels).
  `UNVERIFIED` how Teardown applies `_r` to objects referenced by name. Our writer always writes
  identity rotations (decision D-003) and bakes rotations into the voxels.

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

## 5. Axes, origin, orientation

- `DEDUCED` (from `assetpack/.../salooncar.vox` + `.xml`: red emissive rear lights at high MagicaVoxel Y,
  XML places them at the rear): **MagicaVoxel (x, y, z) -> Teardown (x, z, −y)**.
- `DEDUCED` The shape origin of an object is **bottom center** (light heights match `(z + 0.5) × 0.1`).
- `FILES` Vehicles face **−Z** in the vehicle frame (front wheels at negative z), Y is up.
  Official prefabs put `rot="0 180 0"` on the body `vox`.
- `UNVERIFIED` Sign of X and the half-voxel offset for odd sizes. -> calibration milestone 0.2.0.

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
- `FILES` Local mods folder: `%USERPROFILE%\Documents\Teardown\mods`.
- `FILES` Game log: `%LOCALAPPDATA%\Teardown\log.txt`, lines like
  `... ERROR <id> [NoTag|Loading] File not found ...`.
- `FILES` Lua API definitions: `<install>/data/script_defs.lua` (and `voxscript_defs.lua`). API v2 splits
  client/server; the log warns about deprecated patterns ("won't work in v2").

## 8. Open questions (need in-game tests)

- X sign and half-voxel pivot offset (§5).
- Handling of `nTRN _r` for named objects (§2).
- Whether wheel `vox` should use `collide="false"` (official files are inconsistent).
- Hinge axis convention of `joint rot`.
- Whether custom categories in `spawn.txt` display correctly (official files use localization keys).
- What `teardown_modtest.exe` (in the install folder) does; could it load a mod from the command line?
