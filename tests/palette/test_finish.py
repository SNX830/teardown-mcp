import pytest

from buildup.palette import Finish, FinishKind

EXPECTED_KEYS = {
    "_type",
    "_weight",
    "_rough",
    "_spec",
    "_spec_p",
    "_ior",
    "_att",
    "_g0",
    "_g1",
    "_gw",
    "_flux",
    "_ldr",
}


@pytest.mark.parametrize(
    "finish",
    [Finish.matte(), Finish.metal(), Finish.glass(), Finish.emissive()],
)
def test_matl_has_the_official_version_150_keys(finish: Finish) -> None:
    assert set(finish.to_matl()) == EXPECTED_KEYS


def test_matte() -> None:
    assert Finish.matte().kind is FinishKind.MATTE
    assert Finish.matte().to_matl()["_type"] == "_diffuse"


def test_metal_writes_metallic_and_roughness() -> None:
    matl = Finish.metal(roughness=0.25, metallic=0.1).to_matl()
    assert matl["_type"] == "_metal"
    assert matl["_weight"] == "0.1"
    assert matl["_rough"] == "0.25"


def test_glass_uses_the_official_window_value() -> None:
    assert Finish.glass().to_matl()["_weight"] == "0.5"
    assert Finish.glass().to_matl()["_type"] == "_glass"


def test_emissive_writes_emission_and_power() -> None:
    matl = Finish.emissive(emission=0.46, power=3).to_matl()
    assert matl["_type"] == "_emit"
    assert matl["_weight"] == "0.46"
    assert matl["_flux"] == "3"


@pytest.mark.parametrize(
    "kwargs",
    [{"roughness": 1.5}, {"metallic": -0.1}, {"emission": 2.0}, {"power": 5.0}, {"power": -1.0}],
)
def test_out_of_range_values_are_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="must be between"):
        Finish(**kwargs)  # type: ignore[arg-type]  # kwargs typed loosely on purpose


def test_type_is_the_first_key_like_official_files() -> None:
    assert next(iter(Finish.metal().to_matl())) == "_type"
