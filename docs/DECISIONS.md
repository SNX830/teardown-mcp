# Decisions

Recorded technical decisions. Do not reverse one silently: add a new entry that supersedes it, with the
reason. Format: context, decision, consequences.

## D-001 — Python >= 3.12
Nathan knows Python; numpy/Pillow make voxel grids and rendering simple; the MCP Python SDK is
first-class; performance is not a concern (< a few million voxels). numpy 2.5 requires Python 3.12.

## D-002 — Official MCP Python SDK, stdio transport
Use the official `mcp` package (v2.x at the time of writing) and its high-level server API, stdio
transport, for Claude Code. **Check the SDK's current API in its documentation when implementing**; do
not write it from memory.

## D-003 — Own .vox reader/writer; write version 150, identity rotations
Existing Python libraries are unmaintained (py-vox-io: 2017) and lack scene graph/`MATL` support.
We write version 150 with explicit `MATL`, like official game files, and bake rotations into voxels
instead of using `nTRN _r` (Teardown's handling of `_r` is unverified).

## D-004 — Internal representation
A modelling project is the single source of truth: parts = `uint8` grids indexed `[x, y, z]` in the
Teardown frame, integer voxel positions, anchors. `.vox`, manifests and previews are compiled outputs.

## D-005 — Software renderer (numpy + Pillow)
Deterministic, no GPU, works headless on Windows and CI. Rejected: moderngl/pyrender (headless GPU
issues), MagicaVoxel (no command line), Blender (too heavy).

## D-006 — Scope: voxel-first; the user's AI writes XML/Lua, helped by a manifest and a skeleton
Direction set by Nathan (2026-09-30), details left to the agents. The MCP builds the voxel models
completely and exports a **manifest** with anchors (the contract read by the user's AI), plus reference
and validation tools. XML/Lua are written by the user's AI.
Amendment (2026-09-30): the MCP also offers an optional **minimal XML prefab skeleton** generated from
the manifest (vehicle > body > body vox, wheels with their vox, `player`/`vital`/`exhaust` locations).
Reason: positions of the body and wheels are exactly the error-prone, mechanical part; generating them
deterministically removes that class of mistakes, while the AI stays free to tune parameters and add
lights, joints and scripts. Part of the MVP (0.4.0); `validate_mod` (0.5.0) checks the final result.

## D-007 — MIT license
Maximum adoption by modders and tool authors.

## D-008 — English in the repository, French in chat with Nathan

## D-009 — Semantic Versioning, 0.MINOR.PATCH until 1.0.0
See `docs/VERSIONING.md`. Zero-padded formats are incompatible with SemVer and PEP 440.

## D-010 — Output inside the project folder
Exports go to `workspace/` (git-ignored). Nathan copies the mod into `Documents\Teardown\mods` to test.
The MCP never writes into the game's folders.

## D-011 — Tooling: uv, ruff, mypy --strict, pytest + coverage
One gate script (`scripts/check.py`) used locally and in CI. Strict settings because no human reviews
the code.

## D-012 — No redistribution of game or third-party files
Game files are read at runtime from the user's install; community mods and MagicaVoxel stay local and
git-ignored.

## D-013 — Names: Buildup / `teardown-mcp` / `buildup-mcp` / `buildup`
Chosen by Nathan (2026-09-30): the tool is called **Buildup** (the opposite of "tear down"); the GitHub
repository is **`teardown-mcp`** so people searching for a Teardown MCP find it.
`buildup` is already taken on PyPI (an abandoned 2017 blog generator), so the Python distribution is
**`buildup-mcp`** (free on 2026-09-30) and the import package is **`buildup`**.

## D-014 — Copyright holder: SNX830
LICENSE says "Copyright (c) 2026 SNX830". An AI cannot hold copyright (human authorship is required in
the US and France), so Claude is not named there; its contribution is credited in the README and by the
`Co-Authored-By` trailer on commits.

## D-015 — Runtime dependency: numpy (>= 2.2)
Added in 0.1.0 for voxel grids (`uint8` arrays indexed `[x, y, z]`, D-004) and fast `.vox` encoding
and decoding. Mature, BSD-licensed, ships type hints.

## D-016 — Palette defaults
Unused palette slots are written as mid-grey (128, 128, 128). The default finish is transparent glass
for the glass material and matte for every other material, so that "glass" behaves as an AI user
expects without extra arguments.

## D-017 — Unsupported format variants are refused explicitly, never guessed
When a file uses something whose meaning is not verified (Teardown's `TDCZ` voxel chunk, rotated
named objects), the reader raises a specific error (`TeardownCompressedError`,
`UnsupportedRotationError`) instead of producing a possibly wrong model. Support is added once the
meaning is verified (rule 3 of AGENTS.md).

## D-018 — Object names
Names we create or import: words of letters, digits, `_`, `.`, `-` separated by single spaces, 1 to
64 characters (`OBJECT_NAME_PATTERN`). Spaces are allowed because official files use them a lot
("window 1"). Other characters (`:`, `,`, quotes, backslash, non-ASCII) are refused with
`InvalidObjectNameError`: they are rare and risky in XML attributes and file listings.

## D-019 — In-game calibration by measurement (Lua probes), not by eye
Context: milestone 0.2.0 must confirm axes, origin, half-voxel offset and wheel placement. Half a
voxel is 5 cm, too small to judge reliably by eye. Decision: the calibration prefabs carry
read-only Lua probes (API v2, `client.tick`) that display what the engine computed (grid sizes,
shape transforms, palette entries at grid corners, world-space probes, wheel/ground gaps), and
Nathan only takes screenshots plus a few simple visual checks (driving direction, right side,
ground contact). The XML of the calibration mod is written by hand from
`docs/TEARDOWN_REFERENCE.md`, not by a generator, so the test checks the conventions themselves.
Markers are recognised by color, not by palette entry number (whether the engine keeps our
indices was unverified; measured 2026-10-06: it keeps them). Consequences: `lupa` (Lua 5.1 in
Python, MIT) becomes a **dev** dependency so that `tests/test_calibration_probes.py` runs the probes against a mock engine in the
quality gate; this proves the scripts run and discriminate the hypotheses, not how the real engine
behaves. Tests import development scripts through pytest's `pythonpath = ["scripts"]`.

## D-020 — Runtime dependency: Pillow (>= 11.0)
Added in 0.3.0 for the preview renderer chosen in D-005 (image buffers, polygon drawing for the
3/4 views, text labels, PNG output). Mature, HPND license (permissive), ships type hints and a
bundled default font (`ImageFont.load_default(size=...)`), so no system font is needed.
Tests compare the pure numpy view arrays exactly; annotated images (text) are only checked for
size and key pixels, because font rendering may differ slightly between platforms.

## D-021 — Preview conventions: true views, Teardown coordinates, text inspection in `render`
Orthographic views are what a camera outside the model sees, never mirrored: in the front view
(camera at −Z) the model's right side (+X) is on the image left; the left view puts the front on
the image left; top and bottom views put the front (−Z) at the top of the image. Every panel says
which side of the model each image edge shows, and rulers are labelled with Teardown-frame
coordinates in meters, so an AI can read positions directly. ASCII slices use the same orientation
as the matching view and one symbol table per model (the same letter means the same palette index
on every layer). Text inspection (`describe`, `ascii_slice`) lives in `buildup.render` next to the
image views: both are "views" of a model, and `render` may use `palette` for material names.
Shapes in `voxcore` are boolean masks combined with numpy operators; grid functions never modify
their inputs (safe for the undo history planned in 0.4.0).

## D-022 — Model space limits (where grid sizes are bounded)
Context: `voxcore.new_grid` has no upper bound, and every tool call could otherwise ask for a huge
grid. Decision: the limit lives in the project layer, where tool arguments enter: every voxel of
a project has model-frame coordinates from −128 to 127 on each axis (`WORLD_MIN`, `WORLD_MAX`).
That is 25.6 m per axis, the `.vox` limit of one object (256), so any part fits in one object and
the whole model fits in a 256³ grid (16 MB) for previews. Shapes are clipped to that space;
mirrors, moves, wheels and anchors that would leave it are refused. Shape masks are computed only
over the shape's bounding box, never over the whole space; a shape as large as the whole space
still needs about 0.8 GB of temporary memory (float64 coordinates in `voxcore.shapes`, measured
by the 0.4.0 review), acceptable on a desktop PC. Shape centers and sizes are limited to
±4096 voxels and must be finite numbers. A project holds at most 32 parts and 32 anchors. The core layers (`voxcore`, `render`) stay unbounded: they are called with grids that
already respect these limits.

## D-023 — Runtime dependency: the official MCP SDK `mcp` (>= 2.3)
Implements D-002 in 0.4.0. Version 2.3.0 (2026-10) checked against its documentation
(py.sdk.modelcontextprotocol.io): `MCPServer`, `@mcp.tool()` with `Annotated[..., Field(...)]`
argument descriptions, `ToolError` for errors the AI can fix, `Image` for PNG results, in-memory
`Client(server)` for tests and `StdioServerParameters` for a real subprocess test. It brings
pydantic, anyio, starlette, httpx2, uvicorn, pyjwt, cryptography, opentelemetry-api and (on
Windows) pywin32 as transitive dependencies, under permissive licenses compatible with MIT (MIT,
BSD, Apache-2.0, PSF). Pinned below 3 (`mcp>=2.3,<3`): the SDK announces removals for 3.0.
Tests use the anyio pytest plugin shipped with anyio (no new dev dependency).

## D-024 — Lint exception: many arguments on MCP tool functions
The parameters of an MCP tool function are the JSON fields the AI fills in. Grouping them into
objects only to satisfy ruff's PLR0913/PLR0917 (more than 5 arguments) would make the tool
schemas harder for the AI to use. Those two rules are therefore disabled for
`src/buildup/server/app.py` only (`pyproject.toml`, per-file ignores). Core functions keep the
rule (for example `Project.add_wheels` takes a `WheelLayout`).

## D-025 — Workspace, project files and export layout
- **Workspace**: `--workspace PATH`, else `$BUILDUP_WORKSPACE`, else `./workspace` (resolved to an
  absolute path when the server starts). Projects go to `workspace/projects/<name>/`, mods to
  `workspace/mods/<Mod Name>/` (D-010: never the game's folder).
- **Project files**: `project.json` (readable JSON: colors, parts, wheel data, anchors, format
  version) and `parts.npz` (compressed numpy arrays, read with `allow_pickle=False`; arrays are
  positional, named by `project.json`, so part names never clash with numpy arguments). Every
  edit loads the project, applies the change and saves only on success, after copying the
  previous files to `history/<n>/` (at most 100 steps): `undo` restores them. One lock serialises
  edits (tools run in worker threads).
- **Names**: projects `[a-z][a-z0-9_]{0,39}` (also folder and `.vox` file names; Windows device
  names refused), parts/colors/anchors `[a-z][a-z0-9_]{0,31}` (a subset of D-018), mod names
  Latin letters, digits and single spaces (official recommendation, reference §7).
- **Export** (`export_model`): `mods/<Mod Name>/vox/<project>.vox` (compiled, always rewritten),
  `projects/<name>/export/manifest.json` and `skeleton.xml` (always rewritten), and
  `mods/<Mod Name>/prefab/<project>.xml` copied from the skeleton only if missing by default: the
  user's AI owns that file. If the skeleton changes while the prefab is kept, the export warns.
  `info.txt` and `spawn.txt` are written by the user's AI (D-006).

## D-026 — Modelling and skeleton conventions
- **Model frame**: the Teardown frame in voxels; the vehicle `body` element sits at the frame
  origin (no `pos`), so every model-frame position is directly a body-frame position. Buildup
  recommends (does not enforce) ground at Y = 0 and the center line at X = 0; `add_wheels` puts
  wheel bottoms at Y = 0 by default.
- **Parts** are sets of voxels: the grid follows the voxels (drawing grows it, carving crops it),
  so the AI never manages grid sizes. Drawing modes: `add` (fill, replacing), `paint` (recolor
  existing voxels only), `carve`. Coordinates: boxes use start (inclusive) / end (exclusive)
  cells; centers, axles and anchors are continuous coordinates, like the preview rulers (D-021).
- **Colors** are named and each name owns one palette index in its material's range, so
  redefining a color recolors its voxels; its material cannot change.
- **Wheels**: even diameters only (axles on whole voxels on Y and Z); names `fl`, `fr`, `bl`,
  `br` as in official files, and `m`/`m1`/`m2` for middle axles (whether the engine reads wheel
  names is unknown, reference §8).
- **Skeleton**: only what the calibration verified in game (D-019, reference §5-7): vox `pos` =
  part origin + `xml_origin(size)`; wheel `pos` = axle and wheel vox `pos` = its pos point minus
  the axle; `player`/`vital`/`exhaust` anchors become `location` children of the first body
  object, relative to its pos point; vehicle parameters of the calibration car; no rotations, no
  `script` wrapper (official prefabs have none), no XML comments. A test rebuilds the calibration
  car as an assembly and checks that the skeleton reproduces its verified XML values.

## D-027 — Coherence tools: read only, rules from official files, findings not fixes
Milestone 0.5.0 adds `validate_mod`, `read_game_log` and `lookup_api` (`buildup.teardown`
`validate`, `gamelog`, `api`, `install`; tools in `buildup.server.coherence`).
- **Read only.** The tools read mod folders, the game log and the install; they never write or
  fix anything, so they may read outside the workspace (a mod already copied into the game's
  mods folder, the Steam install). Findings say what to change; the AI edits the files.
- **Rules from official files.** The validator was run on every official mod of the install
  and on Nathan's local mods; official usages it first flagged are now accepted or reported as
  notes (comment lines, localized `info.txt` keys, tags separated by spaces or in lower case,
  no tags, spawn names without category, mods with only `main.lua`, short `rot`/`pos` vectors,
  `rot="0 0 0"`, `LEVEL/` and bare paths, boats without wheels, vehicles without
  `vital`/`exhaust`, `nodrive` vehicles without `player`, vehicles built from `instance`s).
  These usages are recorded in the reference (§6-7). What remains on official mods is real:
  `MOD/` files, objects and `spawn.txt` prefabs missing from some level mods (probably unused),
  one XML syntax error, and malformed `rot` values (`- 180`, `-90.0 90.0 -`). A mod without
  `spawn.txt`, `main.xml` or `main.lua` is only a note: official mods also add content through
  `gamemodes.txt` or data files.
  Levels: `error` = will not work as written (missing file or object, XML syntax, no
  `info.txt` name), `warning` = may not work or differs from official usage (including a UTF-8
  byte order mark in `info.txt`/`spawn.txt`, which no official file has), `info` (shown as
  NOTE) = not checked, or unusual but seen in official files. Unreadable files (unknown XML
  encoding, a folder named `*.xml`) are findings, never crashes; `MOD/` paths that resolve
  outside the mod folder are errors.
- **Manifest comparison.** Positions are compared with the manifests of the workspace's
  projects (matched by `vox_file`; only complete manifests of the current `manifest_version`
  are used), only for `vox` elements directly inside a `body` or `wheel` and without a non-zero
  `rot`; `location`s inside a vox are compared relative to the manifest's vox position (they
  follow the geometry, D-026), `location`s directly in a `body` with the anchor itself. If the
  mod's `.vox` objects differ in size from the manifest (an older copy of the mod), positions
  are not compared and one warning says so. `buildup.teardown.validate` reads `.vox` files
  through `buildup.voxio` (a lower layer, allowed by AGENTS.md §5).
- **Game files.** The install is `$TEARDOWN_DIR`, else the first Steam library (from
  `libraryfolders.vdf`) containing `steamapps/common/Teardown`; the log is `$TEARDOWN_LOG`, else
  `%LOCALAPPDATA%\Teardown\log.txt`. `create_server` accepts explicit `GamePaths`, so tests use
  invented files and never the user's game files (rule 2); tests marked `game` read the real
  ones without copying them.
- **Log filtering** by mod matches the folder name as a path segment (`/Red Pickup/`,
  `(mod path: .../Red Pickup)`), the local id (`local-red-pickup`), and Lua chunk names
  `[string "...<path end>"]` that end one of the mod's files (looked up in `workspace/mods` and
  in the game's local mods folder): the log keeps only the last 32 characters of script paths,
  so the folder name alone would miss the mod's Lua errors. A chunk name that covers the whole
  relative path but only the end of the folder name is attributed too: another local mod with
  the same script path and the same folder ending could be mixed up (rare, accepted). The tool
  takes the folder name, not the `local-` id. "Other Mod" therefore matches
  neither "another mod" nor "Other Mod 2". Spawn messages of the mod are always shown. When
  nothing is found the tool says that unattributable messages exist and how to see them all.
- **Lua runtime errors** are shown on the game screen and not written to `log.txt` (protocol F,
  2026-10-07). `read_game_log` therefore always reminds the AI to ask the user for the on-screen
  text, and lists the `[NoTag|LocalMod]` lines (the mod's scripts as loaded) and spawns with the
  mod filter, so the AI can tell that a script ran. The chunk-name matching still attributes
  the engine's script warnings, which are logged.
- **Locks.** `validate_mod` holds the project lock only while reading the manifests, never while
  scanning a mod folder; `path` must be absolute.
- **Linux.** Steam under `~/.steam/steam` and `~/.local/share/Steam` is searched; the log of a
  Proton install is not located automatically: set `TEARDOWN_LOG`.
