"""Coherence tools: check a mod folder, read the game log, look up the game's Lua API."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Final, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from buildup.server.common import READ_ONLY, Context, user_errors
from buildup.teardown import validate as checks
from buildup.teardown.api import search
from buildup.teardown.gamelog import ModMatcher, local_mod_id, read_log, select, summarize
from buildup.teardown.validate import Finding, manifests_in

MAX_FINDINGS: Final = 80
#: Verified in game (docs/TEARDOWN_REFERENCE.md §7): Lua runtime errors are shown on screen only.
LUA_NOTE: Final = (
    "Note: Lua runtime errors are not written to log.txt; the game shows them as text in the "
    'bottom left corner of the screen ([string "...<script path end>"]:4: attempt to call ...). '
    "Ask the user for that text."
)
MAX_MESSAGE: Final = 600

LogLevel = Literal["error", "warning", "info"]


def _mod_folder(ctx: Context, mod_name: str | None, path: str | None) -> Path:
    if (mod_name is None) == (path is None):
        raise ToolError("give either mod_name (a mod in workspace/mods) or path, not both")
    if path is not None:
        given = Path(path).expanduser()
        if not path.strip() or not given.is_absolute():
            raise ToolError(f"path must be an absolute folder path, got {path!r}")
        return given.resolve()
    assert mod_name is not None  # one of the two is set
    if not mod_name or any(c in mod_name for c in "/\\:") or mod_name in (".", ".."):
        raise ToolError(f"mod_name must be a folder name of workspace/mods, got {mod_name!r}")
    return ctx.mods_dir / mod_name


def mod_files(ctx: Context, mod: str) -> tuple[str, ...]:
    """Relative paths of the files of mod ``mod``, to recognise its Lua messages.

    Looked up in the workspace export and in the game's local mods folder
    (docs/TEARDOWN_REFERENCE.md §7), read only; empty if neither has the folder.
    """
    if not mod or any(c in mod for c in "/\\:") or mod in (".", ".."):
        return ()
    found: set[str] = set()
    for root in (ctx.mods_dir, ctx.game.local_mods):
        if root is None:
            continue
        folder = root / mod
        if folder.is_dir():
            found |= {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    return tuple(sorted(found))


def findings_text(folder: Path, findings: list[Finding]) -> str:
    """Report of ``validate_mod``."""
    counts = {level: sum(f.level == level for f in findings) for level in ("error", "warning")}
    infos = len(findings) - counts["error"] - counts["warning"]
    head = (
        f"Checked {folder}: {counts['error']} error(s), {counts['warning']} warning(s), "
        f"{infos} note(s)."
    )
    if not findings:
        return head + "\nNo problem found."
    lines = [head]
    for finding in findings[:MAX_FINDINGS]:
        where = finding.file or "(mod folder)"
        label = {"error": "ERROR", "warning": "WARNING", "info": "NOTE"}[finding.level]
        lines.append(f"- {label} {where}: {finding.message}")
    if len(findings) > MAX_FINDINGS:
        lines.append(f"... and {len(findings) - MAX_FINDINGS} more")
    if counts["error"]:
        lines.append("Fix the errors before testing in game: the mod may not load or misbehave.")
    return "\n".join(lines)


def coherence_tools(mcp: MCPServer, ctx: Context) -> None:
    """Register validate_mod, read_game_log and lookup_api."""
    _validate_tool(mcp, ctx)
    _log_tool(mcp, ctx)
    _api_tool(mcp, ctx)


def _validate_tool(mcp: MCPServer, ctx: Context) -> None:

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    def validate_mod(
        mod_name: Annotated[
            str | None,
            Field(description="Mod folder name in workspace/mods, for example 'Red Pickup'."),
        ] = None,
        path: Annotated[
            str | None,
            Field(description="Or the absolute path of any mod folder (read only)."),
        ] = None,
    ) -> str:
        """Check a mod folder before testing it in game, and report what is wrong.

        Checks info.txt (name, author, description, documented tags), spawn.txt lines
        ('prefab/x.xml : Category/Name', files that exist), every XML file (syntax, pos/rot
        values, MOD/ file references that exist, vox objects that exist in their .vox file,
        vehicles with a body, wheels with a vox, the player location), and compares vox, wheel
        and location positions with the Buildup manifest of each exported model. Run it after
        writing or editing the mod's files.

        Levels: ERROR = will not work as written (fix it), WARNING = may not work or differs
        from official mods, NOTE = not checked or unusual but seen in official mods. Positions
        are compared only for vox elements directly inside a body or wheel, without rot; the
        mod's .vox must be the latest export of the project.
        """
        folder = _mod_folder(ctx, mod_name, path)
        with ctx.lock:  # only the workspace's manifests need the lock, not the mod folder
            projects = ctx.store.projects_dir
            manifests = manifests_in(projects.iterdir() if projects.is_dir() else ())
        with user_errors():
            findings = checks.validate_mod(folder, manifests)
        return findings_text(folder, findings)


def _log_tool(mcp: MCPServer, ctx: Context) -> None:
    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    def read_game_log(
        mod: Annotated[
            str | None,
            Field(
                min_length=1,
                description="Only messages about this mod, given by its folder name (for "
                "example 'Red Pickup', not 'local-red-pickup'); its spawn messages are included.",
            ),
        ] = None,
        levels: Annotated[
            list[LogLevel] | None,
            Field(min_length=1, description="Message levels to show; default error and warning."),
        ] = None,
        max_entries: Annotated[int, Field(ge=1, le=200, description="Most messages shown.")] = 40,
    ) -> str:
        """Read Teardown's log (log.txt) after the user has played: errors, warnings, spawns.

        The log holds the latest game run only. Identical messages are grouped with a count.
        With mod, the mod's spawns and loaded scripts are listed too. Lua runtime errors
        (for example "attempt to call global ... (a nil value)") are NOT in the log: the game
        shows them on screen only (verified), so ask the user to copy or photograph the text
        shown on screen after playing. Typical use after a test: read_game_log(mod='Red Pickup').
        """
        log = ctx.game.log
        if log is None or not log.is_file():
            raise ToolError(
                f"no game log found ({log or 'LOCALAPPDATA is not set'}); start Teardown once, "
                "or set TEARDOWN_LOG to the log file"
            )
        levels = levels or ["error", "warning"]
        with user_errors():
            entries = read_log(log)
        matcher = None if mod is None else ModMatcher(mod, mod_files(ctx, mod))
        chosen = summarize(select(entries, [lvl.upper() for lvl in levels], matcher))
        written = datetime.fromtimestamp(log.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        head = (
            f"Log {log} (last written {written}): {len(entries)} messages, "
            f"{len(chosen)} distinct shown for levels {', '.join(levels)}"
            + (f" concerning {mod!r} (log id {local_mod_id(mod)!r})" if mod else "")
            + "."
        )
        if not chosen:
            if matcher is None:
                return head + "\nNothing found.\n" + LUA_NOTE
            missing = (
                ""
                if matcher.files
                else " The mod folder was not found, so its Lua messages (which show only the "
                "end of the script path) could not be recognised."
            )
            return (
                head + "\nNo message concerns this mod." + missing + " Messages that name "
                "neither the mod folder nor one of its script paths cannot be attributed: run "
                "read_game_log without mod to see every error.\n" + LUA_NOTE
            )
        lines = [head, LUA_NOTE]
        for entry, count in chosen[:max_entries]:
            text = entry.message
            if len(text) > MAX_MESSAGE:
                text = text[:MAX_MESSAGE] + " [...]"
            repeat = f" (x{count})" if count > 1 else ""
            lines.append(f"- line {entry.line}, {entry.time} {entry.level}{repeat}: {text}")
        if len(chosen) > max_entries:
            lines.append(f"... and {len(chosen) - max_entries} more")
        return "\n".join(lines)


def _api_tool(mcp: MCPServer, ctx: Context) -> None:
    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    def lookup_api(
        query: Annotated[
            str,
            Field(
                min_length=1,
                description="Function name or words in it, for example 'GetVehicleTransform' "
                "or 'vehicle driver'.",
            ),
        ],
        full_text: Annotated[
            bool, Field(description="Also search descriptions and parameter texts.")
        ] = False,
        max_results: Annotated[int, Field(ge=1, le=50, description="Most functions listed.")] = 10,
    ) -> str:
        """Look up Teardown's Lua API in the user's game install.

        Reads data/script_defs.lua (scripts) and data/voxscript_defs.lua (voxel scripts); a
        name present in both is shown from both.

        An exact name (with or without '()') gives the full documentation (description,
        parameters, return values, example); other queries list matching functions with their
        signatures. Use it before writing a mod script; API v2 scripts start with '#version 2'
        and use client.init(), client.tick() (teardown_reference 'vehicle_xml' for the XML side).
        """
        with user_errors():
            functions = ctx.api()
        query = query.strip().removesuffix("()")
        found = search(functions, query, full_text=full_text)
        if not found:
            hint = "" if full_text else " Try full_text=true."
            return f"No API function matches {query!r}.{hint}"
        exact = [f for f in found if f.name.lower() == query.lower()]
        if exact or len(found) == 1:
            shown = exact or found
            others = [f for f in found if f not in shown][:max_results]
            # Some names exist in both definition files, with different signatures.
            text = "\n\n".join(f.details() for f in shown)
            if others:
                text += "\n\nAlso matching: " + ", ".join(
                    f"{f.name} ({f.source.split(':')[0]})" for f in others
                )
            return text
        lines = [f"{len(found)} functions match {query!r}:"]
        lines += [f"- {f.summary()} [{f.source.split(':')[0]}]" for f in found[:max_results]]
        if len(found) > max_results:
            lines.append(f"... and {len(found) - max_results} more; refine the query")
        lines.append("Call lookup_api with an exact name for the full documentation.")
        return "\n".join(lines)
