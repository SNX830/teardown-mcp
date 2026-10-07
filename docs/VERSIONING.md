# Versioning

## Scheme: Semantic Versioning, `MAJOR.MINOR.PATCH`

The project follows [Semantic Versioning 2.0.0](https://semver.org/). Git tags are `vMAJOR.MINOR.PATCH`
(for example `v0.4.0`).

**Why not a zero-padded format like `0.00.00`:** SemVer forbids leading zeros, and Python packaging
(PEP 440) normalizes `0.01.00` to `0.1.0`, so the two would disagree. `0.MINOR.PATCH` gives the same
"pre-release counter" effect without that problem.

### Before 1.0.0 (development phase)

| Part | Meaning before 1.0.0 |
|---|---|
| `0` | Not complete yet; tool names and file formats may still change. |
| `MINOR` | One roadmap milestone (see `docs/ROADMAP.md`): `0.1.0`, `0.2.0`, ... |
| `PATCH` | Fixes and small improvements inside a milestone: `0.4.1`, `0.4.2`, ... |

`0.0.x` is the project setup phase.

### 1.0.0 and after

`1.0.0` is the **first complete release** (criteria in `docs/ROADMAP.md`). From then on, strict SemVer:

- `MAJOR`: breaking change for users (an MCP tool removed or renamed, incompatible arguments,
  incompatible project/manifest format).
- `MINOR`: new backward-compatible features (new tools, new optional arguments).
- `PATCH`: backward-compatible bug fixes.

The **manifest format** carries its own `manifest_version` integer, bumped on every incompatible change,
because other people's AIs will read it.

## Single source of truth

- The version lives **only** in `pyproject.toml` (`[project] version`).
- Code reads it with `importlib.metadata.version("buildup-mcp")` (exposed as `buildup.__version__`).
- `tests/test_version.py` checks that the installed version equals `pyproject.toml` and is valid SemVer.

## Changelog

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Every user-visible
change goes under `## [Unreleased]` during development, in one of: Added, Changed, Deprecated, Removed,
Fixed, Security.

## Commit messages: Conventional Commits

Format: `type(scope): short imperative summary` — for example `feat(voxio): write named objects`.

| Type | Use for |
|---|---|
| `feat` | New functionality |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Tests only |
| `refactor` | Code change with no behaviour change |
| `perf` | Performance improvement |
| `build` / `ci` | Packaging, dependencies, CI |
| `chore` | Maintenance, releases |

Scopes are the package names (`voxcore`, `palette`, `voxio`, `render`, `teardown`, `project`, `server`)
or `docs`, `repo`.

## Branches

- `main` must always pass the quality gate.
- Work happens on short-lived branches named `<type>/<short-topic>` (for example `feat/voxio-writer`),
  merged into `main` when the gate is green.

## Release procedure (only when Nathan asks for a release)

1. The quality gate is green (`uv run python scripts/check.py`).
2. For a milestone release (`MINOR` bump): the milestone's acceptance criteria in `docs/ROADMAP.md` are
   met, **including Nathan's manual/in-game tests** when the milestone requires them.
3. In `CHANGELOG.md`, rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and add a new empty
   `## [Unreleased]` above it.
4. Set `version = "X.Y.Z"` in `pyproject.toml`, then run `uv sync` so the installed version matches.
   On Windows `uv sync` cannot replace `buildup-mcp.exe` while an MCP host runs the server from
   this repository (for example a Claude Code test session started by `.mcp.json`): ask Nathan to
   close those sessions first; never kill the processes.
5. Run the quality gate again.
6. Commit: `chore(release): vX.Y.Z`.
7. Create an annotated tag: `git tag -a vX.Y.Z -m "vX.Y.Z"`.
8. Update `docs/STATUS.md` with the new current version.
