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
