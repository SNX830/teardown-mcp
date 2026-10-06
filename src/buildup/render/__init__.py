"""Previews of models: orthographic and 3/4 views, annotated sheets, text inspection.

Pure numpy for the orthographic views, Pillow for drawing (decisions D-005, D-020).
"""

from buildup.render.iso import iso_image
from buildup.render.sheet import DEFAULT_VIEWS, Annotations, Marker, preview_sheet
from buildup.render.text import ascii_slice, ascii_slices, describe, symbol_table
from buildup.render.views import (
    ORIENTATIONS,
    RenderError,
    View,
    ViewImage,
    as_view,
    meters,
    ortho_view,
)

__all__ = [
    "DEFAULT_VIEWS",
    "ORIENTATIONS",
    "Annotations",
    "Marker",
    "RenderError",
    "View",
    "ViewImage",
    "as_view",
    "ascii_slice",
    "ascii_slices",
    "describe",
    "iso_image",
    "meters",
    "ortho_view",
    "preview_sheet",
    "symbol_table",
]
