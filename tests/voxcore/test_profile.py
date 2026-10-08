"""Profiles: polygon and ASCII sections, extrusion along the right axis, bevels."""

import numpy as np
import pytest

from buildup.voxcore import Face, VoxcoreError, box, chamfer
from buildup.voxcore.profile import (
    MAX_BEVEL,
    Bevel,
    Profile,
    ascii_section,
    bevel_insets,
    bevel_style,
    extrude,
    inner_distance,
    plane_axes,
    polygon_section,
)


def test_polygon_through_whole_coordinates_covers_the_box_cells() -> None:
    section = polygon_section([(2, 1), (6, 1), (6, 4), (2, 4)], (0, 0), (8, 6))
    expected = np.zeros((8, 6), dtype=bool)
    expected[2:6, 1:4] = True
    assert np.array_equal(section, expected)


def test_polygon_uses_cell_centers_and_any_winding() -> None:
    triangle = [(0, 0), (4, 0), (0, 4)]
    section = polygon_section(triangle[::-1], (0, 0), (4, 4))
    # Cell (i, j) is inside when i + 0.5 + j + 0.5 < 4.
    expected = np.array([[i + j + 1 < 4 for j in range(4)] for i in range(4)])
    assert np.array_equal(section, expected)


def test_polygon_window_is_positioned() -> None:
    whole = polygon_section([(-3, -2), (3, -2), (0, 4)], (-4, -3), (8, 8))
    part = polygon_section([(-3, -2), (3, -2), (0, 4)], (0, 0), (4, 5))
    assert np.array_equal(part, whole[4:8, 3:8])


def test_concave_polygon_even_odd() -> None:
    # A "U": two posts joined at the bottom.
    u = [(0, 0), (6, 0), (6, 5), (4, 5), (4, 2), (2, 2), (2, 5), (0, 5)]
    section = polygon_section(u, (0, 0), (6, 5))
    assert section[:2, :].all()
    assert section[4:, :].all()
    assert section[2:4, :2].all()
    assert not section[2:4, 2:].any()


def test_polygon_needs_three_points() -> None:
    with pytest.raises(VoxcoreError, match="at least 3"):
        polygon_section([(0, 0), (1, 1)], (0, 0), (2, 2))


def test_ascii_section_bottom_row_is_v_zero() -> None:
    section = ascii_section(["#..", "## ", "###"])
    assert section.shape == (3, 3)
    assert section[:, 0].tolist() == [True, True, True]  # last row
    assert section[:, 1].tolist() == [True, True, False]
    assert section[:, 2].tolist() == [True, False, False]  # first row


def test_ascii_section_short_rows_and_errors() -> None:
    section = ascii_section(["####", "#"])
    assert section.shape == (4, 2)
    assert section[:, 0].tolist() == [True, False, False, False]
    with pytest.raises(VoxcoreError, match="no rows"):
        ascii_section([])
    with pytest.raises(VoxcoreError, match="fills no cell"):
        ascii_section([" . ", "..."])


def test_inner_distance_of_a_square() -> None:
    section = np.ones((7, 7), dtype=bool)
    distance = inner_distance(section, 5)
    assert distance[0].tolist() == [1] * 7
    assert distance[1, 1:6].tolist() == [2, 2, 2, 2, 2]
    assert distance[3, 3] == 4
    capped = inner_distance(section, 1)
    assert capped.max() == 2


def test_inner_distance_rounds_corners() -> None:
    # Alternating side and diagonal steps: a corner cell next to the border is closer than in
    # a pure square (Chebyshev) metric, giving octagons.
    distance = inner_distance(np.ones((9, 9), dtype=bool), 8)
    assert distance[4, 4] == 5
    assert distance[1, 1] == 2
    assert distance[2, 2] == 3
    assert distance[1, 4] == 2


@pytest.mark.parametrize("size", [1, 2, 3])
def test_chamfer_bevel_matches_voxcore_chamfer(size: int) -> None:
    # A tall section, extruded along X: away from its top and bottom, the bevel at both ends
    # is the chamfer of the four vertical edges (left/right faces against front/back).
    grid = (12, 20, 10)
    profile = Profile("side", np.ones((10, 20), dtype=bool), (0, 0), (0, 12), Bevel(size))
    mask = extrude(grid, profile)
    edges: list[tuple[Face, Face]] = [
        ("left", "front"),
        ("left", "back"),
        ("right", "front"),
        ("right", "back"),
    ]
    expected = chamfer(grid, (0, 0, 0), grid, size, edges)
    assert np.array_equal(mask[:, 10, :], expected[:, 10, :])


def test_bevel_insets() -> None:
    assert bevel_insets(5, 0, "chamfer") == [0] * 5
    assert bevel_insets(7, 3, "chamfer") == [3, 2, 1, 0, 1, 2, 3]
    assert bevel_insets(3, 3, "chamfer") == [3, 2, 3]  # short extrusion: nearest end wins
    assert bevel_insets(5, 1, "round") == [0] * 5
    assert bevel_insets(5, 2, "round") == [1, 0, 0, 0, 1]
    assert bevel_insets(9, 4, "round") == [2, 1, 0, 0, 0, 0, 0, 1, 2]


@pytest.mark.parametrize(
    ("plane", "axes"), [("side", (2, 1, 0)), ("front", (0, 1, 2)), ("top", (0, 2, 1))]
)
def test_extrusion_axes(plane: str, axes: tuple[int, int, int]) -> None:
    assert plane_axes(plane) == axes
    section = np.zeros((3, 2), dtype=bool)
    section[2, 1] = True  # one cell: h = 2, v = 1
    profile = Profile(plane, section, (1, 0), (0, 2))  # type: ignore[arg-type]  # plane checked above
    mask = extrude((4, 4, 4), profile)
    cells = np.argwhere(mask).tolist()
    h, v, e = axes
    assert len(cells) == 2
    for cell in cells:
        assert cell[h] == 3
        assert cell[v] == 1
    assert sorted(cell[e] for cell in cells) == [0, 1]


def test_extrude_offset_and_clipping() -> None:
    section = np.ones((4, 4), dtype=bool)
    profile = Profile("side", section, (-2, -2), (-1, 3))
    mask = extrude((2, 2, 2), profile, offset=(0, 0, 0))
    assert mask.all()
    moved = extrude((3, 3, 3), profile, offset=(1, 1, 1))
    assert np.argwhere(moved).min(axis=0).tolist() == [0, 0, 0]
    assert np.argwhere(moved).max(axis=0).tolist() == [1, 0, 0]
    assert not extrude((2, 2, 2), profile, offset=(10, 0, 0)).any()


def test_round_bevel_of_a_slab() -> None:
    section = np.ones((20, 10), dtype=bool)
    profile = Profile("side", section, (0, 0), (0, 9), Bevel(4, "round"))
    mask = extrude((9, 10, 20), profile)
    # Middle layer intact; outer layers shrunk by 2 cells all around (round 4 inset).
    assert mask[4].all()
    # Cells at distance 3 from the outline are kept, corners included (distance[2, 2] is 3).
    assert mask[0].sum() == (20 - 4) * (10 - 4)
    assert not mask[0, :, 0:2].any()
    assert mask[0, 5, 2:18].all()


def test_bevel_and_profile_validation() -> None:
    with pytest.raises(VoxcoreError, match="at most"):
        Bevel(MAX_BEVEL + 1)
    with pytest.raises(VoxcoreError, match="bevel"):
        Bevel(-1)
    with pytest.raises(VoxcoreError, match="bevel_style"):
        Bevel(1, "smooth")  # type: ignore[arg-type]  # runtime check of bad input
    assert bevel_style("round") == "round"
    assert bevel_style("chamfer") == "chamfer"
    with pytest.raises(VoxcoreError, match="bevel_style"):
        bevel_style(None)
    section = np.ones((2, 2), dtype=bool)
    with pytest.raises(VoxcoreError, match="plane"):
        Profile("diagonal", section, (0, 0), (0, 1))  # type: ignore[arg-type]  # bad input
    with pytest.raises(VoxcoreError, match="2D boolean"):
        Profile("side", np.ones((2, 2), dtype=np.uint8), (0, 0), (0, 1))
    with pytest.raises(VoxcoreError, match="empty"):
        Profile("side", section, (0, 0), (3, 3))


def test_profile_box_equals_voxcore_box() -> None:
    section = polygon_section([(2, 1), (9, 1), (9, 5), (2, 5)], (0, 0), (10, 6))
    mask = extrude((5, 6, 10), Profile("side", section, (0, 0), (1, 4)))
    assert np.array_equal(mask, box((5, 6, 10), (1, 1, 2), (4, 5, 9)))


def test_whitespace_is_empty_in_drawings() -> None:
    section = ascii_section(["\t#", "# "])
    assert section[:, 1].tolist() == [False, True]
    assert section[:, 0].tolist() == [True, False]


def test_profile_normalizes_start_and_span() -> None:
    section = np.ones((1, 1), dtype=bool)
    profile = Profile("side", section, [2, 3], [0, 1])  # type: ignore[arg-type]  # JSON lists
    assert profile.start == (2, 3)
    assert profile.span == (0, 1)
    with pytest.raises(VoxcoreError, match="section start"):
        Profile("side", section, (0.5, 0), (0, 1))  # type: ignore[arg-type]  # bad input
