# Status

Hand-off notes between sessions. Update at the end of every session (see `AGENTS.md` §4).

- **Current version:** 0.6.0 (tag `v0.6.0`)
- **Current milestone:** 0.7.0 — Multi-part models (not started)
- **Last milestone:** 0.6.0 — Modelling quality (released 2026-10-08)
- **Repository:** https://github.com/SNX830/teardown-mcp (public)

## Done

- 2026-09-30 — Phase 1 analysis (example mods, official game files, official docs); findings recorded in
  `docs/TEARDOWN_REFERENCE.md`. Plan validated by Nathan with these answers: client Claude Code;
  "blocky" MVP accepted; MIT; output in the project folder; Nathan runs the manual tests; English in the
  repository; scope voxel-first with manifest + XML skeleton (D-006); all code written by AI agents.
- 2026-09-30 — Repository scaffolding and agent documentation; quality gate verified green in a temporary
  virtual environment (not yet with uv).
- 2026-09-30 — Names chosen (D-013: Buildup / repo `teardown-mcp` / `buildup-mcp` / `buildup`);
  copyright holder SNX830 (D-014).
- 2026-09-30 — Tooling installed on Nathan's machine (uv 0.12.21, GitHub CLI 2.102.0, logged in as
  SNX830). Repository-local git identity: `SNX830 <235518176+SNX830@users.noreply.github.com>` (keeps the
  school e-mail of the global git config private). First commit, tag `v0.0.1`, public GitHub repository.
- 2026-09-30 — CI fixed (actions pinned to commit SHAs; `setup-uv` has no floating major tag) and green
  on Windows/Linux × Python 3.12/3.13. Lesson: check that an action version/tag exists before using it.
- 2026-10-04 — Milestone 0.1.0 implemented: `buildup.palette` (materials, finishes, allocator) and
  `buildup.voxio` (reader, writer, axis conversion, rotations). Quality gate green, 99 % coverage;
  every official `.vox` of the local install is read (3 398 files; 15 `TDCZ` files refused on purpose,
  D-017). Independent review by the `reviewer` subagent: changes required (an unverified "opaque
  glass" option, weak rotation tests, undocumented facts); all findings fixed. Re-review found one
  more bug (object names ending with a newline were accepted); fixed and tested. 173 tests.
  Format facts added to `docs/TEARDOWN_REFERENCE.md` §2-4 with their sources. Sample file generated
  with `uv run python scripts/make_sample_vox.py` -> `workspace/samples/buildup-sample.vox`.
- 2026-10-05 — Milestone 0.2.0, step 1: calibration mod generator
  (`scripts/make_calibration_mod.py`, Lua probe templates in `scripts/calibration/`). Design in
  D-019: the probes measure in game what the engine did (sizes, shape transforms, palette entries
  at grid corners, world probes, wheel/ground gap) instead of judging 5 cm by eye. New facts from
  official files (wheel naming and driver side, wheel vox offsets, Lua API v2) added to
  `docs/TEARDOWN_REFERENCE.md` §5, §7, §7b. `tests/test_calibration_probes.py` runs the probes
  against a mock engine (Lua 5.1 through the new dev dependency `lupa`): `OK` when the engine
  follows our conventions, `MISMATCH` with swapped corners when X is mirrored, `gap +40 cm` when
  wheels are misplaced. Independent review: changes required (missing third outcome of the
  half-voxel rule, a half-voxel hint pointing the wrong way, wrong `FILES` status for vox children,
  markers identified only by palette number, handles searched only once, probe test not kept);
  all fixed: markers recognised by color, location probes and a two-axis `rot` block added.
  Re-review: location probe read in the current body frame (locations may stay in the world);
  fixed (read once after spawn, cross-checked with the vehicle API). Approved after that fix.
- 2026-10-06 — Calibration run by Nathan: all conventions confirmed, half-voxel question settled
  (MagicaVoxel pivot rule). Reference §5 rewritten with the `GAME` status; `xml_origin` added.
  One `DEDUCED` sub-item stays in §5: whether children of a `vox` also follow its `rot` (only the
  translation was measured). Not needed by the MVP (our skeleton writes no `vox` rotation); to
  measure with the joints in 0.7.0.
- 2026-10-06 — Milestone 0.3.0 implemented on branch `feat/voxcore-render`: `buildup.voxcore`
  (shapes as masks, operations, composition, face-connected components) and `buildup.render`
  (true orthographic and 3/4 views, annotated preview sheet, text inspection with ASCII slices).
  Conventions in D-021, Pillow recorded in D-020. Orientation of every view tested voxel by
  voxel. The agent reviewed the sample sheets itself (fixed overlapping labels, unreadable rulers
  on small models, a cut-off axis gizmo). Independent review: changes required, all fixed:
  `box` entirely outside the grid filled almost the whole grid (negative slice bound); `hollow`
  left face-disconnected staircases on curves (now erodes over 26 neighbours, tested on spheres,
  ellipsoids and open slopes); per-part bounding boxes were computed in a slow loop (now one
  vectorised pass); errors unified (`RenderError` is a `VoxcoreError`; JSON-like inputs
  validated); marker labels get leader lines. 319 tests.
  Timing (Nathan's PC, 128^3 grid, sphere of radius 63 hollowed with thickness 1): connectivity
  0.3 s, `describe` 0.35 s, full preview sheet about 2 s; a 128^3 checkerboard (1 048 576
  separate voxels) is analysed in 1.7 s.
- 2026-10-07 — Milestone 0.4.0 implemented on branch `feat/mcp-server`: `buildup.project`
  (projects on disk with undo, named colors, parts that grow with their voxels, wheels, anchors,
  model space limits), `buildup.teardown` (export checks, manifest, XML skeleton, reference
  texts) and `buildup.server` (22 MCP tools, `buildup-mcp` command). Decisions D-022 to D-026.
  MCP SDK 2.3.0 API checked against its documentation (D-023). Verified: the skeleton rebuilt
  from the calibration car reproduces its game-verified XML values; the server runs as a real
  stdio subprocess (stdout clean); a full build-preview-export run through the MCP client gives a
  coherent preview (looked at by the agent) and a `.vox` that reads back identical.
  `scripts/write_mcp_config.py` writes the `.mcp.json` for the acceptance test.
  Independent review: changes required, all fixed: AI-facing texts stated more than the
  reference supports (overlaps "collide", vital "engine area", glass "transparent" in game,
  edge-touching voxels "fall off"); parallel tool calls could break saves on Windows (now one
  re-entrant lock for every file access, both files written before replacing, retries, failed
  saves restored without a fake undo step); a copied project folder edited the original;
  `add_wheels` guidance gave no gap (now half width + 1, like the calibration car); `mirror_part`
  could silently empty a part; non-finite numbers crashed tools; reserved mod names; tool
  annotations. Re-review: approved. 483 tests, coverage 98.7 %.
- 2026-10-07 — Milestone 0.5.0 implemented on branch `feat/coherence-tools`: `validate_mod`,
  `read_game_log`, `lookup_api` (decision D-027). Verified: the validator finds nothing on the
  Petite Rouge mod and the calibration mod; run on every official mod and on Nathan's local
  mods, its false alarms were traced to official usages and fixed (recorded in reference
  §6-7); the log reader parses the real `log.txt` (Petite Rouge's spawn lines, no error for
  it); `lookup_api` reads 781 functions from the local install. 25 MCP tools.
  Independent review: changes required, all fixed: the mod filter of `read_game_log` missed a
  mod's Lua errors (the log keeps only the end of script paths) and then said "no error" (now
  matched through the mod's files, and the empty answer says what cannot be attributed);
  short folder names matched other mods; `validate_mod` crashed on unknown XML encodings,
  folders named `*.xml` and incomplete manifests, and gave wrong findings on files with a
  UTF-8 BOM; it held the project lock while scanning a folder; more official usages were
  still flagged; `lookup_api` hid names present in both definition files. Re-review:
  approved; its two small text remarks (the log tool does not take the `local-` id, a mod
  without spawn.txt is only a note) were fixed before the commit.

- 2026-10-08 — Milestone 0.6.0 implemented on branch `feat/modelling-quality` (decision
  D-028): see-through glass in previews, `draw_profile` (silhouettes extruded with chamfered
  or rounded edges), anchor roles (`driver_seat`/`passenger_seat*` -> rigs, `headlight*`/
  `taillight*` -> lights, manifest roles), seat checks at export, and `start_from_template`
  (sedan, SUV, pickup, van, truck; 27 MCP tools). Read-only surveys of the official land
  vehicles (rigs, lights, body sizes) recorded in reference §5-6. Verified: every template at
  every allowed size exports without warnings in one piece, with no feet inside a seat, and
  passes `validate_mod`; the agent looked at the previews of all five templates
  (recognisable car, SUV, pickup, van and box truck, windows see-through onto the seats).
  Independent review: changes required, all fixed: the truck put the driver's head in the
  cab's back wall at three lengths (the tests now sweep every allowed size); tool and
  changelog texts said "drivable" and "lit headlights" before any game test; the head offset
  differed from the documented median (now documented as rounded to half a voxel); the SUV's
  rear passengers' feet were in the front seats; tabs filled drawing cells; bevels that draw
  nothing and an ignored `origin` are now refused; prop anchors no longer claim seats or lights.
- 2026-10-08 — Protocol G run by Nathan (results in `docs/TESTING_IN_GAME.md` G): driver rig
  and lights verified in game (reference §5-6 `GAME`); marks 2 to 3 for the four requests,
  4 for a Porsche built from a photo. Fixes after it: handling presets from official vehicles
  (`set_handling`, 28 MCP tools), templates raised to the official ground clearance, lighter
  truck, body-colored wheel arches, the AI asked to request a reference picture (D-028).
  Protocol G2 passed: realistic height, normal steering, 'car' 90 and 'sports' 120 km/h.

## Environment notes (Nathan's machine)

- Windows 11, Python 3.13 (Microsoft Store build), uv and gh installed with winget. Terminals opened
  before an installation do not see the new PATH: open a new terminal.
- Teardown install: `C:\Program Files (x86)\Steam\steamapps\common\Teardown`.

## Next steps

1. Milestone 0.7.0 (multi-part models), when Nathan asks.
2. Ideas from protocol G for later milestones: accessories at believable sizes (light bars),
   building from reference pictures (worked best), passenger rigs (not yet tested).
2. Note: uv runs the project locally with Python 3.14 (newest installed); CI tests 3.12, 3.13, 3.14.

## Open questions for Nathan

None blocking.

## Manual tests pending

None. Last result: **0.6.0 protocol G2 passed** (2026-10-08): sedan and race car at a
realistic height, normal steering, about 90 and 120 km/h; shapes weaker when two vehicles are
asked in one request.

Previous result: **0.6.0 protocol G passed with findings** (2026-10-08): driver seated inside,
plausible view, headlights in front, rear lights at the back, glass breaks; marks 2-3
("recognisable"), 4 from a photo; vehicles too low, hard to steer, same speed (addressed,
to verify in G2).

Previous result: **0.5.0 protocol F passed with a finding** (2026-10-07). In a Claude Code
session in `BuildupTest`, `validate_mod` reported the wrong wheel object (`wheel_zz`, listing the
real objects) and nothing once fixed. In game the broken script showed on screen
`[string "...ods/Petite Rouge/script/test.lua"]:4: attempt to call global
'fonction_inexistante' (a nil value)` (the predicted 32-character form), but the error was **not
in `log.txt`**: the log only had the spawns and `[NoTag|LocalMod]` lines naming the loaded
script. Fixed before release: `read_game_log` lists those lines and tells the AI that Lua
runtime errors are on screen only (reference §7, D-027).

Previous result: **0.4.0 MVP acceptance passed** (2026-10-07, protocol E). A fresh Claude
Code session (Sonnet 5.5, high effort) in `Documents\Perso\BuildupTest` built "Petite Rouge" in
about 2 minutes with 47 tool calls and no tool error, exported it and wrote `info.txt` and
`spawn.txt`. In game: listed in the spawn menu, wheels on the ground, turning and steering,
drives forward and backward (reverse slower), glass windows and lights break. `log.txt`: no
error for the mod (only errors of other Workshop mods). Remarks by Nathan:
- the rear cabin pillar "does not reach the roof": the AI put glass quarter windows there; glass
  is see-through in game, which the preview (opaque light blue) does not show;
- the driver's view is low and the driver's feet stick out under the car (no driver `rig`;
  reference §5); the cabin interior is empty (expected).
Both are recorded for 0.6.0 (roadmap). New `GAME` facts in reference §3 and §5.

Older result: **0.3.0 preview review passed** (2026-10-06, protocol D, Nathan: "tout est
OK" on `pickup.png`, `gallery.png` and `pickup.txt`; no remark, including on the "chamfer" label
placed above the wedge in the gallery front view).

Older result: **0.2.0 calibration passed** (2026-10-06, protocol C, screenshots by Nathan).
Every conclusive probe line `OK` (the odd block's probe is not conclusive); engine grid =
MagicaVoxel grid rotated so that MagicaVoxel (x, y, z) -> Teardown (x, z, -y); odd block `pos-xml` `-0.200 0.000 0.400` = MagicaVoxel-pivot rule (no half
voxel); `ROT`/`ROT2` match `QuatEuler`; car: wheels gap 0 cm, axle +2 to +3 cm at rest, locations
exact (entity and vehicle API). Driving: forward towards the white lights, green stripe on the
right, wheels on the ground and steering, exhaust smoke rear right, driver visible (sitting on the
roof, where the `player` location was), engine sound present. Interpreted in
`docs/TEARDOWN_REFERENCE.md` §5. Remove `BuildupCalibration` from the mods folder when done.

Older result: **0.1.0 MagicaVoxel check passed** (2026-10-04, screenshots by Nathan) on
`workspace/samples/buildup-sample.vox`. Only remark: the red axis bar did not touch the green one; that
was a placement mistake in `scripts/make_sample_vox.py` (bar started at x=0 instead of x=-1, a 1-voxel
gap exactly as placed), now fixed. The checklist was:
1. Opens without error in MagicaVoxel 0.99.7.2.
2. Scene outline (TAB) lists 8 objects: ground, cube_odd, cube_even, window, lamp, axis_x_right,
   axis_y_up, axis_front.
3. The red cube (3×3×3) and the wooden cube (4×4×4) touch exactly: no gap, no overlap; both sit on
   the grey plate; their faces on the blue-bar side are in the same plane (flush).
4. The green bar is vertical; the red and blue bars lie flat, perpendicular to each other.
5. Palette: rows are labelled with material names (glass, grass, ... reserved).
6. Render mode: the window color is "Glass" (transparent); the lamp color is "Emit"; the red cube
   color is "Metal".

## Known issues

None.
