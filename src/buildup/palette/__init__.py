"""Teardown material-aware palette (see docs/TEARDOWN_REFERENCE.md §3)."""

from buildup.palette.finish import Finish, FinishKind
from buildup.palette.materials import (
    MATERIAL_INDICES,
    MAX_INDEX,
    Material,
    material_of_index,
    palette_row_names,
)
from buildup.palette.palette import (
    RGB,
    Palette,
    PaletteEntry,
    PaletteError,
    PaletteFullError,
    default_finish,
)

__all__ = [
    "MATERIAL_INDICES",
    "MAX_INDEX",
    "RGB",
    "Finish",
    "FinishKind",
    "Material",
    "Palette",
    "PaletteEntry",
    "PaletteError",
    "PaletteFullError",
    "default_finish",
    "material_of_index",
    "palette_row_names",
]
