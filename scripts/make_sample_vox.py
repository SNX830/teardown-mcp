"""Generate the 0.1.0 MagicaVoxel test file (docs/TESTING_IN_GAME.md, protocol A).

Usage:
    uv run python scripts/make_sample_vox.py [output path]

Default output: workspace/samples/buildup-sample.vox
"""

import sys
from pathlib import Path

import numpy as np

from buildup.palette import Finish, Material, Palette
from buildup.voxio import VoxObject, write_vox

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "workspace" / "samples" / "buildup-sample.vox"


def _box(size: tuple[int, int, int], index: int) -> np.ndarray[tuple[int, ...], np.dtype[np.uint8]]:
    return np.full(size, index, dtype=np.uint8)


def build() -> tuple[list[VoxObject], Palette]:
    """Build the sample scene (Teardown frame: X right, Y up, front is -Z; units are voxels)."""
    palette = Palette()
    concrete = palette.index_for(Material.CONCRETE, (150, 150, 150))
    red_metal = palette.index_for(Material.WEAK_METAL, (200, 40, 40), Finish.metal(0.3))
    wood = palette.index_for(Material.WOOD, (140, 90, 50))
    glass = palette.index_for(Material.GLASS, (150, 200, 230))
    lamp = palette.index_for(Material.HARD_METAL, (255, 230, 150), Finish.emissive(0.8, 3))
    axis_x = palette.index_for(Material.PLASTIC, (230, 30, 30))
    axis_up = palette.index_for(Material.PLASTIC, (30, 200, 30))
    axis_front = palette.index_for(Material.PLASTIC, (30, 60, 230))

    objects = [
        VoxObject("ground", _box((12, 1, 12), concrete), (0, 0, 0)),
        # Odd and even sizes side by side: they must touch exactly, with no gap and no overlap.
        VoxObject("cube_odd", _box((3, 3, 3), red_metal), (1, 1, 1)),
        VoxObject("cube_even", _box((4, 4, 4), wood), (4, 1, 1)),
        VoxObject("window", _box((4, 3, 1), glass), (1, 1, 6)),
        VoxObject("lamp", _box((2, 2, 2), lamp), (9, 1, 9)),
        # Axis markers, outside the ground plate; all three meet at the green bar (x=-2, z=-2).
        VoxObject("axis_x_right", _box((8, 1, 1), axis_x), (-1, 0, -2)),
        VoxObject("axis_y_up", _box((1, 8, 1), axis_up), (-2, 0, -2)),
        VoxObject("axis_front", _box((1, 1, 8), axis_front), (-2, 0, -10)),
    ]
    return objects, palette


def main() -> int:
    """Write the sample file and print where it is."""
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    objects, palette = build()
    write_vox(output, objects, palette)
    print(f"Wrote {len(objects)} objects to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
