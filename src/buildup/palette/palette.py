"""Material-aware palette: turns (material, color, finish) into Teardown palette indices."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

import numpy as np
import numpy.typing as npt

from buildup.palette.finish import Finish
from buildup.palette.materials import MATERIAL_INDICES, MAX_INDEX, Material, material_of_index

RGB = tuple[int, int, int]

#: RGBA written for palette slots that no entry uses.
UNUSED_RGBA: Final = (128, 128, 128, 255)


class PaletteError(ValueError):
    """Base class for palette errors."""


class PaletteFullError(PaletteError):
    """All palette slots of a material are already used."""


def _check_color(color: Sequence[object]) -> RGB:
    # Colors may come straight from an AI tool call, so the types are checked at runtime too.
    channels: list[int] = []
    for c in color:
        if isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= 255:
            break
        channels.append(c)
    if len(channels) != 3 or len(color) != 3:
        raise PaletteError(f"color must be three integers 0-255, got {color!r}")
    return (channels[0], channels[1], channels[2])


def default_finish(material: Material) -> Finish:
    """Finish used when none is given: transparent glass for glass, matte otherwise."""
    return Finish.glass() if material is Material.GLASS else Finish.matte()


@dataclass(frozen=True)
class PaletteEntry:
    """One palette slot: the physical material, the displayed color and the rendering finish.

    The finish is explicit here; ``Palette.index_for`` applies ``default_finish`` (decision D-016).
    """

    material: Material
    color: RGB
    finish: Finish

    def __post_init__(self) -> None:
        object.__setattr__(self, "color", _check_color(self.color))


class Palette:
    """A Teardown palette under construction.

    Indices are allocated inside the range of the requested material, so that every voxel painted
    with an index gets the intended physical material in the game.
    """

    def __init__(self) -> None:
        self._entries: dict[int, PaletteEntry] = {}

    @property
    def entries(self) -> Mapping[int, PaletteEntry]:
        """Read-only view of the used slots, by palette index."""
        return MappingProxyType(self._entries)

    def index_for(self, material: Material, color: RGB, finish: Finish | None = None) -> int:
        """Return the palette index for a (material, color, finish), allocating it if needed.

        An identical existing entry is reused. New entries take the lowest free index of the
        material's range.

        Args:
            material: Physical material in the game.
            color: Displayed color as (red, green, blue), each 0-255.
            finish: Rendering finish; defaults to ``default_finish(material)``.

        Raises:
            PaletteFullError: If the material has no free slot left.
            PaletteError: If the color is invalid.
        """
        entry = PaletteEntry(material, color, finish or default_finish(material))
        indices = MATERIAL_INDICES[material]
        for index in indices:
            if self._entries.get(index) == entry:
                return index
        for index in indices:
            if index not in self._entries:
                self._entries[index] = entry
                return index
        raise PaletteFullError(
            f"no free palette slot for {material.value}: its {len(indices)} slots are used; "
            "reuse an existing color of this material"
        )

    def set_entry(self, index: int, entry: PaletteEntry) -> None:
        """Put an entry at an explicit index.

        Raises:
            PaletteError: If the index does not belong to the entry's material.
        """
        if not 1 <= index <= MAX_INDEX or material_of_index(index) is not entry.material:
            raise PaletteError(f"index {index} is not a {entry.material.value} index")
        self._entries[index] = entry

    def free_slots(self, material: Material) -> int:
        """Number of unused slots left for a material."""
        return sum(1 for i in MATERIAL_INDICES[material] if i not in self._entries)

    def rgba(self) -> npt.NDArray[np.uint8]:
        """Colors as a (256, 4) array: row ``i`` is the RGBA of palette index ``i``.

        Row 0 (empty voxel) is all zeros; unused slots get ``UNUSED_RGBA``.
        """
        table = np.empty((MAX_INDEX + 1, 4), dtype=np.uint8)
        table[0] = 0
        table[1:] = UNUSED_RGBA
        for index, entry in self._entries.items():
            table[index] = (*entry.color, 255)
        return table

    def matl(self, index: int) -> dict[str, str]:
        """MagicaVoxel ``MATL`` dictionary of an index (matte for unused slots)."""
        entry = self._entries.get(index)
        return (entry.finish if entry else Finish.matte()).to_matl()
