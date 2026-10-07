"""Reading Teardown's game log (``log.txt``) for the messages that concern a mod.

Format observed in the log of the user's game (docs/TEARDOWN_REFERENCE.md §7): each entry starts
with a line ``<counter> <hh:mm:ss.micro> <LEVEL> <hex id> [<tags>] <message>``; following lines
without that prefix continue the message. Levels seen: INFO, WARNING, ERROR. A local mod appears
in spawn lines as ``local-<folder name in lower case, spaces as dashes>``; Lua messages name their
script by the end of its path only (``[string "...TABS/scripts/x.lua"]``).
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_ENTRY = re.compile(
    r"^(?P<counter>\d+) (?P<time>\d\d:\d\d:\d\d\.\d+) (?P<level>[A-Z]+) (?P<thread>[0-9A-Fa-f]+)"
    r"(?: \[(?P<tags>[^\]]*)\])? ?(?P<message>.*)$"
)
LEVELS: Final = ("ERROR", "WARNING", "INFO")
#: Lua messages name their script ``[string "...<last characters of the path>"]``.
_CHUNK = re.compile(r'\[string "\.\.\.([^"]+)"\]')
#: A Lua chunk name shorter than the script's relative path must keep at least this many
#: characters to be attributed (the log keeps 32, observed).
MIN_TAIL: Final = 24
#: Messages kept whatever the level filter, when they name the mod: they show it was used.
SPAWN_PREFIX: Final = "Spawning:"
#: Tag of the lines that list a local mod's script files as the game loads them (observed).
LOCAL_MOD_TAG: Final = "LocalMod"


@dataclass(frozen=True)
class LogEntry:
    """One log message.

    Attributes:
        line: Line number of its first line (1-based).
        time: Time since the game started, as written (``00:01:23.456789``).
        level: ``ERROR``, ``WARNING``, ``INFO`` or another level name.
        tags: The bracketed tags, for example ``NoTag|Loading``.
        message: The message, continuation lines joined with newlines.
    """

    line: int
    time: str
    level: str
    tags: str
    message: str


def parse_log(text: str) -> list[LogEntry]:
    """Split a log into entries. Lines before the first entry are ignored."""
    entries: list[LogEntry] = []
    head: tuple[int, re.Match[str]] | None = None
    continuation: list[str] = []

    def flush() -> None:
        if head is not None:
            number, match = head
            message = "\n".join([match["message"], *continuation]).rstrip()
            tags = match["tags"] or ""
            entries.append(LogEntry(number, match["time"], match["level"], tags, message))

    for number, raw in enumerate(text.splitlines(), start=1):
        match = _ENTRY.match(raw)
        if match:
            flush()
            head, continuation = (number, match), []
        elif head is not None:
            continuation.append(raw.rstrip())
    flush()
    return entries


def local_mod_id(folder_name: str) -> str:
    """Identifier a local mod gets in the log: ``Petite Rouge`` -> ``local-petite-rouge``.

    Observed for a name with single spaces; each space becomes a dash (names with other
    characters are not verified).
    """
    return "local-" + folder_name.lower().replace(" ", "-")


@dataclass(frozen=True)
class ModMatcher:
    """Recognises the log messages of one mod.

    A message is the mod's when it names the mod folder as a path segment
    (``.../mods/Red Pickup/vox/a.vox``, ``(mod path: .../Red Pickup)``), its local id
    (``local-red-pickup:prefab/...``), or when a Lua chunk name ``[string "...<path end>"]``,
    which keeps only the end of the script path, is the end of one of the mod's files.

    Attributes:
        folder: Mod folder name.
        files: Paths of the mod's files relative to its folder (``/`` separators), to recognise
            truncated Lua chunk names; empty if the folder is not available.
    """

    folder: str
    files: tuple[str, ...] = ()

    def matches(self, message: str) -> bool:
        """Whether ``message`` concerns this mod."""
        name = re.escape(self.folder)
        # The folder as a path segment: after a separator, before a separator, a quote, a
        # closing parenthesis or the end of a line.
        segment = r"[/\\]" + name + r"(?=[/\\\")]|$)"
        if re.search(segment, message, re.IGNORECASE | re.MULTILINE):
            return True
        if re.search(
            rf"(?<![\w-]){re.escape(local_mod_id(self.folder))}(?![\w-])", message, re.IGNORECASE
        ):
            return True
        return any(self._is_mod_script(tail) for tail in _CHUNK.findall(message))

    def _is_mod_script(self, tail: str) -> bool:
        tail = tail.replace("\\", "/").lower()
        folder = self.folder.lower()
        for relative in self.files:
            rel = relative.lower()
            full = f"{folder}/{rel}"
            # The tail is the end of "<folder>/<file>": it covers the whole relative path (what
            # comes before is then the end of the folder name), or at least MIN_TAIL characters
            # of a long one; or it goes further up, past the folder.
            if full.endswith(tail) and (len(tail) > len(rel) or len(tail) >= MIN_TAIL):
                return True
            if tail.endswith("/" + full):
                return True
        return False


def select(
    entries: Iterable[LogEntry], levels: Sequence[str], mod: ModMatcher | None = None
) -> list[LogEntry]:
    """Entries of the given levels; with ``mod``, only those that concern the mod.

    Spawn messages of the mod and the lines listing its loaded scripts are kept whatever
    ``levels`` says (they show it was used).
    """
    wanted = {level.upper() for level in levels}
    chosen = []
    for entry in entries:
        if mod is not None and not mod.matches(entry.message):
            continue
        used = entry.message.startswith(SPAWN_PREFIX) or LOCAL_MOD_TAG in entry.tags.split("|")
        if entry.level in wanted or (mod is not None and used):
            chosen.append(entry)
    return chosen


def summarize(entries: Sequence[LogEntry]) -> list[tuple[LogEntry, int]]:
    """Group identical (level, message) entries: first occurrence and count, in log order."""
    groups: dict[tuple[str, str], list[LogEntry]] = {}
    for entry in entries:
        groups.setdefault((entry.level, entry.message), []).append(entry)
    return [(found[0], len(found)) for found in groups.values()]


def read_log(path: Path) -> list[LogEntry]:
    """Parse a log file (undecodable bytes are replaced)."""
    return parse_log(path.read_text(encoding="utf-8", errors="replace"))
