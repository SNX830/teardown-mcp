import itertools

import pytest

from buildup.voxio.rotation import (
    IDENTITY,
    IDENTITY_BYTE,
    Matrix3,
    RotationError,
    apply,
    decode_rotation,
    encode_rotation,
    multiply,
)


def _all_signed_permutations() -> list[Matrix3]:
    matrices: list[Matrix3] = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            rows = []
            for row in range(3):
                values = [0, 0, 0]
                values[perm[row]] = signs[row]
                rows.append((values[0], values[1], values[2]))
            matrices.append((rows[0], rows[1], rows[2]))
    return matrices


def test_identity_byte() -> None:
    assert decode_rotation(IDENTITY_BYTE) == IDENTITY
    assert encode_rotation(IDENTITY) == IDENTITY_BYTE


def test_specification_example() -> None:
    # Example from the official .vox extension specification ("ROTATION type").
    packed = (1 << 0) | (2 << 2) | (0 << 4) | (1 << 5) | (1 << 6)
    assert decode_rotation(packed) == ((0, 1, 0), (0, 0, -1), (-1, 0, 0))


@pytest.mark.parametrize("matrix", _all_signed_permutations())
def test_round_trip_for_all_48_matrices(matrix: Matrix3) -> None:
    assert decode_rotation(encode_rotation(matrix)) == matrix


@pytest.mark.parametrize("packed", [3, 0b0000, 0b1101, 128, -1])
def test_invalid_packed_values(packed: int) -> None:
    with pytest.raises(RotationError):
        decode_rotation(packed)


@pytest.mark.parametrize(
    "matrix",
    [
        ((1, 0, 0), (1, 0, 0), (0, 0, 1)),
        ((2, 0, 0), (0, 1, 0), (0, 0, 1)),
        ((1, 1, 0), (0, 1, 0), (0, 0, 1)),
    ],
)
def test_invalid_matrices(matrix: Matrix3) -> None:
    with pytest.raises(RotationError):
        encode_rotation(matrix)


def test_multiply_order_matters() -> None:
    about_z: Matrix3 = ((0, -1, 0), (1, 0, 0), (0, 0, 1))
    about_x: Matrix3 = ((1, 0, 0), (0, 0, -1), (0, 1, 0))
    assert multiply(about_z, about_x) == ((0, 0, 1), (1, 0, 0), (0, 1, 0))
    assert multiply(about_x, about_z) == ((0, -1, 0), (0, 0, -1), (1, 0, 0))
    assert apply(about_x, (1, 2, 3)) == (1, -3, 2)


def test_multiply_and_apply() -> None:
    quarter_turn_z: Matrix3 = ((0, -1, 0), (1, 0, 0), (0, 0, 1))
    assert apply(quarter_turn_z, (1, 0, 0)) == (0, 1, 0)
    half_turn = multiply(quarter_turn_z, quarter_turn_z)
    assert apply(half_turn, (1, 2, 3)) == (-1, -2, 3)
    assert multiply(IDENTITY, quarter_turn_z) == quarter_turn_z
