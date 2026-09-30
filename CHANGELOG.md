# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) as described in [docs/VERSIONING.md](docs/VERSIONING.md).

## [Unreleased]

### Fixed
- CI: `astral-sh/setup-uv` has no `v10` tag; actions are now pinned to full commit SHAs.

## [0.0.1] - 2026-09-30

### Added
- Project setup: packaging (`pyproject.toml`, uv), MIT license, quality gate (`scripts/check.py`:
  ruff format, ruff lint, mypy strict, pytest with coverage), CI on Windows and Linux.
- Documentation for AI agents and contributors: `AGENTS.md`, `CLAUDE.md`, roadmap, versioning,
  quality checks, decisions, Teardown/.vox reference from the phase 1 analysis, manual test protocols.
