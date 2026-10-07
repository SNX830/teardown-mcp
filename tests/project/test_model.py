from typing import Any

import numpy as np
import pytest

from buildup.palette import FinishKind, Material, PaletteError
from buildup.project import (
    MAX_PARTS,
    Axle,
    Part,
    Project,
    ProjectError,
    WheelLayout,
    box_shape,
    cylinder_shape,
    parse_finish,
    parse_material,
)
from buildup.project.shapes import WORLD_MAX, WORLD_MIN
from buildup.voxcore import VoxcoreError

NOT_A_BOOL: Any = 1  # what a JSON client could send


@pytest.fixture
def car() -> Project:
    project = Project("car", "vehicle")
    project.define_color("paint", "weak metal", (200, 30, 30))
    project.define_color("glass", "glass", (100, 150, 200))
    project.define_color("tire", "plastic", (20, 20, 20))
    project.define_color("rim", "weak_metal", (180, 180, 180), "metal")
    project.add_part("body")
    return project


def cells(part: Part) -> set[tuple[int, int, int]]:
    """Model-frame cells of a part's voxels."""
    assert part.grid is not None
    ox, oy, oz = part.origin
    return {(int(x) + ox, int(y) + oy, int(z) + oz) for x, y, z in np.argwhere(part.grid)}


# --- Colors --------------------------------------------------------------------------------


def test_colors_get_indices_in_their_material_range(car: Project) -> None:
    assert [c.index for c in car.colors.values()] == [121, 1, 153, 122]
    assert car.colors["glass"].finish.kind is FinishKind.GLASS  # auto finish
    assert car.colors["paint"].finish.kind is FinishKind.MATTE
    assert car.colors["rim"].material is Material.WEAK_METAL
    assert car.color_names() == {121: "paint", 1: "glass", 153: "tire", 122: "rim"}
    palette = car.palette()
    assert palette.entries[122].color == (180, 180, 180)
    assert palette.entries[122].finish.kind is FinishKind.METAL


def test_two_names_with_the_same_look_get_two_indices(car: Project) -> None:
    twin = car.define_color("paint2", "weak metal", (200, 30, 30))
    assert twin.index == 123


def test_redefining_a_color_keeps_its_index(car: Project) -> None:
    changed = car.define_color("paint", "weak metal", (10, 20, 200), "emissive")
    assert changed.index == 121
    assert changed.rgb == (10, 20, 200)
    assert changed.finish.kind is FinishKind.EMISSIVE
    with pytest.raises(ProjectError, match="material cannot change"):
        car.define_color("paint", "wood", (10, 20, 200))


def test_full_material_is_reported() -> None:
    project = Project("p", "prop")
    for i in range(8):
        project.define_color(f"g{i}", "glass", (i, 0, 0))
    with pytest.raises(ProjectError, match="no palette slot left for glass: its 8 slots"):
        project.define_color("g8", "glass", (9, 0, 0))


@pytest.mark.parametrize(
    ("rgb", "finish", "material", "message"),
    [
        ((1, 2), "auto", "wood", "rgb must be"),
        ((1, 2, 256), "auto", "wood", "rgb must be"),
        ((1, 2, True), "auto", "wood", "rgb must be"),
        ((1, 2, 3), "shiny", "wood", "unknown finish"),
        ((1, 2, 3), "auto", "steel", "unknown material 'steel'; materials: glass"),
    ],
)
def test_bad_colors(car: Project, rgb: object, finish: str, material: str, message: str) -> None:
    with pytest.raises(ProjectError, match=message):
        car.define_color("c", material, rgb, finish)


def test_parsers() -> None:
    assert parse_material(" Heavy_Metal ") is Material.HEAVY_METAL
    with pytest.raises(ProjectError):
        parse_material(3)
    assert parse_finish("auto", Material.GLASS).kind is FinishKind.GLASS
    assert parse_finish("glass", Material.WOOD).kind is FinishKind.GLASS
    assert parse_finish("metal", Material.WOOD).kind is FinishKind.METAL


def test_unknown_color_lists_colors(car: Project) -> None:
    with pytest.raises(ProjectError, match="unknown color 'red'; colors: paint, glass, tire, rim"):
        car.color("red")
    with pytest.raises(ProjectError, match="none yet"):
        Project("p", "prop").color("red")


def test_palette_error_is_a_value_error() -> None:
    assert issubclass(PaletteError, ValueError)


# --- Drawing -------------------------------------------------------------------------------


def test_add_grows_the_part(car: Project) -> None:
    assert car.draw("body", box_shape((-8, 3, -20), (8, 9, 20)), "add", "paint") == 16 * 6 * 40
    body = car.part("body")
    assert body.bounds() == ((-8, 3, -20), (8, 9, 20))
    assert car.draw("body", box_shape((-6, 9, -5), (6, 14, 10)), "add", "paint") == 12 * 5 * 15
    assert body.bounds() == ((-8, 3, -20), (8, 14, 20))
    assert body.voxels == 16 * 6 * 40 + 12 * 5 * 15
    # Adding again with the same color changes nothing; another color replaces.
    assert car.draw("body", box_shape((-6, 9, -5), (6, 14, 10)), "add", "paint") == 0
    assert car.draw("body", box_shape((-6, 13, -5), (6, 14, 10)), "add", "glass") == 12 * 15


def test_paint_changes_only_existing_voxels(car: Project) -> None:
    car.draw("body", box_shape((0, 0, 0), (4, 4, 4)), "add", "paint")
    changed = car.draw("body", box_shape((2, 2, 2), (10, 10, 10)), "paint", "glass")
    assert changed == 8
    body = car.part("body")
    assert body.bounds() == ((0, 0, 0), (4, 4, 4))  # paint never grows a part
    assert body.grid is not None
    assert int(np.count_nonzero(body.grid == 1)) == 8
    assert car.draw("body", box_shape((20, 20, 20), (30, 30, 30)), "paint", "glass") == 0


def test_carve_shrinks_and_empties(car: Project) -> None:
    car.draw("body", box_shape((0, 0, 0), (4, 4, 4)), "add", "paint")
    assert car.draw("body", box_shape((0, 0, 2), (4, 4, 4)), "carve", None) == 32
    body = car.part("body")
    assert body.bounds() == ((0, 0, 0), (4, 4, 2))
    assert car.draw("body", box_shape((-50, -50, -50), (50, 50, 50)), "carve", None) == 32
    assert body.grid is None
    assert body.bounds() is None
    assert car.draw("body", box_shape((0, 0, 0), (1, 1, 1)), "carve", None) == 0


def test_cylinder_drawn_at_a_negative_position(car: Project) -> None:
    car.draw("body", cylinder_shape("x", (4, -13), 4, (-10, -8)), "add", "tire")
    body = car.part("body")
    assert body.bounds() == ((-10, 0, -17), (-8, 8, -9))
    assert body.voxels == 2 * 52  # a disc of radius 4 has 52 voxel centers inside


def test_draw_errors(car: Project) -> None:
    shape = box_shape((0, 0, 0), (1, 1, 1))
    with pytest.raises(ProjectError, match="mode must be one of add, paint, carve"):
        car.draw("body", shape, "erase", None)
    with pytest.raises(ProjectError, match="needs a color"):
        car.draw("body", shape, "add", None)
    with pytest.raises(ProjectError, match="unknown part 'bdy'; parts: body"):
        car.draw("bdy", shape, "add", "paint")
    with pytest.raises(ProjectError, match="outside model space"):
        car.draw("body", box_shape((200, 0, 0), (201, 1, 1)), "add", "paint")


def test_shapes_are_clipped_to_model_space(car: Project) -> None:
    car.draw("body", box_shape((120, 0, 0), (140, 1, 1)), "add", "paint")
    assert car.part("body").bounds() == ((120, 0, 0), (WORLD_MAX, 1, 1))


# --- Parts ---------------------------------------------------------------------------------


def test_part_management(car: Project) -> None:
    with pytest.raises(ProjectError, match="already exists"):
        car.add_part("body")
    car.add_part("roof")
    assert list(car.parts) == ["body", "roof"]
    car.remove_part("roof")
    assert list(car.parts) == ["body"]
    with pytest.raises(ProjectError, match="none yet"):
        Project("p", "prop").part("x")
    for i in range(MAX_PARTS - 1):
        car.add_part(f"p{i}")
    with pytest.raises(ProjectError, match=f"at most {MAX_PARTS} parts"):
        car.add_part("one_more")


def test_part_grow_keeps_voxels() -> None:
    part = Part("p", grid=np.ones((1, 1, 1), np.uint8), origin=(5, 5, 5))
    part.grow((5, 5, 5), (6, 6, 6))  # already covered: no change
    assert part.grid is not None
    assert part.grid.shape == (1, 1, 1)
    part.grow((3, 5, 5), (4, 7, 6))
    assert part.origin == (3, 5, 5)
    assert part.grid.shape == (3, 2, 1)
    assert cells(part) == {(5, 5, 5)}


# --- Mirror, hollow, move ------------------------------------------------------------------


def test_mirror_about_the_center_line(car: Project) -> None:
    car.draw("body", box_shape((-8, 0, 0), (0, 2, 4)), "add", "paint")
    car.draw("body", box_shape((-6, 2, 0), (-4, 3, 1)), "add", "glass")  # left mirror
    car.draw("body", box_shape((3, 0, 0), (5, 1, 1)), "add", "glass")  # discarded right side
    voxels = car.mirror("body", "left")
    body = car.part("body")
    assert body.bounds() == ((-8, 0, 0), (8, 3, 4))
    assert voxels == 2 * (8 * 2 * 4 + 2)
    assert (4, 2, 0) in cells(body)
    assert (5, 2, 0) in cells(body)
    assert body.grid is not None
    # Glass mirror on the right at x 4..6, and the right-side glass block was replaced by paint.
    assert body.grid[3 + 8, 0, 0] == 121


def test_mirror_keeps_the_right_side_and_odd_planes(car: Project) -> None:
    car.draw("body", box_shape((0, 0, 0), (3, 1, 1)), "add", "paint")  # cells 0, 1, 2
    car.mirror("body", "right", 0.5)  # plane through the center of cell 0
    assert cells(car.part("body")) == {(x, 0, 0) for x in range(-2, 3)}
    car.mirror("body", "left", 0.5)
    assert cells(car.part("body")) == {(x, 0, 0) for x in range(-2, 3)}
    with pytest.raises(ProjectError, match=r"no voxels on the left side of X = -2.*keep='right'"):
        car.mirror("body", "left", -2)  # nothing below x = -2: refused, the part is kept
    assert car.part("body").voxels == 5


def test_mirror_errors(car: Project) -> None:
    with pytest.raises(ProjectError, match="empty"):
        car.mirror("body", "left")
    car.draw("body", box_shape((-128, 0, 0), (-120, 1, 1)), "add", "paint")
    with pytest.raises(ProjectError, match="keep must be"):
        car.mirror("body", "up")
    with pytest.raises(ProjectError, match="whole or half voxel"):
        car.mirror("body", "left", 0.25)
    with pytest.raises(VoxcoreError, match="plane_x must be a number"):
        car.mirror("body", "left", "0")
    with pytest.raises(ProjectError, match="leave model space"):
        car.mirror("body", "left", 10)  # images reach x = 147
    (wheel, _) = car.add_wheels([Axle(0)], WheelLayout(8, 2, 8), "tire")
    with pytest.raises(ProjectError, match="is a wheel"):
        car.mirror(wheel.name, "left")


def test_hollow(car: Project) -> None:
    with pytest.raises(ProjectError, match="empty"):
        car.hollow("body")
    car.draw("body", box_shape((0, 0, 0), (6, 6, 6)), "add", "paint")
    assert car.hollow("body") == 4 * 4 * 4
    assert car.part("body").voxels == 6**3 - 4**3
    with pytest.raises(VoxcoreError, match="thickness"):
        car.hollow("body", 0)


def test_move(car: Project) -> None:
    with pytest.raises(ProjectError, match="empty"):
        car.move("body", (1, 0, 0))
    car.draw("body", box_shape((0, 0, 0), (2, 2, 2)), "add", "paint")
    car.move("body", (-3, 1, 120))
    assert car.part("body").bounds() == ((-3, 1, 120), (-1, 3, 122))
    with pytest.raises(ProjectError, match="leave model space"):
        car.move("body", (0, 0, 7))
    with pytest.raises(ProjectError, match="leave model space"):
        car.move("body", (-126, 0, 0))


# --- Wheels --------------------------------------------------------------------------------


def test_add_wheels(car: Project) -> None:
    layout = WheelLayout(diameter=8, width=2, inner_x=8)
    created = car.add_wheels([Axle(13, drive=True), Axle(-13, steer=True)], layout, "tire", "rim")
    assert [p.name for p in created] == ["wheel_fl", "wheel_fr", "wheel_bl", "wheel_br"]
    fl, fr, bl, br = created
    assert fl.wheel is not None
    assert fl.wheel.axle == (-9.0, 4.0, -13.0)
    assert fl.wheel.steer
    assert not fl.wheel.drive
    assert br.wheel is not None
    assert br.wheel.axle == (9.0, 4.0, 13.0)
    assert br.wheel.drive
    assert fl.bounds() == ((-10, 0, -17), (-8, 8, -9))
    assert fr.bounds() == ((8, 0, -17), (10, 8, -9))
    assert bl.bounds() == ((-10, 0, 9), (-8, 8, 17))
    assert fl.role == "wheel"
    # Rim: a disc of radius 4 - 1 = 3 (32 voxel centers) inside a tire ring.
    assert fl.grid is not None
    assert int(np.count_nonzero(fl.grid == 122)) == 2 * 32
    assert int(np.count_nonzero(fl.grid == 153)) == 2 * (52 - 32)
    assert car.markers()[:2] == [("wheel fl", (-9.0, 4.0, -13.0)), ("wheel fr", (9.0, 4.0, -13.0))]


@pytest.mark.parametrize(
    ("count", "names"),
    [
        (1, ["ml", "mr"]),
        (3, ["fl", "fr", "ml", "mr", "bl", "br"]),
        (4, ["fl", "fr", "m1l", "m1r", "m2l", "m2r", "bl", "br"]),
    ],
)
def test_wheel_names(car: Project, count: int, names: list[str]) -> None:
    axles = [Axle(20 * i) for i in range(count)]
    created = car.add_wheels(axles, WheelLayout(6, 3, 7, axle_height=5), "tire")
    assert [p.wheel.position for p in created if p.wheel] == names
    first = created[0]
    assert first.wheel is not None
    assert first.wheel.axle == (-8.5, 5.0, 0.0)  # odd width: half-voxel axle on X
    assert first.bounds() == ((-10, 2, -3), (-7, 8, 3))
    assert first.grid is not None
    assert set(np.unique(first.grid)) == {0, 153}  # no rim color: tire only


@pytest.mark.parametrize(
    ("axles", "layout", "message"),
    [
        ([], WheelLayout(8, 2, 8), "1 to 4 axles"),
        ([Axle(0)] * 5, WheelLayout(8, 2, 8), "1 to 4 axles"),
        ([Axle(0)], WheelLayout(7, 2, 8), "even number"),
        ([Axle(0)], WheelLayout(66, 2, 8), "even number"),
        ([Axle(0)], WheelLayout(2, 2, 8), "diameter must be an integer >= 4"),
        ([Axle(0)], WheelLayout(8, 40, 8), "width must be at most"),
        ([Axle(0)], WheelLayout(8, 2, -1), "inner_x"),
        ([Axle(0), Axle(7)], WheelLayout(8, 2, 8), "closer than the wheel diameter"),
        ([Axle(125)], WheelLayout(8, 2, 8), "outside model space"),
        ([Axle(0, steer=NOT_A_BOOL)], WheelLayout(8, 2, 8), "steer must be true or false"),
    ],
)
def test_wheel_errors(car: Project, axles: list[Axle], layout: WheelLayout, message: str) -> None:
    with pytest.raises((ProjectError, VoxcoreError), match=message):
        car.add_wheels(axles, layout, "tire")


def test_wheel_name_collisions_and_props(car: Project) -> None:
    car.add_wheels([Axle(0)], WheelLayout(8, 2, 8), "tire")
    with pytest.raises(ProjectError, match="'wheel_ml' already exists"):
        car.add_wheels([Axle(0)], WheelLayout(8, 2, 8), "tire")
    with pytest.raises(ProjectError, match="only vehicle projects"):
        Project("p", "prop").add_wheels([Axle(0)], WheelLayout(8, 2, 8), "tire")


def test_moving_a_wheel_moves_its_axle(car: Project) -> None:
    (left, _) = car.add_wheels([Axle(0)], WheelLayout(8, 2, 8), "tire")
    car.move(left.name, (-1, 2, 3))
    assert left.wheel is not None
    assert left.wheel.axle == (-10.0, 6.0, 3.0)


# --- Anchors and views ---------------------------------------------------------------------


def test_anchors(car: Project) -> None:
    car.set_anchor("player", (-4, 9, 2.5))
    assert car.anchors["player"] == (-4.0, 9.0, 2.5)
    car.set_anchor("player", (-3, 9, 2))
    assert car.markers() == [("player", (-3.0, 9.0, 2.0))]
    car.set_anchor("player", None)
    assert car.anchors == {}
    with pytest.raises(ProjectError, match="unknown anchor 'player'; anchors: none"):
        car.set_anchor("player", None)
    with pytest.raises(ProjectError, match="outside model space"):
        car.set_anchor("far", (0, 0, WORLD_MIN - 1))
    with pytest.raises(VoxcoreError, match="three numbers"):
        car.set_anchor("bad", (0, 0))
    for i in range(32):
        car.set_anchor(f"a{i}", (0, 0, 0))
    with pytest.raises(ProjectError, match="at most 32 anchors"):
        car.set_anchor("b", (0, 0, 0))


def test_composed(car: Project) -> None:
    assert car.composed() is None
    car.draw("body", box_shape((0, 0, 0), (2, 2, 2)), "add", "paint")
    car.add_part("roof")
    car.draw("roof", box_shape((1, 2, 0), (2, 3, 1)), "add", "glass")
    composed = car.composed()
    assert composed is not None
    grid, origin = composed
    assert origin == (0, 0, 0)
    assert grid.shape == (2, 3, 2)
    assert grid[1, 2, 0] == 1
    roof = car.composed("roof")
    assert roof is not None
    assert roof[1] == (1, 2, 0)
    assert roof[0].shape == (1, 1, 1)
