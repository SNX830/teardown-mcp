"""Run the project's quality gate (see docs/QUALITY_CHECKS.md).

Usage:
    uv run python scripts/check.py          # run every check
    uv run python scripts/check.py --fix    # apply automatic fixes first, then run every check

Every step runs even if a previous one failed; the exit code is non-zero if any step failed.
"""

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


@dataclass(frozen=True)
class Step:
    """One command of the quality gate."""

    name: str
    command: list[str]


CHECKS = [
    Step("format", [PY, "-m", "ruff", "format", "--check"]),
    Step("lint", [PY, "-m", "ruff", "check"]),
    Step("types", [PY, "-m", "mypy"]),
    Step("tests", [PY, "-m", "pytest", "--cov", "--cov-report=term-missing"]),
]

FIXES = [
    Step("auto-format", [PY, "-m", "ruff", "format"]),
    Step("auto-fix lint", [PY, "-m", "ruff", "check", "--fix"]),
]


def run(step: Step) -> tuple[bool, float]:
    """Run one step from the repository root and return (success, duration in seconds)."""
    print(f"\n=== {step.name}: {' '.join(step.command[1:])}", flush=True)
    start = time.perf_counter()
    result = subprocess.run(step.command, cwd=ROOT, check=False)
    return result.returncode == 0, time.perf_counter() - start


def main() -> int:
    """Run the gate and print a summary. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fix", action="store_true", help="apply automatic fixes before checking")
    args = parser.parse_args()

    if args.fix:
        for step in FIXES:
            run(step)

    results = [(step.name, *run(step)) for step in CHECKS]

    print("\n=== Summary")
    for name, ok, duration in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<8} ({duration:.1f}s)")
    failed = [name for name, ok, _ in results if not ok]
    if failed:
        print(f"\nQuality gate FAILED: {', '.join(failed)}. See docs/QUALITY_CHECKS.md.")
        return 1
    print("\nQuality gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
