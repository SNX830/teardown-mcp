"""What every group of tools shares: the context, error handling and tool annotations."""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from buildup.palette import PaletteError
from buildup.project import Project, ProjectError, ProjectStore
from buildup.teardown import AssemblyError
from buildup.teardown.api import ApiError, ApiFunction, load_api
from buildup.teardown.install import GamePaths
from buildup.voxcore import VoxcoreError
from buildup.voxio import VoxFormatError

#: Errors caused by the arguments or the state of a project: the AI reads the message and can
#: fix the call. Every other exception is a bug.
USER_ERRORS: Final = (
    ProjectError,
    VoxcoreError,
    PaletteError,
    AssemblyError,
    VoxFormatError,
    ApiError,
)

READ_ONLY: Final = ToolAnnotations(read_only_hint=True, open_world_hint=False)
EDIT: Final = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
#: Edits that delete or overwrite (undo can bring a removed part back, not an undone edit).
DESTRUCTIVE: Final = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, open_world_hint=False
)
#: Reads the model and writes preview.png (a regenerated output) in the project folder.
RENDER: Final = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


@contextmanager
def user_errors() -> Iterator[None]:
    """Turn the errors an AI can fix into ``ToolError`` (shown to the AI)."""
    try:
        yield
    except USER_ERRORS as error:
        raise ToolError(str(error)) from error
    except OSError as error:  # a file busy or not writable: worth telling the AI and the user
        raise ToolError(f"file error: {error}; the project was not changed, try again") from error


class Context:
    """What every tool needs: the project store, the mods folder, game paths and the lock.

    Args:
        workspace: Folder for projects (``workspace/projects``) and exported mods
            (``workspace/mods``). Never the game's mods folder (decision D-010).
        game: The user's game install and log (read only); detected when ``None``.
    """

    def __init__(self, workspace: Path, game: GamePaths | None = None) -> None:
        self.store = ProjectStore(workspace)
        self.mods_dir = workspace / "mods"
        self.game = GamePaths.detect() if game is None else game
        self._api: list[ApiFunction] | None = None
        # Tools run in worker threads and hosts call them in parallel; every access to project
        # files holds this lock (re-entrant, so a locked tool may call ``read``).
        self.lock = threading.RLock()

    def edit(self, project: str, action: str, change: Callable[[Project], str]) -> str:
        """Apply ``change`` to a project and save it with an undo step, if it succeeds."""
        with self.lock, user_errors(), self.store.edit(project, action) as loaded:
            return change(loaded)

    def read(self, project: str) -> Project:
        """Load a project (errors become ``ToolError``)."""
        with self.lock, user_errors():
            return self.store.load(project)

    def api(self) -> list[ApiFunction]:
        """The game's Lua API definitions, read once from the install.

        Raises:
            ApiError: If the install or its definition files are not found.
        """
        if self._api is None:
            self._api = load_api(self.game.install)
        return self._api
