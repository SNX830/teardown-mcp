"""Names used in projects, and the errors of the project layer."""

import re
from typing import Final


class ProjectError(ValueError):
    """A project operation cannot be done (unknown name, bad argument, full palette...)."""


#: Parts, colors and anchors: lower-case letters, digits and ``_``, starting with a letter. A
#: subset of the ``.vox`` object names allowed by decision D-018, safe in XML attributes.
NAME_PATTERN: Final = re.compile(r"[a-z][a-z0-9_]{0,31}")

#: Projects: same characters, up to 40; also used as folder and ``.vox`` file names.
PROJECT_NAME_PATTERN: Final = re.compile(r"[a-z][a-z0-9_]{0,39}")

#: Mod folder and display names: Latin letters, digits and single spaces, as the official
#: documentation recommends (docs/TEARDOWN_REFERENCE.md §7).
MOD_NAME_PATTERN: Final = re.compile(r"(?=.{1,40}\Z)[A-Za-z0-9]+(?: [A-Za-z0-9]+)*")

#: Names Windows refuses for files and folders.
_RESERVED: Final = frozenset(
    {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(10)} | {f"lpt{i}" for i in range(10)}
)


def check_name(value: object, what: str) -> str:
    """Validate a part, color or anchor name.

    Raises:
        ProjectError: If it does not follow ``NAME_PATTERN``.
    """
    if not isinstance(value, str) or not NAME_PATTERN.fullmatch(value):
        raise ProjectError(
            f"invalid {what} name {value!r}: use 1-32 lower-case letters, digits or '_', "
            "starting with a letter (for example 'body' or 'wheel_fl')"
        )
    return value


def check_project_name(value: object) -> str:
    """Validate a project name (also a folder and file name).

    Raises:
        ProjectError: If it does not follow ``PROJECT_NAME_PATTERN`` or is reserved by Windows.
    """
    if (
        not isinstance(value, str)
        or not PROJECT_NAME_PATTERN.fullmatch(value)
        or value in _RESERVED
    ):
        raise ProjectError(
            f"invalid project name {value!r}: use 1-40 lower-case letters, digits or '_', "
            "starting with a letter (for example 'red_pickup')"
        )
    return value


def check_mod_name(value: object) -> str:
    """Validate a mod name (folder name and display name).

    Raises:
        ProjectError: If it does not follow ``MOD_NAME_PATTERN`` or is reserved by Windows.
    """
    if (
        not isinstance(value, str)
        or not MOD_NAME_PATTERN.fullmatch(value)
        or value.lower() in _RESERVED
    ):
        raise ProjectError(
            f"invalid mod name {value!r}: use 1-40 Latin letters or digits, words separated by "
            "single spaces (for example 'Red Pickup'), not a name reserved by Windows"
        )
    return value


def default_mod_name(project: str) -> str:
    """Mod name derived from a project name: ``red_pickup`` -> ``Red Pickup``."""
    return " ".join(word.capitalize() for word in project.split("_") if word)
