# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) as described in [docs/VERSIONING.md](docs/VERSIONING.md).

## [Unreleased]

## [0.6.0] - 2026-10-08

### Added
- MCP tool `start_from_template`: builds a complete vehicle to customize (sedan, SUV, pickup,
  van, box truck), sized after the official vehicles: body with a cabin, glass windows, seats,
  dashboard and steering wheel, glowing lamps, lined wheel arches, wheels and every anchor
  (exports without warnings; seated driver and lights verified in game);
  length and width adjustable by up to 20 %.
- MCP tool `draw_profile`: a side, front or top silhouette (polygon or ASCII drawing)
  extruded across the model, with chamfered or rounded edges.
- Seats and lights in the XML skeleton: the anchors `driver_seat` and `passenger_seat*`
  become seated character rigs (official car layout), `headlight*` and `taillight*` become
  lights shining forward and red rear lights (driver and lights verified in game).
- Export warnings for seats: no driver seat, the character's seat or head inside the body,
  no floor under the feet, a player view point far from the official position.
- The manifest gives every anchor its role and what the skeleton writes for it.
- MCP tool `set_handling`: driving presets (`car`, `sports`, `offroad`, `van`, `truck`,
  `basic`), each the speed, engine, suspension, steering assist and engine sound of an
  official vehicle of that kind. Templates use the preset of their kind.

### Changed
- The skeleton's `vehicle` element now uses the project's handling preset (`car` by default)
  instead of the calibration car's three parameters (with them, Buildup vehicles sat low,
  steered badly and all reached the same speed in game; with `car` and `sports` they steer
  normally and reach about 90 and 120 km/h).
- Templates sit higher (0.2 to 0.4 m under the body, like official vehicles), the truck is
  lighter, and wheel arches are lined in the body color.
- The AI is asked to request a reference picture of the vehicle when possible.
- Previews draw glass (glass material with the glass finish) see-through, as it is in game.
- The reference texts and server instructions describe templates, profiles, seats and lights.

## [0.5.0] - 2026-10-07

### Added
- MCP tool `validate_mod`: checks a mod folder (info.txt, spawn.txt, XML syntax and values,
  `MOD/` files and `.vox` objects that exist, vehicle structure, player location) and compares
  vox, wheel and location positions with the Buildup manifests. Official usages found in the
  game's own mods are accepted.
- MCP tool `read_game_log`: errors and warnings of Teardown's `log.txt`, filtered by mod
  (its spawns, loaded scripts and script warnings, which the log names by the end of the script
  path), with repeated messages grouped. Lua runtime errors are shown on the game screen only,
  never in the log (verified): the tool tells the AI to ask the user for that text.
- MCP tool `lookup_api`: searches the Lua API definitions of the local Teardown install
  (`script_defs.lua`, never copied), with parameters, return values and examples.
- The Teardown install is found through `TEARDOWN_DIR` or the Steam libraries.

### Fixed
- Export warnings no longer say that every vehicle needs vital and exhaust locations (official
  boats and machines have none).

## [0.4.0] - 2026-10-07

### Added
- MCP server `buildup-mcp` (stdio, official MCP SDK) with 22 tools: projects saved on disk with
  undo; named colors (material + color + finish); parts drawn with boxes, cylinders, ellipsoids,
  ramps and edge cuts (add, paint or carve); mirror, hollow and move; wheels with axle data;
  named anchors; preview images and text inspection (description, ASCII layers); export to a
  mod folder; Teardown reference texts for the AI.
- `buildup.project`: persistent modelling projects (`project.json` + `parts.npz`, undo history),
  model space limited to 256 voxels per axis.
- `buildup.teardown`: export checks (missing vehicle locations, overlapping objects, loose
  pieces), the manifest (`manifest_version` 1) and a minimal XML prefab skeleton reproducing the
  conventions verified in game.
- `scripts/write_mcp_config.py`: registers the server for Claude Code sessions in a folder
  (`.mcp.json`). Test protocol E in `docs/TESTING_IN_GAME.md`.
- Runtime dependency: `mcp` (official MCP Python SDK).

## [0.3.0] - 2026-10-06

### Added
- `buildup.voxcore`: voxel grids in the Teardown frame; shapes as boolean masks (box, cylinder,
  sphere, ellipsoid, half-space, edge cut, chamfer, wedge); operations (fill, paint, carve, union,
  subtract, intersect, flip, mirror, hollow, fill enclosed cavities); composition of placed parts;
  face-connected components (detects voxels that would fall off in Teardown).
- `buildup.render`: true orthographic views (front, back, left, right, top, bottom) and 3/4 views,
  assembled into an annotated preview sheet (rulers in meters with Teardown coordinates, side
  labels, labelled markers, 1 m axis gizmo); text inspection (`describe`: size, extent, materials,
  palette entries, connectivity; `ascii_slice`: layers as text, oriented like the views).
- `scripts/make_preview_samples.py`: sample previews for review (protocol D).
- Runtime dependency: Pillow.

## [0.2.0] - 2026-10-06

### Added
- `scripts/make_calibration_mod.py`: generates the 0.2.0 calibration mod (a prop with axis
  markers and a box car with four cylinder wheels, hand-written XML, read-only Lua probes that
  show the engine's measurements on screen). Test protocol C in `docs/TESTING_IN_GAME.md`.
- Development dependency `lupa`: the calibration probes are tested against a mock engine.
- `buildup.voxio.xml_origin`: where a Teardown XML `vox` `pos` sits inside a grid, as measured in
  game (no half-voxel offset for odd sizes).

### Changed
- The MagicaVoxel -> Teardown axis mapping, the `vox` origin rule, XML `rot`, wheel placement and
  ground contact are now verified in game (`docs/TEARDOWN_REFERENCE.md` §5, status `GAME`).

## [0.1.0] - 2026-10-04

### Added
- `buildup.palette`: the Teardown materials and their palette index ranges, rendering finishes
  (matte, metal, glass, emissive) and a palette allocator that picks indices in the right material
  range and refuses to overflow a material.
- `buildup.voxio`: `.vox` reader (versions 150 and 200, scene graph with composed transforms, named
  objects, palette, materials, palette notes) and writer (version 150, layout of official Teardown
  files, named objects, explicit materials, palette row names for MagicaVoxel).
- Conversion between the internal Teardown frame and MagicaVoxel axes, in one module.
- The reader handles the variants found in official game files: 255-color palettes, shape nodes
  shared by several transforms, duplicate group children; it refuses Teardown's compressed `TDCZ`
  chunk and rotated objects with explicit errors instead of guessing.
- Object names may contain single spaces between words, as in official files ("window 1").
- `scripts/make_sample_vox.py`: generates the MagicaVoxel test file of milestone 0.1.0.
- Tests against every `.vox` file of a local Teardown installation (marked `game`).
- Runtime dependency: numpy.
- CI also tests Python 3.14.

### Fixed
- CI: `astral-sh/setup-uv` has no `v10` tag; actions are now pinned to full commit SHAs.

## [0.0.1] - 2026-09-30

### Added
- Project setup: packaging (`pyproject.toml`, uv), MIT license, quality gate (`scripts/check.py`:
  ruff format, ruff lint, mypy strict, pytest with coverage), CI on Windows and Linux.
- Documentation for AI agents and contributors: `AGENTS.md`, `CLAUDE.md`, roadmap, versioning,
  quality checks, decisions, Teardown/.vox reference from the phase 1 analysis, manual test protocols.
