"""Teardown materials and the palette index ranges that select them.

In Teardown the physical material of a voxel depends only on its palette index, never on its color.
Source and verification status: docs/TEARDOWN_REFERENCE.md §3 (table extracted from the official
``data/built-in/palette.vox``, consistent with the official modding documentation).
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class Material(StrEnum):
    """A Teardown physical material. Values are the names Teardown uses in its palette notes."""

    GLASS = "glass"
    GRASS = "grass"
    DIRT = "dirt"
    ROCK = "rock"
    WOOD = "wood"
    CONCRETE = "concrete"
    BRICK = "brick"
    PLASTER = "plaster"
    WEAK_METAL = "weak metal"
    HEAVY_METAL = "heavy metal"
    PLASTIC = "plastic"
    HARD_METAL = "hard metal"
    HARD_MASONRY = "hard masonry"
    UNPHYSICAL = "unphysical"


#: Palette indices available for each material (``range`` end is exclusive).
MATERIAL_INDICES: Final[Mapping[Material, range]] = MappingProxyType(
    {
        Material.GLASS: range(1, 9),
        Material.GRASS: range(9, 25),
        Material.DIRT: range(25, 41),
        Material.ROCK: range(41, 57),
        Material.WOOD: range(57, 73),
        Material.CONCRETE: range(73, 89),
        Material.BRICK: range(89, 105),
        Material.PLASTER: range(105, 121),
        Material.WEAK_METAL: range(121, 137),
        Material.HEAVY_METAL: range(137, 153),
        Material.PLASTIC: range(153, 169),
        Material.HARD_METAL: range(169, 177),
        Material.HARD_MASONRY: range(177, 185),
        Material.UNPHYSICAL: range(225, 241),
    }
)

#: Name MagicaVoxel shows for palette rows that no material uses.
RESERVED_ROW_NAME: Final = "reserved"

#: The MagicaVoxel palette is shown as 32 rows of 8 colors.
PALETTE_ROWS: Final = 32
ROW_LENGTH: Final = 8

#: Highest usable palette index (index 0 means "empty voxel").
MAX_INDEX: Final = 255


def material_of_index(index: int) -> Material | None:
    """Return the material selected by a palette index, or ``None`` for a reserved index.

    Args:
        index: Palette index, 1 to 255.

    Raises:
        ValueError: If the index is outside 1..255.
    """
    if not 1 <= index <= MAX_INDEX:
        raise ValueError(f"palette index must be in 1..{MAX_INDEX}, got {index}")
    for material, indices in MATERIAL_INDICES.items():
        if index in indices:
            return material
    return None


def palette_row_names() -> list[str]:
    """Return the 32 palette row names, in the order of the ``.vox`` ``NOTE`` chunk.

    Row ``r`` of the note list covers palette indices ``(31 - r) * 8 + 1`` to ``(31 - r) * 8 + 8``
    (row 31 is indices 1-8). Rows that no material uses are named ``"reserved"``.
    """
    names: list[str] = []
    for row in range(PALETTE_ROWS):
        first_index = (PALETTE_ROWS - 1 - row) * ROW_LENGTH + 1
        material = material_of_index(first_index)
        names.append(RESERVED_ROW_NAME if material is None else material.value)
    return names
