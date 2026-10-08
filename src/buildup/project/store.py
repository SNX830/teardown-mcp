"""Projects on disk: one folder per project, with an undo history.

Layout of ``<workspace>/projects/<name>/``:

- ``project.json``: colors, parts (name, role, origin, wheel data), anchors;
- ``parts.npz``: the part grids (numpy, compressed, no pickled objects); each part of
  ``project.json`` names its array (``arr_0``, ``arr_1``...) or has none while empty;
- ``history/<n>/``: the two files as they were before edit ``n``, and ``action.txt`` naming
  that edit; ``undo`` puts them back.

Files are replaced atomically (written next to the target, then renamed). Every edit loads the
project from disk and saves it only if the edit succeeded, so a failed tool call changes nothing.
"""

import json
import logging
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

import numpy as np

from buildup.palette import Finish, FinishKind, Material
from buildup.project.model import Color, Part, Project, WheelInfo
from buildup.project.names import ProjectError, check_project_name
from buildup.teardown import KINDS
from buildup.teardown.handling import DEFAULT_HANDLING, HANDLING

logger = logging.getLogger(__name__)

FORMAT_VERSION: Final = 1
MAX_HISTORY: Final = 100
PROJECT_FILE: Final = "project.json"
PARTS_FILE: Final = "parts.npz"
HISTORY_DIR: Final = "history"
ACTION_FILE: Final = "action.txt"
REPLACE_ATTEMPTS: Final = 5


class ProjectFileError(ProjectError):
    """A project file is missing, damaged or from an unknown format version."""


def grid_keys(project: Project) -> dict[str, str]:
    """Array name of each non-empty part in ``parts.npz`` (numpy's positional names)."""
    filled = [p.name for p in project.parts.values() if p.grid is not None]
    return {name: f"arr_{k}" for k, name in enumerate(filled)}


def project_to_json(project: Project) -> dict[str, Any]:
    """JSON-ready description of a project, without the grids (see ``grid_keys``)."""
    keys = grid_keys(project)
    return {
        "format": FORMAT_VERSION,
        "name": project.name,
        "kind": project.kind,
        "description": project.description,
        "handling": project.handling,
        "colors": [
            {
                "name": c.name,
                "index": c.index,
                "material": c.material.value,
                "rgb": list(c.rgb),
                "finish": {
                    "kind": c.finish.kind.value,
                    "roughness": c.finish.roughness,
                    "metallic": c.finish.metallic,
                    "emission": c.finish.emission,
                    "power": c.finish.power,
                },
            }
            for c in project.colors.values()
        ],
        "parts": [
            {
                "name": p.name,
                "role": p.role,
                "origin": list(p.origin),
                "grid": keys.get(p.name),
                "wheel": None
                if p.wheel is None
                else {
                    "position": p.wheel.position,
                    "axle": list(p.wheel.axle),
                    "steer": p.wheel.steer,
                    "drive": p.wheel.drive,
                },
            }
            for p in project.parts.values()
        ],
        "anchors": {name: list(point) for name, point in project.anchors.items()},
    }


def _vec3(value: Any) -> tuple[int, int, int]:
    x, y, z = (int(v) for v in value)
    return (x, y, z)


def _point(value: Any) -> tuple[float, float, float]:
    x, y, z = (float(v) for v in value)
    return (x, y, z)


def project_from_json(data: Any, grids: dict[str, np.ndarray]) -> Project:
    """Rebuild a project from ``project_to_json`` output and its grids.

    Raises:
        ProjectFileError: If the data is malformed or of another format version.
    """
    try:
        if data["format"] != FORMAT_VERSION:
            raise ProjectFileError(f"unknown project format {data['format']!r}")
        kind = data["kind"]
        if kind not in KINDS:
            raise ProjectFileError(f"unknown project kind {kind!r}")
        project = Project(str(data["name"]), kind, str(data["description"]))
        preset = data.get("handling", DEFAULT_HANDLING)  # absent before 0.6.0
        if preset not in HANDLING:
            raise ProjectFileError(f"unknown handling preset {preset!r}")
        project.handling = str(preset)
        for c in data["colors"]:
            f = c["finish"]
            finish = Finish(
                FinishKind(f["kind"]),
                roughness=float(f["roughness"]),
                metallic=float(f["metallic"]),
                emission=float(f["emission"]),
                power=float(f["power"]),
            )
            r, g, b = (int(v) for v in c["rgb"])
            color = Color(
                str(c["name"]), int(c["index"]), Material(c["material"]), (r, g, b), finish
            )
            project.colors[color.name] = color
        for p in data["parts"]:
            role = p["role"]
            if role not in ("body", "wheel"):
                raise ProjectFileError(f"unknown part role {role!r}")
            w = p["wheel"]
            wheel = (
                None
                if w is None
                else WheelInfo(
                    str(w["position"]), _point(w["axle"]), bool(w["steer"]), bool(w["drive"])
                )
            )
            name = str(p["name"])
            key = p["grid"]
            grid = None if key is None else grids[str(key)]
            if grid is not None and (grid.dtype != np.uint8 or grid.ndim != 3):
                raise ProjectFileError(f"grid of part {name!r} is not a 3D uint8 array")
            project.parts[name] = Part(name, role, grid, _vec3(p["origin"]), wheel)
        for name, point in data["anchors"].items():
            project.anchors[str(name)] = _point(point)
    except ProjectFileError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ProjectFileError(f"damaged project file: {error!r}") from error
    return project


def _write_temporary(path: Path, write: Any) -> Path:
    """``write(file)`` into a temporary file next to ``path``; return the temporary file."""
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        write(handle)
    return temporary


def _commit(temporary: Path, path: Path) -> None:
    """Rename ``temporary`` over ``path``, retrying while Windows reports the target busy.

    On Windows a file cannot be replaced while another program (an antivirus, an indexer) has it
    open; such locks are short, so a few retries are enough.
    """
    for attempt in range(1, REPLACE_ATTEMPTS + 1):
        try:
            temporary.replace(path)
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS:
                raise
            time.sleep(0.05 * attempt)
        else:
            return


def _replace(path: Path, write: Any) -> None:
    """Write a file atomically: ``write(file)`` into a temporary file, then rename it."""
    _commit(_write_temporary(path, write), path)


class ProjectStore:
    """The projects of a workspace folder.

    Args:
        root: Workspace folder (projects go to ``root / "projects"``).
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.projects_dir = root / "projects"

    def folder(self, name: str) -> Path:
        """Folder of a project (the name is validated, so it cannot leave the workspace).

        Raises:
            ProjectError: If the name is invalid.
        """
        return self.projects_dir / check_project_name(name)

    def names(self) -> list[str]:
        """Names of the existing projects, sorted."""
        if not self.projects_dir.is_dir():
            return []
        return sorted(p.name for p in self.projects_dir.iterdir() if (p / PROJECT_FILE).is_file())

    def create(self, name: str, kind: object, description: str = "") -> Project:
        """Create and save an empty project.

        Raises:
            ProjectError: Invalid name or kind, or a project with this name already exists.
        """
        folder = self.folder(name)
        if kind not in KINDS:
            raise ProjectError(f"kind must be one of {', '.join(KINDS)}, got {kind!r}")
        if (folder / PROJECT_FILE).exists():
            raise ProjectError(f"a project called {name!r} already exists")
        project = Project(name, "vehicle" if kind == "vehicle" else "prop", description)
        folder.mkdir(parents=True, exist_ok=True)
        self._save(project)
        return project

    def load(self, name: str) -> Project:
        """Read a project.

        Raises:
            ProjectError: Invalid name or no such project (the message lists the projects).
            ProjectFileError: If its files are damaged.
        """
        folder = self.folder(name)
        path = folder / PROJECT_FILE
        if not path.is_file():
            known = ", ".join(self.names()) or "none yet, use create_project"
            raise ProjectError(f"unknown project {name!r}; projects: {known}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ProjectFileError(f"cannot read {path}: {error}") from error
        grids: dict[str, np.ndarray] = {}
        parts_path = folder / PARTS_FILE
        if parts_path.is_file():
            try:
                with np.load(parts_path, allow_pickle=False) as archive:
                    grids = {key: archive[key] for key in archive.files}
            except (OSError, ValueError) as error:
                raise ProjectFileError(f"cannot read {parts_path}: {error}") from error
        project = project_from_json(data, grids)
        # The folder decides the name: a copied project folder is a new project, not a second
        # view of the original one.
        project.name = name
        return project

    def _save(self, project: Project) -> None:
        folder = self.folder(project.name)
        arrays = [p.grid for p in project.parts.values() if p.grid is not None]
        text = json.dumps(project_to_json(project), indent=2)
        # Write both files before replacing either, so that a failure while writing (disk full,
        # bad data) leaves the project untouched.
        parts = _write_temporary(
            folder / PARTS_FILE, lambda handle: np.savez_compressed(handle, *arrays)
        )
        data = _write_temporary(folder / PROJECT_FILE, lambda handle: handle.write(text.encode()))
        _commit(parts, folder / PARTS_FILE)
        _commit(data, folder / PROJECT_FILE)

    @contextmanager
    def edit(self, name: str, action: str) -> Iterator[Project]:
        """Load a project for an edit; save it, with an undo step, if the block succeeds.

        Args:
            name: Project name.
            action: Short description of the edit, shown by ``undo``.
        """
        project = self.load(name)
        yield project
        entry = self._snapshot(name, action)
        try:
            self._save(project)
        except BaseException:
            # Put the previous files back (only needed if one was replaced) and always drop the
            # step, so that undo never reports an edit that did not happen.
            try:
                self._restore(name, entry)
            except OSError:
                logger.exception("could not restore project %r after a failed save", name)
            finally:
                shutil.rmtree(entry, ignore_errors=True)
            raise
        self._prune(name)

    def _history_entries(self, name: str) -> list[Path]:
        history = self.folder(name) / HISTORY_DIR
        if not history.is_dir():
            return []
        return sorted((p for p in history.iterdir() if p.name.isdigit()), key=lambda p: int(p.name))

    def _snapshot(self, name: str, action: str) -> Path:
        folder = self.folder(name)
        entries = self._history_entries(name)
        number = int(entries[-1].name) + 1 if entries else 1
        entry = folder / HISTORY_DIR / str(number)
        entry.mkdir(parents=True)
        for file in (PROJECT_FILE, PARTS_FILE):
            if (folder / file).is_file():
                shutil.copy2(folder / file, entry / file)
        (entry / ACTION_FILE).write_text(action, encoding="utf-8")
        return entry

    def _prune(self, name: str) -> None:
        """Keep the newest ``MAX_HISTORY`` steps (after a successful save only)."""
        entries = self._history_entries(name)
        for old in entries[: max(0, len(entries) - MAX_HISTORY)]:
            shutil.rmtree(old)

    def _restore(self, name: str, entry: Path) -> str:
        """Put the files of a history entry back, delete the entry, return its action."""
        folder = self.folder(name)
        for file in (PROJECT_FILE, PARTS_FILE):
            source = entry / file
            if source.is_file():
                _replace(folder / file, lambda handle, s=source: handle.write(s.read_bytes()))
            elif file == PARTS_FILE:
                (folder / file).unlink(missing_ok=True)
        action = (entry / ACTION_FILE).read_text(encoding="utf-8")
        shutil.rmtree(entry)
        return action

    def history(self, name: str) -> list[str]:
        """Edits that ``undo`` can revert, oldest first.

        Raises:
            ProjectError: Invalid name.
        """
        return [
            (entry / ACTION_FILE).read_text(encoding="utf-8")
            for entry in self._history_entries(name)
        ]

    def undo(self, name: str, steps: int = 1) -> list[str]:
        """Revert the last ``steps`` edits (fewer if the history is shorter).

        Returns:
            The reverted edits, most recent first.

        Raises:
            ProjectError: Unknown project, ``steps`` below 1, or nothing to undo.
        """
        self.load(name)  # fail early on an unknown or damaged project
        if steps < 1:
            raise ProjectError(f"steps must be at least 1, got {steps}")
        entries = self._history_entries(name)
        if not entries:
            raise ProjectError(f"nothing to undo in project {name!r}")
        return [self._restore(name, entry) for entry in reversed(entries[-steps:])]
