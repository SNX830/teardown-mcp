import numpy as np
import numpy.typing as npt

from buildup.voxio.axes import (
    grid_from_magica,
    grid_to_magica,
    origin_to_translation,
    pivot,
    size_to_magica,
    translation_to_origin,
)


def _asymmetric_grid() -> npt.NDArray[np.uint8]:
    grid = np.zeros((2, 3, 4), dtype=np.uint8)
    grid[1, 0, 0] = 1  # +X side, bottom, smallest z
    grid[0, 2, 0] = 2  # top
    grid[0, 0, 3] = 3  # largest z (Teardown +Z is the back of a vehicle)
    return grid


def test_grid_mapping_teardown_to_magica() -> None:
    td = _asymmetric_grid()
    mv = grid_to_magica(td)
    assert mv.shape == (2, 4, 3)  # (x, -z, y)
    # Teardown (x, y, z) -> MagicaVoxel cell (x, sz - 1 - z, y) within the model.
    assert mv[1, 3, 0] == 1
    assert mv[0, 3, 2] == 2  # Teardown up (Y) becomes MagicaVoxel up (Z)
    assert mv[0, 0, 0] == 3  # Teardown +Z becomes MagicaVoxel -Y
    assert mv.flags.c_contiguous


def test_grid_round_trip() -> None:
    td = _asymmetric_grid()
    assert np.array_equal(grid_from_magica(grid_to_magica(td)), td)


def test_size_and_pivot() -> None:
    assert size_to_magica((2, 3, 4)) == (2, 4, 3)
    assert pivot((3, 4, 1)) == (1, 2, 0)  # example from the ogt_vox reference documentation


def test_translation_round_trip_for_odd_and_even_sizes() -> None:
    for size in [(1, 1, 1), (3, 4, 5), (8, 2, 7), (256, 1, 256)]:
        for origin in [(0, 0, 0), (5, -3, 12), (-7, 9, -2)]:
            t = origin_to_translation(origin, size)
            assert translation_to_origin(t, size_to_magica(size)) == origin


def test_translation_of_an_odd_cube_at_the_origin() -> None:
    # 3x3x3 at the origin: MagicaVoxel minimum corner (0, -3, 0), pivot floor(3 / 2) = 1 per axis.
    assert origin_to_translation((0, 0, 0), (3, 3, 3)) == (1, -2, 1)
    assert origin_to_translation((0, 0, 0), (3, 4, 5)) == (1, -3, 2)


def test_translation_of_a_cube_at_the_origin() -> None:
    # A 2x2x2 Teardown cube at the origin occupies MagicaVoxel x 0..1, y -2..-1, z 0..1;
    # its pivot is floor(size / 2) = (1, 1, 1) from the minimum corner.
    assert origin_to_translation((0, 0, 0), (2, 2, 2)) == (1, -1, 1)
