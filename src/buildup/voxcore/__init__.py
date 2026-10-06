"""Voxel modelling core: grids, shapes (masks), operations and analysis (AGENTS.md §5).

Grids are ``uint8`` arrays indexed ``[x, y, z]`` in the Teardown frame (X right, Y up, front is
-Z; 1 voxel = 0.1 m); 0 is empty, 1-255 a palette index.
"""

from buildup.voxcore.analysis import Component, components, is_connected, label_components
from buildup.voxcore.grid import (
    EMPTY,
    Axis,
    Grid,
    Mask,
    Vec3,
    VoxcoreError,
    compose,
    crop,
    filled_bounds,
    new_grid,
)
from buildup.voxcore.ops import (
    carve,
    fill,
    fill_enclosed,
    flip,
    hollow,
    intersect,
    mirror,
    outside,
    paint,
    subtract,
    union,
)
from buildup.voxcore.shapes import (
    FACES,
    Face,
    box,
    chamfer,
    cylinder,
    edge_cut,
    ellipsoid,
    half_space,
    sphere,
    wedge,
)

__all__ = [
    "EMPTY",
    "FACES",
    "Axis",
    "Component",
    "Face",
    "Grid",
    "Mask",
    "Vec3",
    "VoxcoreError",
    "box",
    "carve",
    "chamfer",
    "components",
    "compose",
    "crop",
    "cylinder",
    "edge_cut",
    "ellipsoid",
    "fill",
    "fill_enclosed",
    "filled_bounds",
    "flip",
    "half_space",
    "hollow",
    "intersect",
    "is_connected",
    "label_components",
    "mirror",
    "new_grid",
    "outside",
    "paint",
    "sphere",
    "subtract",
    "union",
    "wedge",
]
