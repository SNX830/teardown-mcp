"""MagicaVoxel packed rotations (the ``_r`` attribute of transform nodes).

A rotation is a 3x3 matrix whose rows each hold a single non-zero entry, +1 or -1. It is packed into
one byte (official format specification, "ROTATION type"):

- bits 0-1: column index of the non-zero entry in row 0
- bits 2-3: column index of the non-zero entry in row 1
- bit 4, 5, 6: sign of rows 0, 1, 2 (0 = positive, 1 = negative)
"""

from typing import Final

Matrix3 = tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]

IDENTITY: Final[Matrix3] = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
IDENTITY_BYTE: Final = 0b0000100


class RotationError(ValueError):
    """Invalid packed rotation or rotation matrix."""


def decode_rotation(packed: int) -> Matrix3:
    """Unpack a ``_r`` byte into a rotation matrix.

    Raises:
        RotationError: If the byte does not describe a signed permutation matrix.
    """
    if not 0 <= packed <= 0x7F:
        raise RotationError(f"packed rotation must be in 0..127, got {packed}")
    col0 = packed & 0b11
    col1 = (packed >> 2) & 0b11
    if col0 > 2 or col1 > 2 or col0 == col1:
        raise RotationError(f"invalid packed rotation {packed}")
    col2 = 3 - col0 - col1
    rows: list[tuple[int, int, int]] = []
    for row, col in enumerate((col0, col1, col2)):
        sign = -1 if packed & (1 << (4 + row)) else 1
        values = [0, 0, 0]
        values[col] = sign
        rows.append((values[0], values[1], values[2]))
    return (rows[0], rows[1], rows[2])


def encode_rotation(matrix: Matrix3) -> int:
    """Pack a signed permutation matrix into a ``_r`` byte.

    Raises:
        RotationError: If the matrix is not a signed permutation matrix.
    """
    columns: list[int] = []
    packed = 0
    for row_index, row in enumerate(matrix):
        nonzero = [(col, value) for col, value in enumerate(row) if value != 0]
        if len(nonzero) != 1 or nonzero[0][1] not in (1, -1):
            raise RotationError(f"not a signed permutation matrix: {matrix}")
        col, value = nonzero[0]
        columns.append(col)
        if value < 0:
            packed |= 1 << (4 + row_index)
    if sorted(columns) != [0, 1, 2]:
        raise RotationError(f"not a signed permutation matrix: {matrix}")
    return packed | columns[0] | (columns[1] << 2)


def multiply(a: Matrix3, b: Matrix3) -> Matrix3:
    """Matrix product ``a @ b``."""
    rows = [tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3)]
    return (
        (rows[0][0], rows[0][1], rows[0][2]),
        (rows[1][0], rows[1][1], rows[1][2]),
        (rows[2][0], rows[2][1], rows[2][2]),
    )


def apply(matrix: Matrix3, vector: tuple[int, int, int]) -> tuple[int, int, int]:
    """Matrix-vector product ``matrix @ vector``."""
    x, y, z = (sum(matrix[i][k] * vector[k] for k in range(3)) for i in range(3))
    return (x, y, z)
