"""Text inspection of a model: dimensions, voxel counts, materials, connectivity, ASCII slices.

Written for an AI that reads text: every number states its unit, and slices are oriented like
the matching orthographic view (``docs`` of ``buildup.render.views``).
"""

from collections.abc import Sequence
from typing import Final

import numpy as np

from buildup.palette import Material, Palette, material_of_index
from buildup.render.views import ORIENTATIONS, RenderError, View, meters, ortho_view
from buildup.voxcore import EMPTY, Grid, Vec3, components, filled_bounds
from buildup.voxcore.grid import as_int, as_vec3, axis_number, check_grid

#: Symbols for palette indices in ASCII slices, most used index first.
SYMBOLS: Final = "#ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@%&*+=?"
EMPTY_SYMBOL: Final = "."
OTHER_SYMBOL: Final = "~"
#: Slice orientation per axis: the orthographic view looking along that axis.
SLICE_VIEWS: Final = {0: View.LEFT, 1: View.TOP, 2: View.FRONT}
MAX_LISTED_PARTS: Final = 8


def _material_name(index: int) -> str:
    material = material_of_index(index)
    return material.value if isinstance(material, Material) else "reserved"


def symbol_table(grid: Grid) -> dict[int, str]:
    """Symbol of each palette index used in ``grid``, the most used index first."""
    values, counts = np.unique(check_grid(grid)[grid != EMPTY], return_counts=True)
    order = sorted(range(len(values)), key=lambda i: (-int(counts[i]), int(values[i])))
    return {
        int(values[i]): SYMBOLS[n] if n < len(SYMBOLS) else OTHER_SYMBOL
        for n, i in enumerate(order)
    }


def describe(grid: Grid, *, origin: Vec3 = (0, 0, 0), palette: Palette | None = None) -> str:
    """Summarize a model in plain text.

    Args:
        grid: The model (Teardown frame).
        origin: Teardown-frame position of the grid's first cell, in voxels.
        palette: Optional palette, to show colors next to palette indices.

    Returns:
        Several lines: size, filled bounds, voxel counts per material and per palette index,
        and the face-connected parts (more than one part means some voxels may fall apart when
        damaged).
    """
    grid = check_grid(grid)
    origin = as_vec3(origin, "origin")
    sx, sy, sz = grid.shape
    lines = [
        f"Grid: {sx} x {sy} x {sz} voxels = {meters(sx)} x {meters(sy)} x {meters(sz)} m "
        "(X width, Y height, Z length; 1 voxel = 0.1 m).",
    ]
    bounds = filled_bounds(grid)
    if bounds is None:
        lines.append("Filled voxels: 0 (the model is empty).")
        return "\n".join(lines)
    start, end = bounds
    total = int(np.count_nonzero(grid != EMPTY))
    spans = ", ".join(
        f"{axis} {meters(origin[i] + start[i])} to {meters(origin[i] + end[i])} m "
        f"({end[i] - start[i]} voxels)"
        for i, axis in enumerate("XYZ")
    )
    lines.append(f"Filled voxels: {total}. Filled extent (Teardown frame): {spans}.")

    values, counts = np.unique(grid[grid != EMPTY], return_counts=True)
    per_material: dict[str, int] = {}
    for value, count in zip(values, counts, strict=True):
        name = _material_name(int(value))
        per_material[name] = per_material.get(name, 0) + int(count)
    materials = ", ".join(
        f"{name} {count}" for name, count in sorted(per_material.items(), key=lambda kv: -kv[1])
    )
    lines.append(f"Materials (voxels): {materials}.")
    lines.append("Palette indices used:")
    entries = palette.entries if palette is not None else {}
    for value, count in sorted(zip(values, counts, strict=True), key=lambda vc: -int(vc[1])):
        index = int(value)
        entry = entries.get(index)
        color = f", color rgb{entry.color}, {entry.finish.kind.value}" if entry else ""
        lines.append(f"  {index}: {_material_name(index)}{color}: {int(count)} voxels")

    parts = components(grid)
    if len(parts) == 1:
        lines.append("Connectivity: 1 part, all voxels hold together through faces.")
    else:
        lines.append(
            f"Connectivity: {len(parts)} separate parts (face-connected). Voxels touching only "
            "by an edge or a corner do not hold together in Teardown: join or remove the "
            "smaller parts."
        )
        for part in parts[:MAX_LISTED_PARTS]:
            where = ", ".join(
                f"{axis} {meters(origin[i] + part.start[i])}..{meters(origin[i] + part.end[i])}"
                for i, axis in enumerate("XYZ")
            )
            lines.append(f"  part {part.label}: {part.voxels} voxels, {where} m")
        if len(parts) > MAX_LISTED_PARTS:
            lines.append(f"  ... and {len(parts) - MAX_LISTED_PARTS} more parts")
    return "\n".join(lines)


def ascii_slice(
    grid: Grid, axis: str, index: int, *, origin: Vec3 = (0, 0, 0), legend: bool = True
) -> str:
    """One layer of the model as text, oriented like the orthographic view along ``axis``.

    - ``axis="y"``: a horizontal layer seen from above, front (-Z) at the top, +X to the right.
    - ``axis="z"``: a vertical layer seen from the front, +Y up, +X (right side) to the LEFT.
    - ``axis="x"``: a vertical layer seen from the left, +Y up, front (-Z) to the left.

    Args:
        grid: The model.
        axis: Axis perpendicular to the layer.
        index: Layer index along ``axis`` (grid index, 0-based).
        origin: Teardown-frame position of the grid's first cell, for the coordinate labels.
        legend: Append the symbol legend.

    Returns:
        Lines of symbols (``.`` empty), with the Teardown coordinate (voxels) of every row on
        the left and of every 5th column above.

    Raises:
        RenderError: If ``index`` is outside the grid.
        VoxcoreError: If ``axis``, ``index`` or ``origin`` is malformed.
    """
    grid = check_grid(grid)
    origin = as_vec3(origin, "origin")
    index = as_int(index, "layer index")
    a = axis_number(axis)
    if not 0 <= index < grid.shape[a]:
        raise RenderError(
            f"layer {index} is outside the grid (0 to {grid.shape[a] - 1} along {axis})"
        )
    o = ORIENTATIONS[SLICE_VIEWS[a]]
    layer = np.take(grid, [index], axis=a)
    # The view of a one-layer grid shows the layer itself, correctly oriented.
    image = ortho_view(layer, SLICE_VIEWS[a])
    symbols = symbol_table(grid)  # the same symbols on every layer of this grid
    cols = [int(c) + origin[o.right] for c in image.columns]
    rows = [int(r) + origin[o.up] for r in image.rows]
    width = max(len(str(r)) for r in rows)
    header = [" "] * len(cols)
    for i, c in enumerate(cols):
        if c % 5 == 0:
            label = str(c)
            for j, ch in enumerate(label):
                if i + j < len(header):
                    header[i + j] = ch
    names = "XYZ"
    lines = [
        f"Layer {names[a]} = {origin[a] + index} voxels ({meters(origin[a] + index)} m), "
        f"seen {o.seen_from}; columns: {names[o.right]}, rows: {names[o.up]} (voxels)",
        " " * (width + 1) + "".join(header),
    ]
    for r, row in zip(rows, image.indices, strict=True):
        text = "".join(symbols.get(int(v), EMPTY_SYMBOL) if v else EMPTY_SYMBOL for v in row)
        lines.append(f"{r:>{width}} {text}")
    if legend:
        lines.append(legend_line(grid))
    return "\n".join(lines)


def legend_line(grid: Grid) -> str:
    """Meaning of the ASCII slice symbols of ``grid``."""
    table = symbol_table(grid)
    named = [(i, s) for i, s in table.items() if s != OTHER_SYMBOL]
    others = [i for i, s in table.items() if s == OTHER_SYMBOL]
    items = [f"{s} = {i} ({_material_name(i)})" for i, s in named]
    if others:
        items.append(
            f"{OTHER_SYMBOL} = any of {len(others)} rarer indices: " + ", ".join(map(str, others))
        )
    return "Legend: . empty" + (", " + ", ".join(items) if items else "")


def ascii_slices(grid: Grid, axis: str, indices: Sequence[int], *, origin: Vec3 = (0, 0, 0)) -> str:
    """Several layers along ``axis``, separated by blank lines, with one shared legend."""
    blocks = [ascii_slice(grid, axis, i, origin=origin, legend=False) for i in indices]
    return "\n\n".join([*blocks, legend_line(grid)])
