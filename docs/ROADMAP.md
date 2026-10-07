# Roadmap

Each milestone is one `MINOR` version (see `docs/VERSIONING.md`). A milestone is finished only when its
acceptance criteria are met, including Nathan's manual tests when listed.

Scope reminder: the MCP builds the **voxel models** completely and exports what the user's AI needs to
write the rest of the mod (manifest, anchors, reference, validation). See `AGENTS.md` §1.

## 0.0.x — Project setup

- Repository, tooling, quality gate, CI, agent documentation.
- **Accept:** quality gate green locally and on CI (Windows + Linux).

## 0.1.0 — .vox I/O and Teardown palette

- `voxio`: reader and writer (version 150, several models, named objects, `RGBA`, `MATL`, `NOTE`
  with Teardown material row names so MagicaVoxel shows them).
- `palette`: allocate indices by (material, color, render type); report when a material runs out of slots.
- **Accept:** round-trip tests; the reader parses every official `.vox` of the local install (`game`
  tests); **Nathan opens a generated multi-object file in MagicaVoxel 0.99.7.2** and sees the right
  names, colors and palette row labels.

## 0.2.0 — Calibration in game

- A scripted (no AI) calibration mod: an asymmetric prop with axis markers and a box-shaped test car
  with 4 cylinder wheels; its XML is hand-written from the conventions in `docs/TEARDOWN_REFERENCE.md`.
- **Accept:** Nathan's in-game test confirms axes, origin, half-voxel offset, wheel placement and ground
  contact. Every `DEDUCED` item of §5 becomes `FILES`/verified or is corrected.

## 0.3.0 — Modelling core, preview and inspection

- `voxcore`: box, cylinder, sphere, wedge/chamfer, mirror, fill, hollow, boolean operations, paint.
- `render`: multi-view orthographic preview (front, side, top, 3/4) with scale ruler and annotations.
- Text inspection: dimensions in meters, voxel counts, **ASCII slices**, disconnected-voxel detection,
  materials used.
- **Accept:** unit tests; preview images reviewed.

## 0.4.0 — MVP: MCP server

- MCP server (stdio) for Claude Code: persistent projects, parts, primitives, paint, preview (image),
  inspect, export `.vox` + **manifest** (objects, sizes, pivots, wheel anchors) into `workspace/`.
- Optional **XML prefab skeleton** generated from the manifest (decision D-006).
- A reference tool giving the AI the XML conventions it needs (from `docs/TEARDOWN_REFERENCE.md`).
- **Accept (MVP):** in a fresh Claude Code session, Claude builds a small car with the MCP, writes the XML
  (starting from the skeleton), `spawn.txt` and `info.txt`; Nathan copies the mod into the game: it appears in the
  spawn menu, drives, wheels touch the ground and turn, glass breaks, and `log.txt` has no errors for it.

## 0.5.0 — Coherence tools

- `validate_mod`: checks that XML references existing `.vox` files and object names, positions are
  consistent with the manifest, required tags/locations exist, file names are valid.
- `read_game_log`: extracts errors related to a given mod from `log.txt`.
- `lookup_api`: searches the local `script_defs.lua` for the user's AI (never redistributed).

## 0.6.0 — Modelling quality

- Profile extrusion (side silhouette drawn as ASCII or polyline, extruded and chamfered).
- Parametric templates (sedan, pickup, truck...) the AI customizes.
- Named anchors (headlights, exhaust, seats, hinge points) exported in the manifest.
- Driver seat: a `rig` (seat and IK points) in the skeleton so that the driver sits inside the
  car, and guidance for the `player` view point (0.4.0 acceptance: feet out under the car, view
  low); previews that show glass as see-through, as it is in game.
- **Accept:** a panel of test prompts produces recognisable vehicles (judged by Nathan on previews and
  in game).

## 0.7.0 — Multi-part models

- Separate objects for doors, hood, trunk, turret..., with hinge/axis anchors; joint axis convention
  calibrated in game.

## 0.8.0 — Working with existing models

- Import and edit existing `.vox` files, split large objects, reduce empty space, scale variants,
  props and "brush" objects.

## 0.9.0 — Hardening and map-scale content

- Voxel content for maps (building pieces, terrain pieces); performance for large models.
- Packaging (`uvx`), installation guide, examples, documentation for end users.

## 1.0.0 — First complete release

- A non-modder, using Claude Code and the MCP, can get a working vehicle mod from a description
  (single-body and multi-part vehicles), with coherent XML written by their AI from the manifest.
- Tool names and the manifest format are stable and documented.
- All `UNVERIFIED` items used by the code are resolved.
