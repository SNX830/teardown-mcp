# Status

Hand-off notes between sessions. Update at the end of every session (see `AGENTS.md` §4).

- **Current version:** 0.3.0 (tag `v0.3.0`)
- **Current milestone:** 0.4.0 — MVP: MCP server (not started)
- **Last milestone:** 0.3.0 — Modelling core, preview and inspection (released 2026-10-06)
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

## Environment notes (Nathan's machine)

- Windows 11, Python 3.13 (Microsoft Store build), uv and gh installed with winget. Terminals opened
  before an installation do not see the new PATH: open a new terminal.
- Teardown install: `C:\Program Files (x86)\Steam\steamapps\common\Teardown`.

## Next steps

1. Milestone 0.4.0 (MVP: MCP server).
2. For 0.4.0: decide where grid sizes are limited (`voxcore.new_grid` has no upper bound; `.vox`
   objects are limited to 256 per edge) so that a tool call cannot allocate gigabytes. The future XML skeleton must place `vox` elements with
   `buildup.voxio.xml_origin` (measured rule, no half voxel).
3. Note: uv runs the project locally with Python 3.14 (newest installed); CI tests 3.12, 3.13, 3.14.

## Open questions for Nathan

None blocking.

## Manual tests pending

None. Last result: **0.3.0 preview review passed** (2026-10-06, protocol D, Nathan: "tout est
OK" on `pickup.png`, `gallery.png` and `pickup.txt`; no remark, including on the "chamfer" label
placed above the wedge in the gallery front view).

Previous result: **0.2.0 calibration passed** (2026-10-06, protocol C, screenshots by Nathan).
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
