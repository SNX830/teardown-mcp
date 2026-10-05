"""Run the calibration Lua probes against a mock Teardown engine (Lua 5.1 through lupa).

What this proves: the generated scripts run (API v2 callbacks, Lua 5.1 syntax), read the API
return values at the right positions, and tell apart an engine that follows our conventions from
engines that do not (mirrored X, misplaced wheels). What it does NOT prove: how the real engine
behaves. The mock is written from our own conventions and the signatures in the game's
``script_defs.lua``; only the in-game test (docs/TESTING_IN_GAME.md, protocol C) measures the game.
"""

import importlib
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

import make_calibration_mod as cal
from buildup.voxio import VoxObject, objects_from_document, read_vox, xml_origin
from buildup.voxio.axes import grid_to_magica

# A plain import (not importorskip): lupa is a declared dev dependency, its absence must fail.
lua51 = importlib.import_module("lupa.lua51")

# Vector, quaternion and transform helpers of the Teardown API, written from their documented
# behaviour. Quaternions are {x, y, z, w}; QuatEuler applies X, then Z, then Y (q = qy * qz * qx).
MOCK_MATH = r"""
client = {}
watches = {}
function Vec(x, y, z) return { x or 0, y or 0, z or 0 } end
function VecAdd(a, b) return { a[1] + b[1], a[2] + b[2], a[3] + b[3] } end
function VecSub(a, b) return { a[1] - b[1], a[2] - b[2], a[3] - b[3] } end
function VecScale(a, s) return { a[1] * s, a[2] * s, a[3] * s } end
function VecLerp(a, b, t) return VecAdd(a, VecScale(VecSub(b, a), t)) end
function QuatMul(a, b)
  return { a[4]*b[1] + a[1]*b[4] + a[2]*b[3] - a[3]*b[2],
           a[4]*b[2] - a[1]*b[3] + a[2]*b[4] + a[3]*b[1],
           a[4]*b[3] + a[1]*b[2] - a[2]*b[1] + a[3]*b[4],
           a[4]*b[4] - a[1]*b[1] - a[2]*b[2] - a[3]*b[3] }
end
function QuatAxisAngle(axis, deg)
  local h = math.rad(deg) / 2
  return { axis[1] * math.sin(h), axis[2] * math.sin(h), axis[3] * math.sin(h), math.cos(h) }
end
function QuatEuler(x, y, z)
  return QuatMul(QuatAxisAngle({ 0, 1, 0 }, y or 0),
    QuatMul(QuatAxisAngle({ 0, 0, 1 }, z or 0), QuatAxisAngle({ 1, 0, 0 }, x or 0)))
end
function QuatRotateVec(q, v)
  local p = QuatMul(QuatMul(q, { v[1], v[2], v[3], 0 }), { -q[1], -q[2], -q[3], q[4] })
  return { p[1], p[2], p[3] }
end
function Transform(pos, rot) return { pos = pos or Vec(), rot = rot or { 0, 0, 0, 1 } } end
function TransformToParentPoint(t, p) return VecAdd(t.pos, QuatRotateVec(t.rot, p)) end
function TransformToLocalPoint(t, p)
  return QuatRotateVec({ -t.rot[1], -t.rot[2], -t.rot[3], t.rot[4] }, VecSub(p, t.pos))
end
function TransformToParentTransform(a, b)
  return Transform(TransformToParentPoint(a, b.pos), QuatMul(a.rot, b.rot))
end
function DebugWatch(name, value) watches[name] = tostring(value) end
function DebugTransform() end
"""

# The scene: shapes[h] = {size, local_t, body, voxel(i, j, k) -> entry}, bodies[b] = transform,
# locations[h] = world transform, tags[tag] = handle (only once `ready` is true).
MOCK_ENGINE = r"""
shapes, bodies, locations, tags, colors = {}, {}, {}, {}, {}
ready = true
ground_y = 0
local function find(tag) if ready then return tags[tag] or 0 end return 0 end
FindShape, FindVehicle, FindLocation = find, find, find
function GetVehicleBody() return vehicle_body end
function GetLocationTransform(h) return locations[h] end
function GetShapeSize(h) local s = shapes[h].size return s[1], s[2], s[3], 0.1 end
function GetShapeLocalTransform(h) return shapes[h].local_t end
function GetShapeBody(h) return shapes[h].body end
function GetBodyTransform(b) return bodies[b] end
local function world(h)
  return TransformToParentTransform(bodies[shapes[h].body], shapes[h].local_t)
end
local function material(h, i, j, k)
  local entry = shapes[h].voxel(i, j, k)
  if entry == 0 then return "", 0, 0, 0, 0, 0 end
  local c = colors[entry]
  return "plastic", c[1], c[2], c[3], 1, entry + entry_shift
end
function GetShapeMaterialAtIndex(h, i, j, k) return material(h, i, j, k) end
function GetShapeMaterialAtPosition(h, p)
  local l = TransformToLocalPoint(world(h), p)
  local i, j, k = math.floor(l[1] / 0.1), math.floor(l[2] / 0.1), math.floor(l[3] / 0.1)
  local s = shapes[h].size
  if i < 0 or j < 0 or k < 0 or i >= s[1] or j >= s[2] or k >= s[3] then
    return "", 0, 0, 0, 0, 0
  end
  return material(h, i, j, k)
end
function GetShapeBounds(h)
  local s, t = shapes[h], world(h)
  local lo, hi = { 1e9, 1e9, 1e9 }, { -1e9, -1e9, -1e9 }
  for _, c in ipairs({ {0,0,0}, {1,0,0}, {0,1,0}, {0,0,1}, {1,1,0}, {1,0,1}, {0,1,1}, {1,1,1} }) do
    local corner = { c[1] * s.size[1] * 0.1, c[2] * s.size[2] * 0.1, c[3] * s.size[3] * 0.1 }
    local p = TransformToParentPoint(t, corner)
    for a = 1, 3 do lo[a] = math.min(lo[a], p[a]); hi[a] = math.max(hi[a], p[a]) end
  end
  return lo, hi
end
rejected = {}
function QueryRejectVehicle() end
function QueryRejectShape(h) rejected[h] = true end
-- The ray from above a wheel hits that wheel unless the probe rejected it (5 cm below the origin).
function QueryRaycast(origin)
  local wheel_rejected = next(rejected) ~= nil
  rejected = {}
  if not wheel_rejected then return true, 0.05, Vec(0, 1, 0), 0 end
  return true, origin[2] - ground_y, Vec(0, 1, 0), 0
end
-- Vehicle API: positions in vehicle space, set by the test.
driver_pos, exhausts, vitals = nil, {}, {}
function GetVehicleDriverPos() return driver_pos end
function GetVehicleExhaustTransforms() return exhausts end
function GetVehicleVitalTransforms() return vitals end
"""

VOXEL_M = 0.1
BODY = 7


@dataclass
class Engine:
    """Knobs of the mock engine. Defaults follow the engine as measured in game on 2026-10-06
    (docs/TEARDOWN_REFERENCE.md §5): it keeps the MagicaVoxel grid, rotates the shape so that grid
    axes x, y, z point to +X, -Z, +Y of the body, and puts the XML ``pos`` at ``xml_origin``.
    """

    mirror_x: bool = False
    entry_shift: int = 0  # the engine numbers palette entries differently from our .vox
    ready_at_init: bool = True
    body_moves_after_init: bool = False  # the car drives away; locations stay where they were
    wheel_lift_vox: int = 0  # the engine shows the wheel shapes higher than we expect
    body_yaw_deg: float = 30.0


@pytest.fixture(scope="module")
def mod_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("probe") / "BuildupCalibration"
    cal.build_mod(output)
    return output


@pytest.fixture(scope="module")
def objects(mod_dir: Path) -> dict[str, VoxObject]:
    return {o.name: o for o in objects_from_document(read_vox(mod_dir / cal.VOX_PATH))}


def _quat_euler(lua: Any, rot: tuple[float, float, float]) -> Any:
    return lua.eval("QuatEuler")(*rot)


def _voxel_reader(grid: npt.NDArray[np.uint8], mirror_x: bool) -> Callable[[Any, Any, Any], int]:
    sx = grid.shape[0]

    def voxel(i: Any, j: Any, k: Any) -> int:
        x = sx - 1 - int(i) if mirror_x else int(i)
        return int(grid[x, int(j), int(k)])

    return voxel


def _add_shape(
    lua: Any, handle: int, td_grid: npt.NDArray[np.uint8], local_t: Any, engine: Engine
) -> None:
    """Add a shape of the body ``BODY``: the engine stores the MagicaVoxel grid."""
    magica = grid_to_magica(td_grid)
    lua.globals().shapes[handle] = lua.table_from(
        {
            "size": lua.table(*magica.shape),
            "local_t": local_t,
            "body": BODY,
            "voxel": _voxel_reader(magica, engine.mirror_x),
        }
    )


def _engine_rot(lua: Any, rot: Any) -> Any:
    """Shape rotation: the XML rotation applied after the MagicaVoxel-to-Teardown turn."""
    to_teardown = lua.eval("QuatAxisAngle")(lua.table(1, 0, 0), -90)  # grid y -> -Z, z -> +Y
    return lua.eval("QuatMul")(rot, to_teardown)


def _engine_transform(lua: Any, pos_vox: cal.Vec3, rot: Any, td_size: tuple[int, ...]) -> Any:
    """Shape transform: its grid corner (Teardown min x, min y, max z) placed around ``pos``."""
    ox, _, oz = xml_origin((td_size[0], td_size[1], td_size[2]))
    corner_vox = lua.table(-ox * VOXEL_M, 0, (td_size[2] - oz) * VOXEL_M)
    offset = lua.eval("QuatRotateVec")(rot, corner_vox)
    corner = lua.table(*(p * VOXEL_M + offset[i + 1] for i, p in enumerate(pos_vox)))
    return lua.eval("Transform")(corner, _engine_rot(lua, rot))


def _new_lua(engine: Engine) -> Any:
    lua = lua51.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(MOCK_MATH)
    lua.execute(MOCK_ENGINE)
    g = lua.globals()
    g.entry_shift = engine.entry_shift
    palette, _ = cal.make_palette()
    for index, entry in palette.entries.items():
        g.colors[index] = lua.table(*(c / 255 for c in entry.color))
    yaw = math.radians(engine.body_yaw_deg) / 2
    g.bodies[BODY] = lua.eval("Transform")(
        lua.table(12.0, 3.0, -4.0), lua.table(0, math.sin(yaw), 0, math.cos(yaw))
    )
    g.vehicle_body = BODY
    return lua


def _run(lua: Any, mod_dir: Path, script: str, engine: Engine) -> dict[str, str]:
    code = (mod_dir / "script" / script).read_text(encoding="utf-8")
    assert code.startswith("#version 2\n")  # Teardown's directive, not Lua: strip it
    lua.globals().ready = engine.ready_at_init
    lua.execute(code.split("\n", 1)[1])
    lua.execute("client.init()")
    if engine.body_moves_after_init:
        lua.execute(f"bodies[{BODY}] = Transform(Vec(20, 4, 9), QuatAxisAngle({{ 0, 0, 1 }}, 10))")
    lua.globals().ready = True
    lua.execute("client.tick()")
    return {str(k): str(v) for k, v in lua.globals().watches.items()}


def run_prop(mod_dir: Path, objects: dict[str, VoxObject], engine: Engine) -> dict[str, str]:
    lua = _new_lua(engine)
    for handle, element in enumerate(cal.PROP_ELEMENTS, start=1):
        grid = objects[element.object_name].grid
        rot = _quat_euler(lua, element.rot_deg)
        local_t = _engine_transform(lua, element.pos_vox, rot, grid.shape)
        _add_shape(lua, handle, grid, local_t, engine)
        lua.globals().tags[element.tag] = handle
    return _run(lua, mod_dir, "prop.lua", engine)


def run_car(
    mod_dir: Path, objects: dict[str, VoxObject], engine: Engine, drop_locations: bool = False
) -> dict[str, str]:
    lua = _new_lua(engine)
    g = lua.globals()
    identity = lua.table(0, 0, 0, 1)
    body = objects["car_body"].grid
    _add_shape(lua, 1, body, _engine_transform(lua, cal.BODY_VOX_POS, identity, body.shape), engine)
    g.tags[cal.VEHICLE_TAG] = 50
    g.tags[cal.BODY_TAG] = 1
    for handle, wheel in enumerate(cal.WHEELS, start=2):
        grid = objects[wheel.object_name].grid
        # A spinning wheel: turned 30 degrees about its axle, its box center stays on the axle.
        spin = _engine_rot(lua, lua.eval("QuatAxisAngle")(lua.table(1, 0, 0), 30))
        magica_size = grid_to_magica(grid).shape
        half = lua.eval("QuatRotateVec")(spin, lua.table(*(s * VOXEL_M / 2 for s in magica_size)))
        cx, cy, cz = (v * VOXEL_M for v in wheel.center_vox)
        cy += engine.wheel_lift_vox * VOXEL_M
        corner = lua.table(cx - half[1], cy - half[2], cz - half[3])
        _add_shape(lua, handle, grid, lua.eval("Transform")(corner, spin), engine)
        g.tags[wheel.tag] = handle
    for handle, (tag, pos) in enumerate(cal.LOCATIONS.items(), start=10):
        vehicle_space = lua.table(*(v * VOXEL_M for v in pos))
        # Location entities stay in the world where they were spawned.
        world = lua.eval("TransformToParentTransform")(
            g.bodies[BODY], lua.eval("Transform")(vehicle_space)
        )
        g.locations[handle] = world
        g.tags[tag] = handle
        if tag == "player":
            g.driver_pos = vehicle_space
        else:
            target = g.exhausts if tag == "exhaust" else g.vitals
            target[1] = lua.eval("Transform")(vehicle_space)
    if drop_locations:  # the engine consumed the locations and the vehicle has none
        for tag in cal.LOCATIONS:
            g.tags[tag] = None
        g.driver_pos, g.exhausts, g.vitals = None, lua.table(), lua.table()
    g.ground_y = 3.0  # world height of the ground; the body sits at y = 3 in this scene
    return _run(lua, mod_dir, "car.lua", engine)


# --- Prop -------------------------------------------------------------------------------------


def _corner_letters(corners: str) -> dict[str, str]:
    """{"000": "O", ...} from "000=O153 100=X154 ..." (letter only, raw entry dropped)."""
    return {item[:3]: item[4] for item in corners.split()}


# Corner pattern measured in game: the engine grid is the MagicaVoxel grid (index y runs towards
# Teardown -Z, index z upwards), so our Z marker sits at the engine's corner 000.
MEASURED_CORNERS = {
    "000": "Z", "100": ".", "010": "O", "001": ".",
    "110": "X", "101": ".", "011": "Y", "111": ".",
}  # fmt: skip


def test_prop_reproduces_the_game_readings(mod_dir: Path, objects: dict[str, VoxObject]) -> None:
    """The mock follows the measured engine, so the probe shows the 2026-10-06 readings."""
    watches = run_prop(mod_dir, objects, Engine())
    for element in cal.PROP_ELEMENTS:
        label = element.label
        assert _corner_letters(watches[f"{label} corners"]) == MEASURED_CORNERS
        sx, sy, sz = element.size
        assert watches[f"{label} size"] == f"{sx} {sz} {sy} scale 0.10"
        if label != "ODD":  # ODD probe points fall on voxel boundaries: not conclusive
            assert watches[f"{label} probe"].startswith("OK "), watches[f"{label} probe"]
    assert watches["ODD pos-xml"] == "-0.200 0.000 0.400"
    assert watches["EVEN pos-xml"] == "-0.300 0.000 0.500"
    assert watches["ODD axes"] == "x>+x y>-z z>+y"
    assert watches["EVEN axes"] == "x>+x y>-z z>+y"
    assert watches["ROT axes"] == "x>-z y>-x z>+y"
    assert watches["ROT pos-xml"] == "0.500 0.000 0.300"
    assert watches["ROT2 axes"] == "x>-z y>+y z>+x"
    assert watches["ROT2 pos-xml"] == "0.000 -0.500 0.300"


def test_prop_shows_our_palette_entries(mod_dir: Path, objects: dict[str, VoxObject]) -> None:
    _, colors = cal.make_palette()
    watches = run_prop(mod_dir, objects, Engine())
    assert f"O{colors.marker['O']} X{colors.marker['X']}" in watches["BUILDUP PROP"]
    assert f"010=O{colors.marker['O']} " in watches["EVEN corners"]


def test_prop_mirrored_x_is_detected(mod_dir: Path, objects: dict[str, VoxObject]) -> None:
    watches = run_prop(mod_dir, objects, Engine(mirror_x=True))
    for element in cal.PROP_ELEMENTS:
        if element.label != "ODD":
            assert watches[f"{element.label} probe"].startswith("MISMATCH ")
        letters = _corner_letters(watches[f"{element.label} corners"])
        assert letters != MEASURED_CORNERS
        # O and X sit at the two ends of the mirrored axis: they swap corners.
        assert (letters["010"], letters["110"]) == ("X", "O")


def test_prop_renumbered_entries_still_recognised(
    mod_dir: Path, objects: dict[str, VoxObject]
) -> None:
    watches = run_prop(mod_dir, objects, Engine(entry_shift=-1))
    assert all(
        watches[f"{e.label} probe"].startswith("OK ") for e in cal.PROP_ELEMENTS if e.label != "ODD"
    )


def test_prop_shapes_found_after_init(mod_dir: Path, objects: dict[str, VoxObject]) -> None:
    watches = run_prop(mod_dir, objects, Engine(ready_at_init=False))
    assert watches["EVEN probe"].startswith("OK ")


# --- Car --------------------------------------------------------------------------------------


def test_car_conventions_hold(mod_dir: Path, objects: dict[str, VoxObject]) -> None:
    watches = run_car(mod_dir, objects, Engine())
    assert watches["CAR body size"] == "16 36 6 scale 0.10"
    assert watches["CAR body pos-xml"].replace("-0.000", "0.000") == "-0.800 0.000 1.800"
    for wheel in cal.WHEELS:
        text = watches[f"CAR {wheel.name}"]
        axle, gap = text.split(" | ")
        assert [abs(float(v)) for v in axle.split()[1:]] == pytest.approx([0, 0, 0], abs=1e-6)
        assert gap == "gap +0 cm"
    for tag in cal.LOCATIONS:
        _assert_location_zero(watches[f"CAR loc {tag}"])


def _assert_location_zero(text: str) -> None:
    """ "entity dx dy dz | vehicle dx dy dz" with every difference zero."""
    entity, used = text.split(" | ")
    assert entity.startswith("entity ")
    assert used.startswith("vehicle ")
    for part in (entity, used):
        assert [abs(float(v)) for v in part.split()[1:]] == pytest.approx([0, 0, 0], abs=1e-6)


def test_car_locations_read_once_before_the_car_moves(
    mod_dir: Path, objects: dict[str, VoxObject]
) -> None:
    watches = run_car(mod_dir, objects, Engine(body_moves_after_init=True))
    for tag in cal.LOCATIONS:
        _assert_location_zero(watches[f"CAR loc {tag}"])


def test_car_locations_missing(mod_dir: Path, objects: dict[str, VoxObject]) -> None:
    lua_watches = run_car(mod_dir, objects, Engine(), drop_locations=True)
    for tag in cal.LOCATIONS:
        assert lua_watches[f"CAR loc {tag}"] == "entity not found | vehicle none"


def test_car_misplaced_wheels_are_detected(mod_dir: Path, objects: dict[str, VoxObject]) -> None:
    watches = run_car(mod_dir, objects, Engine(wheel_lift_vox=4))
    for wheel in cal.WHEELS:
        axle, gap = watches[f"CAR {wheel.name}"].split(" | ")
        assert float(axle.split()[2]) == pytest.approx(0.4)
        assert gap == "gap +40 cm"


def test_car_found_after_init(mod_dir: Path, objects: dict[str, VoxObject]) -> None:
    watches = run_car(mod_dir, objects, Engine(ready_at_init=False))
    assert watches["CAR fl"].endswith("gap +0 cm")
    assert "not found" not in " ".join(watches.values())
