# Buildup — an MCP server for Teardown voxel modding

> **Status: pre-alpha (0.6.0).** The MCP server works for simple vehicles and props: a fresh
> Claude Code session built a drivable car with it. See [docs/ROADMAP.md](docs/ROADMAP.md).

Buildup is an [MCP](https://modelcontextprotocol.io/) server that lets an AI assistant (such as Claude
Code) build **complete, Teardown-ready voxel models**: multi-part `.vox` files using Teardown's material
palette, previews the AI can look at to correct its work, and a manifest (object names, sizes, anchor
points) plus a known-good XML skeleton, so the AI can then write the mod's XML and Lua files coherently.

Goal: anyone can describe a vehicle and get a working [Teardown](https://teardowngame.com/) mod, without
knowing voxel modelling or modding.

## Using it with Claude Code

Requires [uv](https://docs.astral.sh/uv/) and a clone of this repository. Buildup runs as a local
MCP server over stdio:

```bash
uv run --project /path/to/teardown-mcp buildup-mcp --workspace /path/to/your/folder/workspace
```

The easiest way to register it for Claude Code sessions opened in a folder of yours (outside this
repository) is:

```bash
uv run python scripts/write_mcp_config.py /path/to/your/folder
```

which writes `/path/to/your/folder/.mcp.json`. Start Claude Code in that folder, approve the
`buildup` server, and ask for a vehicle. Buildup writes projects to `workspace/projects/` and
exported mods to `workspace/mods/<Mod Name>/`; copy a mod folder into
`Documents\Teardown\mods\` to test it. Buildup never writes into the game's folders.

Tools: projects (`create_project`, `list_projects`, `project_summary`, `undo`), vehicle
templates to customize (`start_from_template`: sedan, SUV, pickup, van, truck), colors and parts
(`define_color`, `add_part`, `remove_part`), drawing (`draw_profile` for silhouettes, `draw_box`,
`draw_cylinder`, `draw_ellipsoid`, `draw_wedge`, `cut_edges`), operations (`mirror_part`,
`hollow_part`, `move_part`, `add_wheels`, `set_anchor` for seats, lights and locations,
`set_handling` for driving presets),
inspection (`preview` image with see-through glass, `inspect`,
`slice_layers`), `export_model` (`.vox`, manifest, XML prefab skeleton),
`teardown_reference`, and coherence tools that read the user's game files without changing
them: `validate_mod` (checks a mod folder), `read_game_log` (the game's errors for a mod) and
`lookup_api` (Teardown's Lua API from the local install).

## Documentation

- [Roadmap](docs/ROADMAP.md)
- [Teardown and .vox reference](docs/TEARDOWN_REFERENCE.md)
- [Versioning](docs/VERSIONING.md)
- For contributors and AI agents: [AGENTS.md](AGENTS.md), [quality checks](docs/QUALITY_CHECKS.md)

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python scripts/check.py
```

## Credits

Created by SNX830. The code is written with [Claude Code](https://claude.com/claude-code) (Anthropic).

## Legal

MIT licensed (see [LICENSE](LICENSE)). This project is not affiliated with or endorsed by Tuxedo Labs
(Teardown) or ephtracy (MagicaVoxel). It does not contain or redistribute any game files.
