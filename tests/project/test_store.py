import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import buildup.project.store as store_module
from buildup.palette import FinishKind
from buildup.project import (
    Axle,
    Project,
    ProjectError,
    ProjectFileError,
    ProjectStore,
    WheelLayout,
    box_shape,
)
from buildup.project.store import project_from_json, project_to_json


@pytest.fixture
def store(tmp_path: Path) -> ProjectStore:
    return ProjectStore(tmp_path / "workspace")


def _build(store: ProjectStore) -> None:
    store.create("car", "vehicle", "a test car")
    with store.edit("car", "colors") as p:
        p.define_color("paint", "weak metal", (200, 30, 30))
        p.define_color("lamp", "glass", (255, 255, 200), "emissive")
        p.define_color("tire", "plastic", (20, 20, 20))
    with store.edit("car", "body") as p:
        p.add_part("body")
        p.add_part("empty")
        p.draw("body", box_shape((-8, 3, -20), (8, 9, 20)), "add", "paint")
        p.draw("body", box_shape((-6, 5, -21), (-3, 7, -20)), "add", "lamp")
    with store.edit("car", "wheels") as p:
        p.add_wheels([Axle(-13, steer=True), Axle(13, drive=True)], WheelLayout(8, 3, 8), "tire")
        p.set_anchor("player", (-4, 9, 2.5))


def test_round_trip(store: ProjectStore) -> None:
    _build(store)
    p = store.load("car")
    assert (p.name, p.kind, p.description) == ("car", "vehicle", "a test car")
    assert list(p.colors) == ["paint", "lamp", "tire"]
    lamp = p.colors["lamp"]
    assert (lamp.index, lamp.rgb, lamp.finish.kind) == (1, (255, 255, 200), FinishKind.EMISSIVE)
    assert lamp.finish.power == 2.0
    assert list(p.parts) == ["body", "empty", "wheel_fl", "wheel_fr", "wheel_bl", "wheel_br"]
    assert p.parts["empty"].grid is None
    body = p.parts["body"]
    assert body.bounds() == ((-8, 3, -21), (8, 9, 20))
    assert body.voxels == 16 * 6 * 40 + 6
    wheel = p.parts["wheel_br"]
    assert wheel.role == "wheel"
    assert wheel.wheel is not None
    assert wheel.wheel.axle == (9.5, 4.0, 13.0)
    assert (wheel.wheel.position, wheel.wheel.steer, wheel.wheel.drive) == ("br", False, True)
    assert p.anchors == {"player": (-4.0, 9.0, 2.5)}
    # Grids come back identical.
    again = store.load("car")
    for name, part in p.parts.items():
        other = again.parts[name].grid
        if part.grid is None:
            assert other is None
        else:
            assert other is not None
            assert np.array_equal(part.grid, other)


def test_project_file_is_readable_json(store: ProjectStore) -> None:
    _build(store)
    data = json.loads((store.folder("car") / "project.json").read_text(encoding="utf-8"))
    assert data["format"] == 1
    assert [p["grid"] for p in data["parts"]] == [
        "arr_0",
        None,
        "arr_1",
        "arr_2",
        "arr_3",
        "arr_4",
    ]
    with np.load(store.folder("car") / "parts.npz", allow_pickle=False) as archive:
        assert sorted(archive.files) == ["arr_0", "arr_1", "arr_2", "arr_3", "arr_4"]


def test_a_part_may_be_called_like_a_numpy_argument(store: ProjectStore) -> None:
    store.create("p", "prop")
    with store.edit("p", "x") as p:
        p.define_color("c", "wood", (1, 2, 3))
        p.add_part("allow_pickle")
        p.draw("allow_pickle", box_shape((0, 0, 0), (1, 1, 1)), "add", "c")
    assert store.load("p").parts["allow_pickle"].voxels == 1


def test_failed_edit_saves_nothing(store: ProjectStore) -> None:
    _build(store)
    before = (store.folder("car") / "project.json").read_bytes()

    def broken_edit() -> None:
        with store.edit("car", "broken") as p:
            p.add_part("roof")
            p.draw("roof", box_shape((0, 0, 0), (1, 1, 1)), "add", "no_such_color")

    with pytest.raises(ProjectError, match="unknown color"):
        broken_edit()
    assert (store.folder("car") / "project.json").read_bytes() == before
    assert store.history("car") == ["colors", "body", "wheels"]


def test_undo(store: ProjectStore) -> None:
    _build(store)
    assert store.undo("car") == ["wheels"]
    p = store.load("car")
    assert list(p.parts) == ["body", "empty"]
    assert p.anchors == {}
    assert store.undo("car", 5) == ["body", "colors"]
    p = store.load("car")
    assert p.parts == {}
    assert p.colors == {}
    with pytest.raises(ProjectError, match="nothing to undo"):
        store.undo("car")
    with pytest.raises(ProjectError, match="steps must be at least 1"):
        store.undo("car", 0)


def test_history_is_limited(store: ProjectStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_module, "MAX_HISTORY", 3)
    store.create("p", "prop")
    for i in range(5):
        with store.edit("p", f"edit {i}") as p:
            p.define_color(f"c{i}", "wood", (i, 0, 0))
    assert store.history("p") == ["edit 2", "edit 3", "edit 4"]
    assert store.undo("p", 10) == ["edit 4", "edit 3", "edit 2"]
    assert list(store.load("p").colors) == ["c0", "c1"]


def test_a_copied_project_folder_is_a_separate_project(store: ProjectStore) -> None:
    _build(store)
    shutil.copytree(store.folder("car"), store.folder("car_copy"))
    with store.edit("car_copy", "copy edit") as p:
        assert p.name == "car_copy"
        p.remove_part("empty")
    assert "empty" not in store.load("car_copy").parts
    assert "empty" in store.load("car").parts
    assert store.history("car") == ["colors", "body", "wheels"]
    assert store.history("car_copy")[-1] == "copy edit"


def test_a_failed_save_restores_the_project(
    store: ProjectStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build(store)
    before = {f: (store.folder("car") / f).read_bytes() for f in ("project.json", "parts.npz")}
    calls = []
    real_commit = store_module._commit

    def failing_commit(temporary: Path, path: Path) -> None:
        calls.append(path.name)
        if path.name == "project.json" and len(calls) == 2:
            raise PermissionError("busy")
        real_commit(temporary, path)

    monkeypatch.setattr(store_module, "_commit", failing_commit)
    with pytest.raises(PermissionError), store.edit("car", "doomed") as p:
        p.remove_part("empty")
    after = {f: (store.folder("car") / f).read_bytes() for f in ("project.json", "parts.npz")}
    assert after == before
    assert store.history("car") == ["colors", "body", "wheels"]


def test_busy_files_are_retried(store: ProjectStore, monkeypatch: pytest.MonkeyPatch) -> None:
    store.create("p", "prop")
    attempts = []
    real_replace = Path.replace

    def flaky_replace(self: Path, target: Path) -> Path:
        attempts.append(self.name)
        if len(attempts) <= 2:
            raise PermissionError("busy")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    with store.edit("p", "x") as p:
        p.define_color("c", "wood", (1, 2, 3))
    assert "c" in store.load("p").colors
    attempts.clear()

    def always_busy(self: Path, target: Path) -> Path:
        raise PermissionError("busy")

    monkeypatch.setattr(Path, "replace", always_busy)
    with pytest.raises(PermissionError), store.edit("p", "y") as p:
        p.define_color("d", "wood", (1, 2, 3))
    monkeypatch.undo()
    assert store.history("p") == ["x"]  # no step for the edit that was not saved
    assert list(store.load("p").colors) == ["c"]


def test_create_and_list(store: ProjectStore) -> None:
    assert store.names() == []
    store.create("b_car", "vehicle")
    store.create("a_crate", "prop")
    assert store.names() == ["a_crate", "b_car"]
    assert store.load("a_crate").kind == "prop"
    with pytest.raises(ProjectError, match="already exists"):
        store.create("a_crate", "prop")
    with pytest.raises(ProjectError, match="kind must be one of vehicle, prop"):
        store.create("c", "boat")
    with pytest.raises(ProjectError, match="unknown project 'zz'; projects: a_crate, b_car"):
        store.load("zz")
    with pytest.raises(ProjectError, match="invalid project name"):
        store.load("../a_crate")


def test_damaged_files(store: ProjectStore) -> None:
    _build(store)
    folder = store.folder("car")
    (folder / "parts.npz").write_bytes(b"not a zip")
    with pytest.raises(ProjectFileError, match="cannot read"):
        store.load("car")
    (folder / "project.json").write_text("{", encoding="utf-8")
    with pytest.raises(ProjectFileError, match="cannot read"):
        store.load("car")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.update(format=2), "unknown project format 2"),
        (lambda d: d.update(kind="boat"), "unknown project kind"),
        (lambda d: d["parts"][0].update(role="door"), "unknown part role"),
        (lambda d: d["colors"][0].update(material="steel"), "damaged project file"),
        (lambda d: d.pop("anchors"), "damaged project file"),
        (lambda d: d["parts"][0].update(grid="arr_9"), "damaged project file"),
        (lambda d: d.update(anchors=[1, 2]), "damaged project file"),
    ],
)
def test_malformed_project_data(change: Callable[[Any], object], message: str) -> None:
    project = Project("p", "vehicle")
    project.define_color("c", "wood", (1, 2, 3))
    project.add_part("a")
    project.draw("a", box_shape((0, 0, 0), (1, 1, 1)), "add", "c")
    data = project_to_json(project)
    grids = {"arr_0": np.ones((1, 1, 1), np.uint8)}
    assert project_from_json(data, grids).parts["a"].voxels == 1
    change(data)
    with pytest.raises(ProjectFileError, match=message):
        project_from_json(data, grids)


def test_grid_with_wrong_type_is_refused() -> None:
    project = Project("p", "vehicle")
    project.define_color("c", "wood", (1, 2, 3))
    project.add_part("a")
    project.draw("a", box_shape((0, 0, 0), (1, 1, 1)), "add", "c")
    with pytest.raises(ProjectFileError, match="not a 3D uint8"):
        project_from_json(project_to_json(project), {"arr_0": np.ones((1, 1), np.uint8)})
