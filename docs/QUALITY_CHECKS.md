# Quality checks (the quality gate)

No human reviews the code of this project line by line. The quality gate below is therefore the
**minimum** proof that a change is correct. It must be run and be green:

- at the **start** of every coding session (to know the starting state),
- **before declaring any task done**,
- at the **end** of every session,
- in CI on every push (`.github/workflows/ci.yml` runs the same script).

## One command

```bash
uv run python scripts/check.py
```

Use `uv run python scripts/check.py --fix` to first apply the automatic fixes (formatting and safe lint
fixes), then run the full gate. Always re-read the diff after `--fix`.

The script runs every step even if an earlier one fails, prints a summary, and exits non-zero if anything
failed. A task is not done while the summary shows a failure.

## The steps

| # | Step | Command it runs | Catches |
|---|---|---|---|
| 1 | Formatting | `ruff format --check` | Inconsistent formatting |
| 2 | Lint | `ruff check` | Syntax errors, undefined names, unused imports/variables, likely bugs (bugbear), bad patterns, `print` in `src/`, missing docstrings, import order |
| 3 | Types | `mypy` (strict, configured in `pyproject.toml`) | Wrong types, missing annotations, `None` misuse, wrong return types, unreachable code |
| 4 | Tests + coverage | `pytest --cov` | Behaviour regressions; coverage of `src/` below the threshold |

Configuration for all tools is in `pyproject.toml`. Changing that configuration to make the gate pass is
a **decision** and must be recorded in `docs/DECISIONS.md` with a reason.

## How to fix each kind of failure

**Formatting (step 1).** Run `uv run ruff format`. Never hand-format against the formatter.

**Lint (step 2).**
- Fix the code, not the rule. Read the rule's documentation: `uv run ruff rule <CODE>`.
- A `# noqa: <CODE>` is allowed only on a single line, with the exact code and a reason:
  `x = eval(s)  # noqa: S307 - input is a constant from our own table`. Never a bare `# noqa`.
- `T201` (print found) in `src/`: use `logging`. In the MCP server, stdout is the protocol channel.

**Types (step 3).**
- Add or correct annotations; prefer precise types (`npt.NDArray[np.uint8]`, `TypedDict`,
  dataclasses) over `Any`.
- `# type: ignore[<code>]` only with the exact error code and a reason comment, and only when the fault is
  in a third-party library's typing. Bare `# type: ignore` is rejected by the configuration.
- `cast()` is a claim you must be able to justify; add a comment if it is not obvious.

**Tests (step 4).**
- A failing test means the code or the test is wrong: find out which before changing anything.
  Never delete, skip or loosen a test just to go green.
- Warnings are errors (`filterwarnings = ["error"]`). Fix the cause; if a third-party warning must be
  ignored, add a *specific* filter in `pyproject.toml` with a comment.
- Coverage below the threshold: add tests for the uncovered behaviour. Excluding code from coverage needs
  a reason (`# pragma: no cover - <reason>`).
- Tests marked `game` need a local Teardown install and skip otherwise. They do not count as passing on
  CI; say so explicitly when reporting.

## What the gate does NOT prove

Report these honestly instead of implying they were checked:

- That a `.vox` file opens in MagicaVoxel -> manual check by Nathan (`docs/TESTING_IN_GAME.md`).
- That a model or mod behaves correctly in Teardown -> manual in-game test by Nathan.
- That a preview "looks right" -> a human (or at least a careful look at the rendered image) is needed.

## Definition of done (for any task)

1. Quality gate green.
2. New behaviour has tests that would fail without the change.
3. Public functions and MCP tools documented (units, ranges, examples for tools).
4. No new fact about Teardown or `.vox` without an entry in `docs/TEARDOWN_REFERENCE.md`.
5. `docs/STATUS.md` and `CHANGELOG.md` updated.
6. Manual tests needed from Nathan are listed, with the exact protocol.
