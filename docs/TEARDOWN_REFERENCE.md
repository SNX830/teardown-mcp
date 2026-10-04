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
