"""Checks against the official files of a local Teardown installation (read only, never copied)."""

from pathlib import Path

import pytest

from buildup.palette import palette_row_names
from buildup.voxio import TeardownCompressedError, read_vox

pytestmark = pytest.mark.game


def test_material_table_matches_the_official_palette(teardown_dir: Path) -> None:
    document = read_vox(teardown_dir / "data" / "built-in" / "palette.vox")
    assert document.notes == palette_row_names()


def test_official_car_object_names(teardown_dir: Path) -> None:
    path = teardown_dir / "mods" / "assetpack" / "assets" / "vehicles" / "land" / "salooncar.vox"
    if not path.is_file():
        pytest.skip("assetpack not installed")
    document = read_vox(path)
    names = {i.name for i in document.instances}
    assert names == {"body", "wheel_fl", "wheel_fr", "wheel_bl", "wheel_br"}
    body = next(i for i in document.instances if i.name == "body")
    assert document.models[body.model_index].shape == (21, 44, 13)


@pytest.mark.slow
def test_every_official_vox_file_can_be_read(teardown_dir: Path) -> None:
    paths = [
        path
        for folder in ("data", "mods", "dlcs")
        for path in sorted((teardown_dir / folder).rglob("*.vox"))
    ]
    assert paths, "no .vox files found"
    failures: list[str] = []
    compressed: list[Path] = []
    for path in paths:
        try:
            document = read_vox(path)
        except TeardownCompressedError:
            compressed.append(path)  # known, explicitly refused format (TEARDOWN_REFERENCE.md §2)
            continue
        except Exception as error:  # collect every failure and report them together
            failures.append(f"{path.relative_to(teardown_dir)}: {error}")
            continue
        if document.version not in (150, 200):
            failures.append(
                f"{path.relative_to(teardown_dir)}: unexpected version {document.version}"
            )
    assert not failures, f"{len(failures)}/{len(paths)} files failed:\n" + "\n".join(failures[:20])
    assert len(compressed) < len(paths) // 10, "TDCZ is expected to be rare"
