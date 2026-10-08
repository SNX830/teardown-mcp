import numpy as np
import pytest

from buildup.palette import (
    MATERIAL_INDICES,
    Finish,
    Material,
    Palette,
    PaletteEntry,
    PaletteError,
    PaletteFullError,
)

RED = (200, 30, 30)


def test_allocates_inside_the_material_range() -> None:
    palette = Palette()
    assert palette.index_for(Material.WEAK_METAL, RED) == 121
    assert palette.index_for(Material.WOOD, RED) == 57
    assert palette.index_for(Material.WEAK_METAL, (0, 0, 0)) == 122


def test_identical_entries_are_reused() -> None:
    palette = Palette()
    first = palette.index_for(Material.BRICK, RED)
    assert palette.index_for(Material.BRICK, RED) == first
    assert palette.index_for(Material.BRICK, RED, Finish.metal()) != first
    assert len(palette.entries) == 2


def test_default_finish_depends_on_material() -> None:
    palette = Palette()
    glass = palette.entries[palette.index_for(Material.GLASS, (90, 90, 100))]
    plaster = palette.entries[palette.index_for(Material.PLASTER, RED)]
    assert glass.finish == Finish.glass()
    assert plaster.finish == Finish.matte()


def test_full_material_raises() -> None:
    palette = Palette()
    for shade in range(len(MATERIAL_INDICES[Material.GLASS])):
        palette.index_for(Material.GLASS, (shade, shade, shade))
    assert palette.free_slots(Material.GLASS) == 0
    with pytest.raises(PaletteFullError, match="glass"):
        palette.index_for(Material.GLASS, (255, 255, 255))


@pytest.mark.parametrize(
    "color", [(256, 0, 0), (-1, 0, 0), (1, 2), (1, 2, 3, 4), (1.5, 2, 3), (True, 0, 0)]
)
def test_invalid_colors_are_rejected(color: tuple[object, ...]) -> None:
    with pytest.raises(PaletteError, match="color"):
        Palette().index_for(Material.WOOD, color)  # type: ignore[arg-type]  # invalid on purpose


def test_set_entry_checks_the_material_range() -> None:
    palette = Palette()
    palette.set_entry(60, PaletteEntry(Material.WOOD, RED, Finish.matte()))
    assert palette.entries[60].material is Material.WOOD
    with pytest.raises(PaletteError, match="not a wood index"):
        palette.set_entry(121, PaletteEntry(Material.WOOD, RED, Finish.matte()))
    with pytest.raises(PaletteError):
        palette.set_entry(0, PaletteEntry(Material.WOOD, RED, Finish.matte()))


def test_entries_view_is_read_only() -> None:
    palette = Palette()
    palette.index_for(Material.WOOD, RED)
    with pytest.raises(TypeError):
        palette.entries[1] = PaletteEntry(Material.GLASS, RED, Finish.glass())  # type: ignore[index]  # read-only


def test_rgba_table_layout() -> None:
    palette = Palette()
    index = palette.index_for(Material.HARD_METAL, (10, 20, 30))
    table = palette.rgba()
    assert table.shape == (256, 4)
    assert table.dtype == np.uint8
    assert tuple(table[0]) == (0, 0, 0, 0)
    assert tuple(table[index]) == (10, 20, 30, 255)
    assert tuple(table[1]) == (128, 128, 128, 255)


def test_matl_of_used_and_unused_slots() -> None:
    palette = Palette()
    index = palette.index_for(Material.HARD_METAL, RED, Finish.emissive(power=3))
    assert palette.matl(index)["_type"] == "_emit"
    assert palette.matl(200)["_type"] == "_diffuse"


def test_see_through_is_glass_material_with_glass_finish_only() -> None:
    palette = Palette()
    window = palette.index_for(Material.GLASS, (150, 200, 230))
    lamp = palette.index_for(Material.GLASS, (255, 250, 220), Finish.emissive())
    shiny = palette.index_for(Material.WEAK_METAL, (150, 200, 230), Finish.glass())
    paint = palette.index_for(Material.WEAK_METAL, RED)
    assert palette.see_through() == {window}
    assert {lamp, shiny, paint}.isdisjoint(palette.see_through())
