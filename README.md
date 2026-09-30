# Buildup — an MCP server for Teardown voxel modding

> **Status: pre-alpha, in development.** Nothing is usable yet. See [docs/ROADMAP.md](docs/ROADMAP.md).

Buildup is an [MCP](https://modelcontextprotocol.io/) server that lets an AI assistant (such as Claude
Code) build **complete, Teardown-ready voxel models**: multi-part `.vox` files using Teardown's material
palette, previews the AI can look at to correct its work, and a manifest (object names, sizes, anchor
points) plus a known-good XML skeleton, so the AI can then write the mod's XML and Lua files coherently.

Goal: anyone can describe a vehicle and get a working [Teardown](https://teardowngame.com/) mod, without
knowing voxel modelling or modding.

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
