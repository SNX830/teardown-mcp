"""Generate the 0.3.0 preview samples for Nathan's review (docs/TESTING_IN_GAME.md, protocol D).

Usage:
    uv run python scripts/make_preview_samples.py [output folder]

Default output: workspace/previews/. For each sample: a preview sheet (PNG) and a text report
(dimensions, materials, connectivity, ASCII slices), both built only with buildup.voxcore and
buildup.render.
"""

import sys
from pathlib import Path

import numpy as np

from buildup.palette import Finish, Material, Palette
from buildup.render import Annotations, Marker, ascii_slices, describe, preview_sheet
from buildup.voxcore import (
    Grid,
    Vec3,
    box,
    carve,
    chamfer,
    compose,
    cylinder,
    edge_cut,
    fill,
    hollow,
    mirror,
    new_grid,
    paint,
    sphere,
    union,
    wedge,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "workspace" / "previews"


def pickup(palette: Palette) -> tuple[Grid, Vec3, list[Marker]]:
    """A small blocky pickup truck, front at -Z, built from voxcore shapes and parts."""
    paint_red = palette.index_for(Material.WEAK_METAL, (170, 30, 30), Finish.metal(0.4))
    trim = palette.index_for(Material.WEAK_METAL, (40, 40, 45))
    glass = palette.index_for(Material.GLASS, (150, 200, 230))
    head = palette.index_for(Material.HARD_METAL, (255, 245, 210), Finish.emissive())
    tail = palette.index_for(Material.HARD_METAL, (255, 30, 20), Finish.emissive())
    tire = palette.index_for(Material.PLASTIC, (30, 30, 30))
    rim = palette.index_for(Material.PLASTIC, (180, 180, 180))

    size = (18, 13, 44)  # 1.8 x 1.3 x 4.4 m body box, built on the left half then mirrored
    body = new_grid(size)
    body = fill(body, chamfer(size, (0, 3, 0), (18, 8, 44), 2, [("top", "front")]), paint_red)
    # Cab: a hollow shell with a sloped windshield. Its outer layer between y 9 and 11 becomes
    # glass, except the pillars (corners and the middle post at z 18).
    cab_start, cab_end = (1, 8, 12), (17, 13, 26)
    cab_mask = box(size, cab_start, cab_end) & ~edge_cut(
        size, cab_start, cab_end, ("top", "front"), (4, 6)
    )
    cab = hollow(fill(new_grid(size), cab_mask, paint_red))
    pillars = (
        box(size, (1, 8, 18), (17, 13, 19))
        | box(size, (1, 8, 12), (2, 13, 26))
        | box(size, (16, 8, 12), (17, 13, 26))
    )
    band = box(size, (1, 9, 12), (17, 12, 26)) & ~pillars
    body = union(body, paint(cab, band, glass))
    # Side windows, on the pillar columns, between the posts.
    side = (box(size, (1, 9, 13), (2, 12, 18)) | box(size, (1, 9, 19), (2, 12, 25))) & (cab > 0)
    body = paint(body, side, glass)
    # Open bed at the back.
    body = carve(body, box(size, (2, 5, 28), (16, 8, 43)))
    body = paint(body, box(size, (0, 3, 0), (18, 4, 44)), trim)
    body = paint(body, box(size, (1, 5, 0), (4, 7, 1)), head)
    body = paint(body, box(size, (1, 5, 43), (3, 7, 44)), tail)
    body = mirror(body, "x")  # make both sides identical (left half kept)
    body_origin = (-9, 2, -22)

    wheel = new_grid((3, 8, 8))
    wheel = fill(wheel, cylinder(wheel.shape, "x", (4, 4), 4, (0, 3)), tire)
    wheel = paint(wheel, cylinder(wheel.shape, "x", (4, 4), 2, (0, 3)), rim)
    parts = [(body, body_origin)]
    markers = []
    # Body cells span x -9..8; wheels (3 wide) go just outside: x -12..-10 and 9..11.
    for name, x0, z in (("fl", -12, -14), ("fr", 9, -14), ("bl", -12, 14), ("br", 9, 14)):
        parts.append((wheel, (x0, 0, z - 4)))
        markers.append(Marker(f"wheel_{name}", (x0 + 1.5, 4.0, float(z))))
    grid, origin = compose(parts)
    return grid, origin, markers


def gallery(palette: Palette) -> tuple[Grid, Vec3, list[Marker]]:
    """One of each shape and operation, side by side along X, on a thin plate."""
    concrete = palette.index_for(Material.CONCRETE, (150, 150, 150))
    wood = palette.index_for(Material.WOOD, (150, 100, 55))
    blue = palette.index_for(Material.PLASTIC, (40, 90, 200))
    green = palette.index_for(Material.PLASTIC, (40, 170, 70))
    orange = palette.index_for(Material.PLASTIC, (230, 130, 30))
    size = (78, 12, 14)
    g = new_grid(size)
    g = fill(g, box(size, (0, 0, 0), (78, 1, 14)), concrete)
    g = fill(g, box(size, (2, 1, 3), (10, 9, 11)), wood)  # box
    g = fill(
        g, chamfer(size, (14, 1, 3), (22, 9, 11), 3, [("top", "front"), ("top", "left")]), blue
    )
    g = fill(g, wedge(size, (26, 1, 3), (34, 9, 11), ("top", "front")), green)  # ramp
    g = fill(g, cylinder(size, "y", (42, 7), 4, (1, 10)), orange)  # post
    g = fill(g, sphere(size, (54, 5, 7), 4), blue)
    shell = hollow(np.where(box(size, (62, 1, 3), (74, 11, 11)), wood, 0).astype(np.uint8))
    shell = carve(shell, box(size, (62, 1, 3), (74, 11, 7)))  # cut away the front half
    g = np.where(shell > 0, shell, g).astype(np.uint8)
    labels = ["box", "chamfer", "wedge", "cylinder", "sphere", "hollow"]
    centers = [6, 18, 30, 42, 54, 68]
    markers = [Marker(lbl, (float(c), 11.0, 3.0)) for lbl, c in zip(labels, centers, strict=True)]
    return g, (0, 0, 0), markers


def main() -> int:
    """Write the sample previews and reports."""
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    for name, build in (("pickup", pickup), ("gallery", gallery)):
        palette = Palette()
        grid, origin, markers = build(palette)
        sheet = preview_sheet(
            grid, palette.rgba(), origin=origin, annotations=Annotations(name, tuple(markers))
        )
        sheet.save(output / f"{name}.png")
        middle = [grid.shape[1] // 2, grid.shape[1] - 4]
        report = "\n\n".join(
            [
                describe(grid, origin=origin, palette=palette),
                ascii_slices(grid, "y", middle, origin=origin),
            ]
        )
        (output / f"{name}.txt").write_text(report + "\n", encoding="utf-8")
        print(f"Wrote {output / name}.png and .txt ({sheet.width} x {sheet.height} px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
