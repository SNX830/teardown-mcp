"""Shared fixtures."""

import os
from pathlib import Path

import pytest

_DEFAULT_TEARDOWN_DIRS = (
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\Teardown"),
    Path.home() / ".steam" / "steam" / "steamapps" / "common" / "Teardown",
)


def _find_teardown_dir() -> Path | None:
    env = os.environ.get("TEARDOWN_DIR")
    candidates = (Path(env),) if env else _DEFAULT_TEARDOWN_DIRS
    for candidate in candidates:
        if (candidate / "data").is_dir():
            return candidate
    return None


@pytest.fixture(scope="session")
def teardown_dir() -> Path:
    """Local Teardown installation (set TEARDOWN_DIR to override). Skips the test if missing.

    Tests using it must be marked ``@pytest.mark.game``. Game files are only read, never copied.
    """
    found = _find_teardown_dir()
    if found is None:
        pytest.skip("Teardown installation not found (set TEARDOWN_DIR)")
    return found
