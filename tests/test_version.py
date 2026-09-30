"""The installed version must match pyproject.toml and follow SemVer (docs/VERSIONING.md)."""

import re
import tomllib
from pathlib import Path

import buildup

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"

# Official SemVer 2.0.0 regular expression (semver.org), without build metadata.
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?$"
)


def _pyproject_version() -> str:
    with PYPROJECT.open("rb") as f:
        data = tomllib.load(f)
    version = data["project"]["version"]
    assert isinstance(version, str)
    return version


def test_pyproject_version_is_semver() -> None:
    assert SEMVER.match(_pyproject_version())


def test_installed_version_matches_pyproject() -> None:
    assert buildup.__version__ == _pyproject_version(), (
        "Installed version differs from pyproject.toml: run `uv sync`."
    )
