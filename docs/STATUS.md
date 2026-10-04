# Status

Hand-off notes between sessions. Update at the end of every session (see `AGENTS.md` §4).

- **Current version:** 0.1.0 (tag `v0.1.0`)
- **Current milestone:** 0.2.0 — Calibration in game (not started)
- **Last milestone:** 0.1.0 — .vox I/O and Teardown palette (released 2026-10-04)
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

## Environment notes (Nathan's machine)

- Windows 11, Python 3.13 (Microsoft Store build), uv and gh installed with winget. Terminals opened
  before an installation do not see the new PATH: open a new terminal.
- Teardown install: `C:\Program Files (x86)\Steam\steamapps\common\Teardown`.

## Next steps

1. Milestone 0.2.0: scripted calibration mod (asymmetric prop + box car with cylinder wheels).
2. Note: uv runs the project locally with Python 3.14 (newest installed); CI tests 3.12, 3.13, 3.14.

## Open questions for Nathan

None blocking.

## Manual tests pending

None. Last result: **0.1.0 MagicaVoxel check passed** (2026-10-04, screenshots by Nathan) on
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
