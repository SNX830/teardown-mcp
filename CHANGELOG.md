# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) as described in [docs/VERSIONING.md](docs/VERSIONING.md).

## [Unreleased]

### Added
- `buildup.voxcore`: voxel grids in the Teardown frame; shapes as boolean masks (box, cylinder,
  sphere, ellipsoid, half-space, edge cut, chamfer, wedge); operations (fill, paint, carve, union,
  subtract, intersect, flip, mirror, hollow, fill enclosed cavities); composition of placed parts;
  face-connected components (detects voxels that would fall off in Teardown).
- `buildup.render`: true orthographic views (front, back, left, right, top, bottom) and 3/4 views,
  assembled into an annotated preview sheet (rulers in meters with Teardown coordinates, side
  labels, labelled markers, 1 m axis gizmo); text inspection (`describe`: size, extent, materials,
  palette entries, connectivity; `ascii_slice`: layers as text, oriented like the views).
- `scripts/make_preview_samples.py`: sample previews for review (protocol D).
- Runtime dependency: Pillow.

## [0.2.0] - 2026-10-06

### Added
- `scripts/make_calibration_mod.py`: generates the 0.2.0 calibration mod (a prop with axis
  markers and a box car with four cylinder wheels, hand-written XML, read-only Lua probes that
  show the engine's measurements on screen). Test protocol C in `docs/TESTING_IN_GAME.md`.
- Development dependency `lupa`: the calibration probes are tested against a mock engine.
- `buildup.voxio.xml_origin`: where a Teardown XML `vox` `pos` sits inside a grid, as measured in
  game (no half-voxel offset for odd sizes).

### Changed
- The MagicaVoxel -> Teardown axis mapping, the `vox` origin rule, XML `rot`, wheel placement and
  ground contact are now verified in game (`docs/TEARDOWN_REFERENCE.md` §5, status `GAME`).

## [0.1.0] - 2026-10-04

### Added
- `buildup.palette`: the Teardown materials and their palette index ranges, rendering finishes
  (matte, metal, glass, emissive) and a palette allocator that picks indices in the right material
  range and refuses to overflow a material.
- `buildup.voxio`: `.vox` reader (versions 150 and 200, scene graph with composed transforms, named
  objects, palette, materials, palette notes) and writer (version 150, layout of official Teardown
  files, named objects, explicit materials, palette row names for MagicaVoxel).
- Conversion between the internal Teardown frame and MagicaVoxel axes, in one module.
- The reader handles the variants found in official game files: 255-color palettes, shape nodes
  shared by several transforms, duplicate group children; it refuses Teardown's compressed `TDCZ`
  chunk and rotated objects with explicit errors instead of guessing.
- Object names may contain single spaces between words, as in official files ("window 1").
- `scripts/make_sample_vox.py`: generates the MagicaVoxel test file of milestone 0.1.0.
- Tests against every `.vox` file of a local Teardown installation (marked `game`).
- Runtime dependency: numpy.
- CI also tests Python 3.14.

### Fixed
- CI: `astral-sh/setup-uv` has no `v10` tag; actions are now pinned to full commit SHAs.

## [0.0.1] - 2026-09-30

### Added
- Project setup: packaging (`pyproject.toml`, uv), MIT license, quality gate (`scripts/check.py`:
  ruff format, ruff lint, mypy strict, pytest with coverage), CI on Windows and Linux.
- Documentation for AI agents and contributors: `AGENTS.md`, `CLAUDE.md`, roadmap, versioning,
  quality checks, decisions, Teardown/.vox reference from the phase 1 analysis, manual test protocols.
