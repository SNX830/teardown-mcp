"""Where the user's Teardown installation and game log are (read only, never redistributed).

Locations from docs/TEARDOWN_REFERENCE.md §7: the game log is ``Teardown/log.txt`` in the user's
local application data folder (``LOCALAPPDATA``); the API definitions are
``<install>/data/script_defs.lua``. The install folder is looked up in ``$TEARDOWN_DIR``, then in
the Steam libraries listed in Steam's ``libraryfolders.vdf``.
"""

import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

INSTALL_VARIABLE: Final = "TEARDOWN_DIR"
LOG_VARIABLE: Final = "TEARDOWN_LOG"
STEAM_DIRS: Final = (
    Path(r"C:\Program Files (x86)\Steam"),
    Path.home() / ".steam" / "steam",
    Path.home() / ".local" / "share" / "Steam",
)
_VDF_PATH = re.compile(r'"path"\s+"((?:[^"\\]|\\.)*)"')


def steam_libraries(steam_dirs: tuple[Path, ...] = STEAM_DIRS) -> list[Path]:
    """Steam folders and the libraries listed in their ``libraryfolders.vdf``."""
    found: list[Path] = []
    for steam in steam_dirs:
        candidates = [steam]
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            text = vdf.read_text(encoding="utf-8", errors="replace")
            candidates += [Path(m.replace("\\\\", "\\")) for m in _VDF_PATH.findall(text)]
        for candidate in candidates:
            if candidate not in found:
                found.append(candidate)
    return found


def find_install(
    environ: Mapping[str, str] | None = None, steam_dirs: tuple[Path, ...] = STEAM_DIRS
) -> Path | None:
    """The Teardown install folder (the one containing ``data/``), or ``None`` if not found.

    A ``$TEARDOWN_DIR`` without ``data/`` is logged and the Steam libraries are searched.
    """
    env = os.environ if environ is None else environ
    if env.get(INSTALL_VARIABLE):
        candidate = Path(env[INSTALL_VARIABLE])
        if (candidate / "data").is_dir():
            return candidate
        logger.warning(
            "%s=%s has no data folder; looking in the Steam libraries", INSTALL_VARIABLE, candidate
        )
    for library in steam_libraries(steam_dirs):
        candidate = library / "steamapps" / "common" / "Teardown"
        if (candidate / "data").is_dir():
            return candidate
    return None


def default_log_path(environ: Mapping[str, str] | None = None) -> Path | None:
    """``$TEARDOWN_LOG``, else ``$LOCALAPPDATA/Teardown/log.txt``; ``None`` if unknown."""
    env = os.environ if environ is None else environ
    if env.get(LOG_VARIABLE):
        return Path(env[LOG_VARIABLE])
    local = env.get("LOCALAPPDATA")
    return Path(local) / "Teardown" / "log.txt" if local else None


@dataclass(frozen=True)
class GamePaths:
    """Paths of the user's game files that the tools read.

    Attributes:
        install: Teardown install folder, or ``None`` if not found.
        log: Game log file (may not exist yet), or ``None`` if unknown.
        local_mods: The game's local mods folder (``Documents/Teardown/mods``, official files),
            or ``None``.
    """

    install: Path | None
    log: Path | None
    local_mods: Path | None = None

    @classmethod
    def detect(cls, environ: Mapping[str, str] | None = None) -> "GamePaths":
        """Find the paths from the environment and the Steam libraries."""
        mods = Path.home() / "Documents" / "Teardown" / "mods"
        return cls(
            find_install(environ), default_log_path(environ), mods if mods.is_dir() else None
        )
