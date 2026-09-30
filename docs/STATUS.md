# Status

Hand-off notes between sessions. Update at the end of every session (see `AGENTS.md` §4).

- **Current version:** 0.0.1 (tag `v0.0.1`)
- **Current milestone:** 0.0.x — Project setup (done)
- **Next milestone:** 0.1.0 — .vox I/O and Teardown palette
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

## Environment notes (Nathan's machine)

- Windows 11, Python 3.13 (Microsoft Store build), uv and gh installed with winget. Terminals opened
  before an installation do not see the new PATH: open a new terminal.
- Teardown install: `C:\Program Files (x86)\Steam\steamapps\common\Teardown`.

- 2026-09-30 — CI fixed (actions pinned to commit SHAs; `setup-uv` has no floating major tag) and green
  on Windows/Linux × Python 3.12/3.13. Lesson: check that an action version/tag exists before using it.

## Next steps

1. Start milestone 0.1.0 (`voxio` + `palette`).

## Open questions for Nathan

None blocking.

## Manual tests pending

None yet.

## Known issues

None.
