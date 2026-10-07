"""Shared fixtures."""

from pathlib import Path

import pytest

from buildup.teardown.install import find_install


@pytest.fixture(scope="session")
def teardown_dir() -> Path:
    """Local Teardown installation (set TEARDOWN_DIR to override). Skips the test if missing.

    Tests using it must be marked ``@pytest.mark.game``. Game files are only read, never copied.
    """
    found = find_install()
    if found is None:
        pytest.skip("Teardown installation not found (set TEARDOWN_DIR)")
    return found
