import pytest

from buildup.palette import MATERIAL_INDICES, Material, material_of_index, palette_row_names


def test_ranges_are_disjoint_and_sized_as_documented() -> None:
    seen: set[int] = set()
    for material, indices in MATERIAL_INDICES.items():
        assert not seen & set(indices), material
        seen |= set(indices)
        expected = (
            8 if material in {Material.GLASS, Material.HARD_METAL, Material.HARD_MASONRY} else 16
        )
        assert len(indices) == expected, material
    assert set(MATERIAL_INDICES) == set(Material)


@pytest.mark.parametrize(
    ("index", "material"),
    [
        (1, Material.GLASS),
        (8, Material.GLASS),
        (9, Material.GRASS),  # official documentation: "index 9 is always grass"
        (57, Material.WOOD),  # official documentation: wood is 57-72
        (72, Material.WOOD),
        (121, Material.WEAK_METAL),
        (176, Material.HARD_METAL),
        (184, Material.HARD_MASONRY),
        (225, Material.UNPHYSICAL),
        (240, Material.UNPHYSICAL),
    ],
)
def test_material_of_index(index: int, material: Material) -> None:
    assert material_of_index(index) is material


@pytest.mark.parametrize("index", [185, 224, 241, 255])
def test_reserved_indices_have_no_material(index: int) -> None:
    assert material_of_index(index) is None


@pytest.mark.parametrize("index", [0, 256, -1])
def test_material_of_index_rejects_out_of_range(index: int) -> None:
    with pytest.raises(ValueError, match="palette index"):
        material_of_index(index)


def test_row_names_follow_note_order() -> None:
    names = palette_row_names()
    assert len(names) == 32
    assert names[31] == "glass"  # last row = indices 1-8
    assert names[29:31] == ["grass", "grass"]
    assert names[23:25] == ["wood", "wood"]
    assert names[2:4] == ["unphysical", "unphysical"]
    assert names[0] == "reserved"
