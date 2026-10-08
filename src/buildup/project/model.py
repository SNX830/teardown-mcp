"""A modelling project in memory: colors, parts, wheels, anchors, and the edits tools make.

Everything is in the model frame (Teardown frame, voxels, see ``buildup.teardown.assembly``).
A part is a set of voxels stored as a grid cropped to them plus the position of the grid's first
cell, so tools never need to manage grid sizes: drawing grows the part, carving shrinks it.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Final, Literal

import numpy as np

from buildup.palette import (
    MATERIAL_INDICES,
    RGB,
    Finish,
    Material,
    Palette,
    PaletteEntry,
    default_finish,
)
from buildup.project.names import ProjectError, check_name
from buildup.project.shapes import (
    WORLD_MAX,
    WORLD_MIN,
    Shape,
    clip_to_world,
    cylinder_shape,
    inside_world,
)
from buildup.teardown import Kind, Point
from buildup.teardown.handling import DEFAULT_HANDLING, HANDLING
from buildup.voxcore import EMPTY, Grid, Vec3, compose, filled_bounds, hollow
from buildup.voxcore.grid import as_float3, as_int, as_number, as_vec3

PartRole = Literal["body", "wheel"]
EditMode = Literal["add", "paint", "carve"]
EDIT_MODES: Final = ("add", "paint", "carve")
FINISHES: Final = ("auto", "matte", "metal", "glass", "emissive")
MAX_PARTS: Final = 32
MAX_ANCHORS: Final = 32
MAX_AXLES: Final = 4
#: Wheel diameter limits in voxels (even, so that axles sit on whole voxels).
MIN_WHEEL_DIAMETER: Final = 4
MAX_WHEEL_DIAMETER: Final = 64
MAX_WHEEL_WIDTH: Final = 32

#: Wheel position names along the vehicle, by number of axles, front first.
_AXLE_NAMES: Final[dict[int, tuple[str, ...]]] = {
    1: ("m",),
    2: ("f", "b"),
    3: ("f", "m", "b"),
    4: ("f", "m1", "m2", "b"),
}


@dataclass(frozen=True)
class Color:
    """A named color: a palette entry reserved for this name.

    Attributes:
        name: Name used by the drawing tools.
        index: Palette index (decides the material in game).
        material: Physical material.
        rgb: Displayed color.
        finish: Rendering finish.
    """

    name: str
    index: int
    material: Material
    rgb: RGB
    finish: Finish


@dataclass(frozen=True)
class WheelInfo:
    """What makes a part a wheel.

    Attributes:
        position: Wheel name in the XML (``fl``, ``fr``, ``bl``, ``br``, ``ml``...).
        axle: Center of the wheel, continuous model-frame voxel coordinates.
        steer: Whether the wheel steers.
        drive: Whether the engine drives it.
    """

    position: str
    axle: Point
    steer: bool
    drive: bool


@dataclass
class Part:
    """A named voxel object of the model.

    Attributes:
        name: Part name (also the object name in the ``.vox`` file).
        role: ``"body"`` (attached to the main body) or ``"wheel"``.
        grid: Voxels, cropped to the filled cells; ``None`` while the part is empty.
        origin: Model-frame position of the grid's first cell.
        wheel: Wheel data for wheel parts.
    """

    name: str
    role: PartRole = "body"
    grid: Grid | None = None
    origin: Vec3 = (0, 0, 0)
    wheel: WheelInfo | None = None

    def bounds(self) -> tuple[Vec3, Vec3] | None:
        """Model-frame ``(start, end)`` of the voxels (end exclusive), ``None`` if empty."""
        if self.grid is None:
            return None
        sx, sy, sz = self.grid.shape
        ox, oy, oz = self.origin
        return (ox, oy, oz), (ox + sx, oy + sy, oz + sz)

    @property
    def voxels(self) -> int:
        """Number of filled voxels."""
        return 0 if self.grid is None else int(np.count_nonzero(self.grid))

    def trim(self) -> None:
        """Crop the grid to its filled cells (``grid`` becomes ``None`` when nothing is left)."""
        if self.grid is None:
            return
        found = filled_bounds(self.grid)
        if found is None:
            self.grid = None
            return
        (x0, y0, z0), (x1, y1, z1) = found
        if (x0, y0, z0) != (0, 0, 0) or (x1, y1, z1) != self.grid.shape:
            self.grid = self.grid[x0:x1, y0:y1, z0:z1].copy()
            ox, oy, oz = self.origin
            self.origin = (ox + x0, oy + y0, oz + z0)

    def grow(self, start: Vec3, end: Vec3) -> None:
        """Enlarge the grid so that it covers the cells ``start..end``."""
        current = self.bounds()
        if current is not None:
            start = (
                min(start[0], current[0][0]),
                min(start[1], current[0][1]),
                min(start[2], current[0][2]),
            )
            end = (
                max(end[0], current[1][0]),
                max(end[1], current[1][1]),
                max(end[2], current[1][2]),
            )
            if (start, end) == current:
                return
        grid = np.zeros((end[0] - start[0], end[1] - start[1], end[2] - start[2]), np.uint8)
        if self.grid is not None:
            x, y, z = (self.origin[i] - start[i] for i in range(3))
            sx, sy, sz = self.grid.shape
            grid[x : x + sx, y : y + sy, z : z + sz] = self.grid
        self.grid = grid
        self.origin = start


@dataclass(frozen=True)
class WheelLayout:
    """Dimensions shared by the wheels of ``Project.add_wheels`` (voxels).

    Attributes:
        diameter: Even number of voxels, 4 to 64.
        width: Wheel width along X, 1 to 32.
        inner_x: Distance from the center line (X = 0) to the inner face of each wheel.
        axle_height: Y of the axles; ``None`` puts the wheel bottoms at Y = 0.
    """

    diameter: int
    width: int
    inner_x: int
    axle_height: int | None = None


@dataclass(frozen=True)
class Axle:
    """One axle of ``Project.add_wheels``: two wheels at the same Z.

    Attributes:
        z: Model-frame Z of the axle (voxels; front axles have negative Z).
        steer: Whether its wheels steer.
        drive: Whether the engine drives them.
    """

    z: int
    steer: bool = False
    drive: bool = False


def parse_material(value: object) -> Material:
    """Material from its name, ``"weak metal"`` or ``"weak_metal"``.

    Raises:
        ProjectError: For an unknown name (the message lists the materials).
    """
    if isinstance(value, str):
        key = value.strip().lower().replace("_", " ")
        for material in Material:
            if material.value == key:
                return material
    names = ", ".join(m.value for m in MATERIAL_INDICES)
    raise ProjectError(f"unknown material {value!r}; materials: {names}")


def parse_finish(value: object, material: Material) -> Finish:
    """Finish from its name (``auto`` picks glass for glass and matte otherwise).

    Raises:
        ProjectError: For an unknown name.
    """
    match value:
        case "auto":
            return default_finish(material)
        case "matte":
            return Finish.matte()
        case "metal":
            return Finish.metal()
        case "glass":
            return Finish.glass()
        case "emissive":
            return Finish.emissive()
    raise ProjectError(f"unknown finish {value!r}; finishes: {', '.join(FINISHES)}")


def _rgb(value: object) -> RGB:
    if (
        not isinstance(value, tuple | list)
        or len(value) != 3
        or any(isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= 255 for c in value)
    ):
        raise ProjectError(f"rgb must be three integers 0-255, got {value!r}")
    return (value[0], value[1], value[2])


def _bool(value: object, what: str) -> bool:
    if not isinstance(value, bool):
        raise ProjectError(f"{what} must be true or false, got {value!r}")
    return value


@dataclass
class Project:
    """A modelling project: the single source of truth of a model (decision D-004).

    Attributes:
        name: Project name.
        kind: ``"vehicle"`` or ``"prop"``.
        description: Free text.
        colors: Named colors, by name.
        parts: Parts in creation order (also the order in the ``.vox`` file).
        anchors: Named points (continuous model-frame voxel coordinates).
        handling: Driving preset of a vehicle (``buildup.teardown.handling``).
    """

    name: str
    kind: Kind
    description: str = ""
    colors: dict[str, Color] = field(default_factory=dict)
    parts: dict[str, Part] = field(default_factory=dict)
    anchors: dict[str, Point] = field(default_factory=dict)
    handling: str = DEFAULT_HANDLING

    def set_handling(self, preset: object) -> None:
        """Choose the driving preset written on the skeleton's ``vehicle`` element.

        Raises:
            ProjectError: Not a vehicle, or an unknown preset (the message lists them).
        """
        if self.kind != "vehicle":
            raise ProjectError("only vehicle projects have a handling preset")
        if not isinstance(preset, str) or preset not in HANDLING:
            raise ProjectError(f"unknown handling {preset!r}; presets: {', '.join(HANDLING)}")
        self.handling = preset

    # --- Colors ----------------------------------------------------------------------------

    def define_color(self, name: str, material: str, rgb: object, finish: str = "auto") -> Color:
        """Create a named color, or change the color and finish of an existing one.

        Changing an existing color repaints every voxel that uses it (they share its palette
        index). Its material cannot change: define a new color instead.

        Raises:
            ProjectError: Bad name, material or finish; material change; no free palette slot
                left for the material.
            PaletteError: If ``rgb`` is not three integers 0-255.
        """
        name = check_name(name, "color")
        chosen = parse_material(material)
        entry = PaletteEntry(chosen, _rgb(rgb), parse_finish(finish, chosen))
        existing = self.colors.get(name)
        if existing is not None:
            if existing.material is not chosen:
                raise ProjectError(
                    f"color {name!r} is {existing.material.value}; its material cannot change "
                    "(voxels using it would change material): define a new color for "
                    f"{chosen.value}"
                )
            index = existing.index
        else:
            used = {c.index for c in self.colors.values()}
            free = [i for i in MATERIAL_INDICES[chosen] if i not in used]
            if not free:
                same = [c.name for c in self.colors.values() if c.material is chosen]
                raise ProjectError(
                    f"no palette slot left for {chosen.value}: its {len(MATERIAL_INDICES[chosen])} "
                    f"slots are used by {', '.join(same)}; reuse or redefine one of them"
                )
            index = free[0]
        color = Color(name, index, chosen, entry.color, entry.finish)
        self.colors[name] = color
        return color

    def color(self, name: object) -> Color:
        """The color called ``name``.

        Raises:
            ProjectError: If there is no such color (the message lists the colors).
        """
        if isinstance(name, str) and name in self.colors:
            return self.colors[name]
        known = ", ".join(self.colors) or "none yet, use define_color"
        raise ProjectError(f"unknown color {name!r}; colors: {known}")

    def palette(self) -> Palette:
        """Palette with one entry per color."""
        palette = Palette()
        for c in self.colors.values():
            palette.set_entry(c.index, PaletteEntry(c.material, c.rgb, c.finish))
        return palette

    def color_names(self) -> dict[int, str]:
        """Color name of each used palette index."""
        return {c.index: c.name for c in self.colors.values()}

    # --- Parts -----------------------------------------------------------------------------

    def part(self, name: object) -> Part:
        """The part called ``name``.

        Raises:
            ProjectError: If there is no such part (the message lists the parts).
        """
        if isinstance(name, str) and name in self.parts:
            return self.parts[name]
        known = ", ".join(self.parts) or "none yet, use add_part"
        raise ProjectError(f"unknown part {name!r}; parts: {known}")

    def _check_new_part(self, name: str, count: int = 1) -> str:
        name = check_name(name, "part")
        if name in self.parts:
            raise ProjectError(f"a part called {name!r} already exists")
        if len(self.parts) + count > MAX_PARTS:
            raise ProjectError(f"a project holds at most {MAX_PARTS} parts")
        return name

    def add_part(self, name: str) -> Part:
        """Add an empty body part.

        Raises:
            ProjectError: Bad or duplicate name, too many parts.
        """
        part = Part(self._check_new_part(name))
        self.parts[part.name] = part
        return part

    def remove_part(self, name: str) -> None:
        """Delete a part and its voxels.

        Raises:
            ProjectError: If there is no such part.
        """
        del self.parts[self.part(name).name]

    def draw(self, part_name: str, shape: Shape, mode: object, color: str | None) -> int:
        """Apply a shape to a part.

        Args:
            part_name: Target part.
            shape: Shape in the model frame.
            mode: ``"add"`` fills the shape with ``color`` (replacing what is there),
                ``"paint"`` recolors the part's existing voxels inside the shape, ``"carve"``
                empties them.
            color: Color name, required for ``add`` and ``paint``.

        Returns:
            Number of voxels changed.

        Raises:
            ProjectError: Unknown part, color or mode, missing color, shape outside model space.
        """
        part = self.part(part_name)
        if mode not in EDIT_MODES:
            raise ProjectError(f"mode must be one of {', '.join(EDIT_MODES)}, got {mode!r}")
        index = 0
        if mode != "carve":
            if color is None:
                raise ProjectError(f"mode {mode!r} needs a color")
            index = self.color(color).index
        clipped = clip_to_world(shape.start, shape.end)
        if clipped is None:
            raise ProjectError(
                f"the shape ({shape.start} to {shape.end}) is outside model space: coordinates "
                f"must be from {WORLD_MIN} to {WORLD_MAX - 1} voxels on every axis"
            )
        lo, hi = clipped
        if mode == "add":
            part.grow(lo, hi)
        current = part.bounds()
        if current is None:
            return 0
        lo = (max(lo[0], current[0][0]), max(lo[1], current[0][1]), max(lo[2], current[0][2]))
        hi = (min(hi[0], current[1][0]), min(hi[1], current[1][1]), min(hi[2], current[1][2]))
        if any(lo[i] >= hi[i] for i in range(3)):
            return 0
        assert part.grid is not None  # bounds() is not None
        size = (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
        mask = shape.mask(lo, size)
        o = part.origin
        window = part.grid[
            lo[0] - o[0] : hi[0] - o[0], lo[1] - o[1] : hi[1] - o[1], lo[2] - o[2] : hi[2] - o[2]
        ]
        if mode != "add":
            mask &= window != EMPTY
        changed = int(np.count_nonzero(mask & (window != index)))
        window[mask] = index
        part.trim()
        return changed

    def mirror(self, part_name: str, keep: object, plane_x: object = 0) -> int:
        """Make a part symmetric across the plane ``X = plane_x``.

        The ``keep`` side (``"left"``: X below the plane, ``"right"``: above) is copied, mirrored,
        onto the other side, replacing what was there. Voxels centered on the plane stay.

        Returns:
            The part's voxel count afterwards.

        Raises:
            ProjectError: Unknown, empty or wheel part, bad ``keep``, ``plane_x`` not a multiple
                of 0.5, nothing on the kept side, result outside model space.
        """
        part = self.part(part_name)
        if keep not in ("left", "right"):
            raise ProjectError(f"keep must be 'left' or 'right', got {keep!r}")
        twice = as_number(plane_x, "plane_x") * 2
        if not twice.is_integer():
            raise ProjectError(f"plane_x must be a whole or half voxel, got {plane_x!r}")
        p2 = int(twice)
        if part.grid is None:
            raise ProjectError(f"part {part.name!r} is empty")
        if part.wheel is not None:
            raise ProjectError(
                f"{part.name!r} is a wheel: mirroring would not move its axle; mirror body parts"
            )
        cells = np.argwhere(part.grid != EMPTY)
        values = part.grid[tuple(cells.T)]
        cells += np.array(part.origin)
        doubled_centers = 2 * cells[:, 0] + 1
        kept = doubled_centers <= p2 if keep == "left" else doubled_centers >= p2
        cells, values = cells[kept], values[kept]
        if len(cells) == 0:
            other = "right" if keep == "left" else "left"
            raise ProjectError(
                f"part {part.name!r} has no voxels on the {keep} side of X = {twice / 2:g}; "
                f"nothing to copy (did you mean keep='{other}'?)"
            )
        images = cells.copy()
        images[:, 0] = p2 - 1 - cells[:, 0]
        cells = np.concatenate([cells, images])
        values = np.concatenate([values, values])
        lo, hi = cells.min(axis=0), cells.max(axis=0) + 1
        if lo.min() < WORLD_MIN or hi.max() > WORLD_MAX:
            raise ProjectError(
                f"the mirrored part would leave model space ({WORLD_MIN} to {WORLD_MAX - 1} voxels)"
            )
        grid = np.zeros(tuple(int(v) for v in hi - lo), dtype=np.uint8)
        grid[tuple((cells - lo).T)] = values
        part.grid = grid
        part.origin = (int(lo[0]), int(lo[1]), int(lo[2]))
        return part.voxels

    def hollow(self, part_name: str, thickness: object = 1) -> int:
        """Empty the inside of a part, keeping a shell ``thickness`` voxels thick.

        Returns:
            Number of voxels removed.

        Raises:
            ProjectError: Unknown or empty part.
            VoxcoreError: If ``thickness`` is not an integer of at least 1.
        """
        part = self.part(part_name)
        if part.grid is None:
            raise ProjectError(f"part {part.name!r} is empty")
        before = part.voxels
        part.grid = hollow(part.grid, as_int(thickness, "thickness", minimum=1))
        part.trim()
        return before - part.voxels

    def move(self, part_name: str, offset: object) -> None:
        """Shift a part (and its wheel axle) by ``offset`` voxels.

        Raises:
            ProjectError: Unknown or empty part, result outside model space.
        """
        part = self.part(part_name)
        dx, dy, dz = as_vec3(offset, "offset")
        bounds = part.bounds()
        if bounds is None:
            raise ProjectError(f"part {part.name!r} is empty")
        start, end = bounds
        if min(start[0] + dx, start[1] + dy, start[2] + dz) < WORLD_MIN or (
            max(end[0] + dx, end[1] + dy, end[2] + dz) > WORLD_MAX
        ):
            raise ProjectError(
                f"the moved part would leave model space ({WORLD_MIN} to {WORLD_MAX - 1} voxels)"
            )
        part.origin = (start[0] + dx, start[1] + dy, start[2] + dz)
        if part.wheel is not None:
            ax, ay, az = part.wheel.axle
            part.wheel = WheelInfo(
                part.wheel.position, (ax + dx, ay + dy, az + dz), part.wheel.steer, part.wheel.drive
            )

    # --- Wheels ----------------------------------------------------------------------------

    def add_wheels(
        self, axles: Sequence[Axle], layout: WheelLayout, tire: str, rim: str | None = None
    ) -> list[Part]:
        """Add two wheels (left and right) per axle.

        Wheels are cylinders along X. The left wheel spans ``-inner_x - width`` to ``-inner_x``
        on X, the right one ``inner_x`` to ``inner_x + width`` (see ``WheelLayout``). With a
        ``rim`` color, the tire is a ring ``max(1, diameter // 5)`` voxels thick around it.

        Returns:
            The new wheel parts, named ``wheel_<position>`` (``wheel_fl``, ``wheel_fr``...).

        Raises:
            ProjectError: Not a vehicle, bad sizes, overlapping axles, unknown colors, name
                collisions, too many parts, wheels outside model space.
        """
        if self.kind != "vehicle":
            raise ProjectError("only vehicle projects have wheels")
        if not 1 <= len(axles) <= MAX_AXLES:
            raise ProjectError(f"give 1 to {MAX_AXLES} axles, got {len(axles)}")
        d = as_int(layout.diameter, "diameter", minimum=MIN_WHEEL_DIAMETER)
        if d % 2 or d > MAX_WHEEL_DIAMETER:
            raise ProjectError(
                f"diameter must be an even number of voxels from {MIN_WHEEL_DIAMETER} to "
                f"{MAX_WHEEL_DIAMETER}, got {d}"
            )
        w = as_int(layout.width, "width", minimum=1)
        if w > MAX_WHEEL_WIDTH:
            raise ProjectError(f"width must be at most {MAX_WHEEL_WIDTH} voxels, got {w}")
        gap = as_int(layout.inner_x, "inner_x", minimum=0)
        height = d // 2 if layout.axle_height is None else as_int(layout.axle_height, "axle_height")
        tire_index = self.color(tire).index
        rim_index = self.color(rim).index if rim is not None else tire_index
        for a in axles:
            as_int(a.z, "axle z")
            _bool(a.steer, "steer")
            _bool(a.drive, "drive")
        ordered = sorted(axles, key=lambda a: a.z)
        for front, back in pairwise(ordered):
            if back.z - front.z < d:
                raise ProjectError(
                    f"axles at z={front.z} and z={back.z} are closer than the wheel diameter {d}"
                )
        names = _AXLE_NAMES[len(ordered)]
        planned: list[tuple[str, int, Axle]] = []
        for axle, along in zip(ordered, names, strict=True):
            planned.append((f"{along}l", -1, axle))
            planned.append((f"{along}r", 1, axle))
        for position, _, _ in planned:
            self._check_new_part(f"wheel_{position}", len(planned))
        tire_thickness = max(1, d // 5)
        created: list[Part] = []
        for position, side, axle in planned:
            x0 = -gap - w if side < 0 else gap
            start = (x0, height - d // 2, axle.z - d // 2)
            end = (x0 + w, height + d // 2, axle.z + d // 2)
            if clip_to_world(start, end) != (start, end):
                raise ProjectError(f"wheel {position} would be outside model space")
            part = Part(f"wheel_{position}", "wheel")
            part.wheel = WheelInfo(position, (x0 + w / 2, height, axle.z), axle.steer, axle.drive)
            created.append(part)
            center = (float(height), float(axle.z))
            outer = cylinder_shape("x", center, d / 2, (x0, x0 + w))
            inner = cylinder_shape("x", center, d / 2 - tire_thickness, (x0, x0 + w))
            self.parts[part.name] = part
            self.draw(part.name, outer, "add", tire)
            if rim_index != tire_index:
                self.draw(part.name, inner, "paint", rim)
        return created

    # --- Anchors ---------------------------------------------------------------------------

    def set_anchor(self, name: str, position: object) -> None:
        """Create, move or (with ``position=None``) delete a named point.

        Raises:
            ProjectError: Bad name, unknown anchor to delete, too many anchors, point outside
                model space.
        """
        name = check_name(name, "anchor")
        if position is None:
            if name not in self.anchors:
                known = ", ".join(self.anchors) or "none"
                raise ProjectError(f"unknown anchor {name!r}; anchors: {known}")
            del self.anchors[name]
            return
        point = as_float3(position, "position")
        if not inside_world(point):
            raise ProjectError(
                f"anchor {name!r} at {point} is outside model space "
                f"({WORLD_MIN} to {WORLD_MAX} voxels)"
            )
        if name not in self.anchors and len(self.anchors) >= MAX_ANCHORS:
            raise ProjectError(f"a project holds at most {MAX_ANCHORS} anchors")
        self.anchors[name] = point

    # --- Views -----------------------------------------------------------------------------

    def composed(self, part_name: str | None = None) -> tuple[Grid, Vec3] | None:
        """One grid with every part (or only ``part_name``) and its origin; ``None`` if empty.

        Raises:
            ProjectError: Unknown part.
        """
        parts = [self.part(part_name)] if part_name is not None else list(self.parts.values())
        placed = [(p.grid, p.origin) for p in parts if p.grid is not None]
        if not placed:
            return None
        return compose(placed)

    def markers(self) -> list[tuple[str, Point]]:
        """Labelled points to show on previews: wheel axles and anchors."""
        points = [
            (f"wheel {p.wheel.position}", p.wheel.axle)
            for p in self.parts.values()
            if p.wheel is not None
        ]
        points += list(self.anchors.items())
        return points
