"""Searching the Lua API definitions of the user's Teardown installation.

The game ships ``data/script_defs.lua`` and ``data/voxscript_defs.lua``: LuaLS-style annotation
files where each function is a ``function Name(args) ... end`` line preceded by ``---`` comment
lines (description, an example in a ```` ```lua ```` block, ``---@param`` and ``---@return``
lines). These files are read at run time from the user's install and never copied into this
repository (AGENTS.md rule 2).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

DEFINITION_FILES: Final = ("script_defs.lua", "voxscript_defs.lua")
_FUNCTION = re.compile(r"^function\s+(?P<name>[A-Za-z_][\w.:]*)\s*\((?P<args>[^)]*)\)")
_PARAM = re.compile(r"^@param\s+(?P<name>\S+)\s+(?P<type>\S+)\s*(?P<text>.*)$")
_RETURN = re.compile(r"^@return\s+(?P<type>\S+)\s*(?P<name>\S*)\s*(?P<text>.*)$")


class ApiError(ValueError):
    """The API definitions cannot be found or read."""


@dataclass(frozen=True)
class ApiFunction:
    """One documented function.

    Attributes:
        name: Function name (``GetShapeSize``, ``client.init``...).
        arguments: Argument names as written in the definition.
        description: Text before the example, lines joined.
        example: Lua example code, or ``""``.
        params: ``(name, type, description)`` of each parameter.
        returns: ``(type, name, description)`` of each return value.
        source: File name and line of the definition.
    """

    name: str
    arguments: tuple[str, ...]
    description: str
    example: str
    params: tuple[tuple[str, str, str], ...] = field(default=())
    returns: tuple[tuple[str, str, str], ...] = field(default=())
    source: str = ""

    def signature(self) -> str:
        """``Name(a, b) -> type name, type name``."""
        text = f"{self.name}({', '.join(self.arguments)})"
        if self.returns:
            text += " -> " + ", ".join(f"{t} {n}".strip() for t, n, _ in self.returns)
        return text

    def summary(self) -> str:
        """Signature and the first sentence of the description."""
        first = self.description.split(". ")[0].strip()
        return f"{self.signature()}" + (f": {first}" if first else "")

    def details(self) -> str:
        """Everything known about the function, as text."""
        lines = [self.signature(), f"(from {self.source})"]
        if self.description:
            lines += ["", self.description]
        if self.params:
            lines += ["", "Parameters:"]
            lines += [f"  {n} ({t}): {d}".rstrip(": ") for n, t, d in self.params]
        if self.returns:
            lines += ["", "Returns:"]
            lines += [f"  {n or '-'} ({t}): {d}".rstrip(": ") for t, n, d in self.returns]
        if self.example:
            lines += ["", "Example:", self.example]
        return "\n".join(lines)


def parse_definitions(text: str, source: str) -> list[ApiFunction]:
    """Read the documented functions of one definition file."""
    functions: list[ApiFunction] = []
    comments: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.startswith("---"):
            comments.append(line[3:].removeprefix(" ") if not line.startswith("---@") else line[3:])
            continue
        match = _FUNCTION.match(line)
        if match:
            functions.append(_function(match, comments, f"{source}:{number}"))
        comments = []
    return functions


def _function(match: re.Match[str], comments: list[str], source: str) -> ApiFunction:
    description: list[str] = []
    example: list[str] = []
    params: list[tuple[str, str, str]] = []
    returns: list[tuple[str, str, str]] = []
    in_code = False
    for comment in comments:
        stripped = comment.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            example.append(comment)
        elif m := _PARAM.match(stripped):
            params.append((m["name"], m["type"], m["text"].strip()))
        elif m := _RETURN.match(stripped):
            returns.append((m["type"], m["name"], m["text"].strip()))
        elif stripped.startswith("@") or stripped.rstrip(":") == "Example":
            continue
        elif stripped:
            description.append(stripped)
    arguments = tuple(a.strip() for a in match["args"].split(",") if a.strip())
    return ApiFunction(
        name=match["name"],
        arguments=arguments,
        description=" ".join(description),
        example="\n".join(example).strip("\n"),
        params=tuple(params),
        returns=tuple(returns),
        source=source,
    )


def load_api(install: Path | None) -> list[ApiFunction]:
    """Every documented function of the install's definition files.

    Raises:
        ApiError: If no install is known or no definition file is found.
    """
    if install is None:
        raise ApiError(
            "Teardown installation not found: set the TEARDOWN_DIR environment variable to the "
            "game folder (the one containing data/), then restart the MCP server"
        )
    functions: list[ApiFunction] = []
    for name in DEFINITION_FILES:
        path = install / "data" / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            functions += parse_definitions(text, name)
    if not functions:
        raise ApiError(f"no API definitions found in {install / 'data'}")
    return functions


def search(
    functions: list[ApiFunction], query: str, *, full_text: bool = False
) -> list[ApiFunction]:
    """Functions whose name contains every word of ``query`` (case-insensitive).

    With ``full_text``, descriptions and parameter texts are searched too. An exact name match
    comes first.
    """
    words = [w.lower() for w in query.split()]
    if not words:
        return []

    def haystack(f: ApiFunction) -> str:
        if not full_text:
            return f.name.lower()
        parts = [f.name, f.description, *(" ".join(p) for p in f.params)]
        parts += [" ".join(r) for r in f.returns]
        return " ".join(parts).lower()

    found = [f for f in functions if all(w in haystack(f) for w in words)]
    exact = query.strip().lower()
    return sorted(found, key=lambda f: (f.name.lower() != exact, f.name.lower()))
