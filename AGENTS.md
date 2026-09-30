# AGENTS.md — context for AI coding agents

This file is the entry point for any AI agent working on this repository (Claude Code reads it through
`CLAUDE.md`). Read it fully at the start of every session. It is short on purpose; details live in `docs/`.

## 1. What this project is

**Buildup** (GitHub repository `teardown-mcp`, Python distribution `buildup-mcp`, import package
`buildup`; see `docs/DECISIONS.md` D-013) is an open-source (MIT) **MCP server** that lets an AI
assistant build **complete, Teardown-ready voxel models** (`.vox` files).

- **The MCP owns the voxel side, completely:** modelling with high-level tools, Teardown material palette,
  multi-object `.vox` files with named objects, previews the AI can look at, geometric validation.
- **The user's own AI writes the rest of the mod** (XML prefabs, `spawn.txt`, `info.txt`, Lua scripts).
  To make that possible and coherent, the MCP exports a **manifest** for every `.vox` (object names,
  sizes, pivots, named *anchor points* such as wheel centers or hinge points, expressed in Teardown
  coordinates and meters), can generate a **minimal, known-good XML prefab skeleton** from it (body,
  wheels, required locations) that the AI then customizes, and provides **reference and validation
  tools** (conventions, palette, local API lookup, XML <-> `.vox` coherence checks, game-log reader).
  See decision D-006.
- Target: someone with no modding knowledge describes a vehicle (later: props, map pieces) and gets a
  working mod. Vehicles first.

## 2. Who is involved

- **All code is written by AI agents** (Claude Code). Nathan (project owner) **supervises and tests in
  the game**; he is not a programmer and cannot review code. Consequences for you:
  - Your work must be **self-verifying**: automated checks and meaningful tests are the only code review
    that reliably happens. Never weaken them (see `docs/QUALITY_CHECKS.md`).
  - When you need a game test, give Nathan a **short, concrete, step-by-step protocol** and tell him
    exactly what to report back (see `docs/TESTING_IN_GAME.md`).
  - Explain decisions and risks honestly; do not present guesses as facts.
- **Language:** everything in the repository (code, comments, docs, commits) is in **English**.
  Talk to Nathan in **French** in the chat.

## 3. Hard rules (never break these)

1. **Never commit, copy or paraphrase third-party content.** `mods-examples/` (community mods) and
   `MagicaVoxel-*/` (closed-source software) are kept locally for analysis only and are git-ignored.
   Never copy their files, models, XML or Lua into the repository, tests or fixtures.
2. **Never redistribute Teardown game files** (`script_defs.lua`, built-in `.vox`, prefabs...).
   Tools may *read* them at runtime from the user's own installation; tests that need them are marked
   `game` and skip when the install is not found.
3. **Never invent format details.** Every Teardown/`.vox` fact must come from
   `docs/TEARDOWN_REFERENCE.md`, where each fact carries a verification status. If you need a fact that
   is not there, verify it (official docs, official game files) and add it with its source. If it can
   only be confirmed in game, mark it `UNVERIFIED` and ask Nathan for a test.
4. **Never skip or weaken the quality gate.** No disabling rules, no blanket `# type: ignore` / `# noqa`,
   no deleting or skipping tests to make the gate pass, no lowering coverage thresholds without a
   recorded decision.
5. **Never write to stdout in the MCP server process.** The stdio transport uses stdout for the protocol;
   a stray `print` corrupts it. Use `logging` (stderr). Ruff rule `T20` enforces "no print" in `src/`.
6. **Generated output goes inside the project folder** (`workspace/`, git-ignored), never directly into
   the user's Teardown mods folder (decision D-010).
7. **Do not bump the version, tag, commit or push unless Nathan asks** (or the release procedure in
   `docs/VERSIONING.md` is explicitly requested).
8. **New runtime dependencies require a recorded decision** in `docs/DECISIONS.md`.

## 4. Session workflow

**Start of session**
1. Read `docs/STATUS.md` (where we are, what is next, open issues).
2. Read the milestone in `docs/ROADMAP.md` you are working on, and the relevant parts of
   `docs/TEARDOWN_REFERENCE.md` and `docs/DECISIONS.md`.
3. Run the quality gate once (`uv run python scripts/check.py`) to know the starting state.

**During the session**
- Work in small, testable steps. Write tests together with the code, not after.
- Prefer pure, typed functions in the core layers; keep MCP tool functions thin.

**End of session (mandatory)**
1. Run the full quality gate; it must be green (`docs/QUALITY_CHECKS.md`).
2. Update `docs/STATUS.md` (what was done, what is next, known issues, tests Nathan must do).
3. Add user-visible changes to the `[Unreleased]` section of `CHANGELOG.md`.
4. Summarize for Nathan in French: what changed, what was verified and how, what he should test.

## 5. Architecture (planned)

```
src/buildup/
  voxcore/     voxel grids (numpy uint8, 0 = empty, 1..255 = palette index), primitives, operations
  palette/     Teardown material-aware palette allocator (material + color -> index in the right range)
  voxio/       .vox reader/writer (version 150, scene graph, named objects, MATL, NOTE)
  render/      software renderer (numpy + Pillow): multi-view orthographic previews with annotations
  teardown/    manifest export, anchors, conventions, XML/mod validators, game-log reader, API lookup
  project/     persistent modelling projects on disk (JSON + .npy), undo history
  server/      MCP server: thin tool wrappers over the layers above
```

Layering rule: `server` -> `project` -> (`teardown`, `render`, `voxio`) -> (`voxcore`, `palette`).
Lower layers never import higher ones; nothing below `server` imports the MCP SDK.

**Single source of truth:** a modelling project (parts, grids, positions, anchors) is the source;
`.vox` files, manifests and previews are compiled outputs, never edited in place.

## 6. Conventions

- Python >= 3.12, full type hints, `mypy --strict` clean.
- **Coordinates:** internal geometry uses the **Teardown frame** (X right, Y up, vehicles face **-Z**),
  in **integer voxels** (1 voxel = 0.1 m). Conversion to MagicaVoxel axes happens only in `voxio`;
  conversion to meters only at the manifest/XML boundary. Name units in identifiers when ambiguous
  (`size_vox`, `pos_m`).
- Grids are `numpy.ndarray[uint8]` indexed `[x, y, z]`.
- Public functions and every MCP tool have Google-style docstrings. **MCP tool docstrings are what the
  AI user sees**: write them for an AI that cannot see the model (units, ranges, examples).
- Errors: raise specific exceptions in core layers; MCP tools turn them into clear, actionable messages.
- Tests: `pytest`, in `tests/` mirroring `src/` layout. Tiny hand-made fixtures only (rule 1).
  Markers: `game` (needs local Teardown install), `slow`.

## 7. Key documents

| File | Purpose |
|---|---|
| `docs/STATUS.md` | Current state and hand-off notes between sessions |
| `docs/ROADMAP.md` | Milestones, version numbers, acceptance criteria |
| `docs/VERSIONING.md` | Version scheme, commit convention, release procedure |
| `docs/QUALITY_CHECKS.md` | The quality gate and how to fix each kind of failure |
| `docs/TEARDOWN_REFERENCE.md` | Verified Teardown / `.vox` facts, with sources and status |
| `docs/DECISIONS.md` | Recorded technical decisions (do not re-litigate without a new entry) |
| `docs/TESTING_IN_GAME.md` | Protocols for Nathan's manual tests (MagicaVoxel and in game) |
