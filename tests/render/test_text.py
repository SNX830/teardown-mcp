from typing import Any

import numpy as np
import pytest

from buildup.palette import Material, Palette
from buildup.render import RenderError, ascii_slice, ascii_slices, describe, symbol_table
from buildup.render.text import OTHER_SYMBOL, SYMBOLS
from buildup.voxcore import VoxcoreError, new_grid


def _palette() -> tuple[Palette, int, int]:
    palette = Palette()
    metal = palette.index_for(Material.WEAK_METAL, (90, 110, 150))
    glass = palette.index_for(Material.GLASS, (150, 200, 230))
    return palette, metal, glass


def test_describe_sizes_materials_and_one_part() -> None:
    palette, metal, glass = _palette()
    grid = new_grid((16, 6, 36))
    grid[:, 0:4, :] = metal
    grid[2:14, 4:6, 10:20] = glass
    text = describe(grid, origin=(-8, 3, -18), palette=palette)
    assert "16 x 6 x 36 voxels = 1.6 x 0.6 x 3.6 m" in text
    assert "X -0.8 to 0.8 m (16 voxels)" in text
    assert "Y 0.3 to 0.9 m (6 voxels)" in text
    assert "Z -1.8 to 1.8 m (36 voxels)" in text
    assert f"Filled voxels: {16 * 4 * 36 + 12 * 2 * 10}." in text
    assert "weak metal 2304, glass 240" in text
    assert f"{metal}: weak metal, color rgb(90, 110, 150), matte: 2304 voxels" in text
    assert "1 part" in text


def test_describe_lists_separate_parts() -> None:
    grid = new_grid((10, 1, 1))
    grid[0:6, 0, 0] = 121
    grid[8, 0, 0] = 121
    text = describe(grid)
    assert "2 separate parts" in text
    assert "part 2: 1 voxels, X 0.8..0.9" in text
    assert "rgb" not in text  # no palette given


def test_describe_empty_and_reserved() -> None:
    assert "0 (the model is empty)" in describe(new_grid((2, 2, 2)))
    grid = new_grid((1, 1, 1))
    grid[0, 0, 0] = 200  # a reserved index
    assert "reserved 1" in describe(grid)


def test_top_slice_orientation_and_labels() -> None:
    grid = new_grid((3, 1, 2))
    grid[2, 0, 0] = 121  # right side (+X), front (-Z)
    grid[0, 0, 1] = 1  # left side, back
    text = ascii_slice(grid, "y", 0, origin=(-1, 0, -1))
    lines = text.splitlines()
    assert lines[0].startswith("Layer Y = 0 voxels (0 m), seen from above")
    assert lines[1] == "    0 "  # column labels: x = -1, 0, 1 -> "0" above x = 0
    assert lines[2] == "-1 ..A"  # front row first, +X to the right
    assert lines[3] == " 0 #.."
    assert lines[4] == "Legend: . empty, # = 1 (glass), A = 121 (weak metal)"


def test_front_slice_is_seen_from_the_front() -> None:
    grid = new_grid((2, 2, 1))
    grid[1, 1, 0] = 5  # right side (+X), top
    lines = ascii_slice(grid, "z", 0, legend=False).splitlines()
    assert lines[2:] == ["1 #.", "0 .."]  # +X appears on the LEFT, as in the front view


def test_side_slice_is_seen_from_the_left() -> None:
    grid = new_grid((1, 1, 3))
    grid[0, 0, 0] = 5  # front
    lines = ascii_slice(grid, "x", 0, legend=False).splitlines()
    assert lines[2] == "0 #.."  # front on the left


def test_symbols_are_shared_by_all_layers() -> None:
    grid = new_grid((2, 2, 1))
    grid[:, 0, 0] = 7  # most used: '#'
    grid[0, 1, 0] = 9
    assert symbol_table(grid) == {7: "#", 9: "A"}
    top_layer = ascii_slice(grid, "y", 1, legend=False)
    assert top_layer.splitlines()[2].endswith("A.")
    text = ascii_slices(grid, "y", [0, 1])
    assert text.count("Legend") == 1
    assert text.count("Layer Y") == 2


def test_slice_outside_grid() -> None:
    with pytest.raises(ValueError, match="outside"):
        ascii_slice(new_grid((2, 2, 2)), "y", 2)


def test_inputs_are_validated() -> None:
    bad_origin: Any = (1, 2)
    with pytest.raises(VoxcoreError, match="origin"):
        describe(new_grid((1, 1, 1)), origin=bad_origin)
    bad_index: Any = 0.5
    with pytest.raises(VoxcoreError, match="layer index"):
        ascii_slice(new_grid((2, 2, 2)), "y", bad_index)
    with pytest.raises(RenderError, match="outside"):
        ascii_slice(new_grid((2, 2, 2)), "y", -1)


def test_legend_lists_rare_indices_sharing_one_symbol() -> None:
    grid = new_grid((80, 1, 1))
    grid[:, 0, 0] = np.arange(1, 81)  # 80 different palette indices, one voxel each
    table = symbol_table(grid)
    assert len(set(table.values())) == len(SYMBOLS) + 1  # every symbol, plus the shared one
    legend = ascii_slices(grid, "y", [0]).splitlines()[-1]
    rare = 80 - len(SYMBOLS)
    assert f"{OTHER_SYMBOL} = any of {rare} rarer indices: " in legend
