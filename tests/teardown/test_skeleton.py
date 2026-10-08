"""The skeleton must reproduce the XML positions verified in game by the 0.2.0 calibration car."""

import xml.etree.ElementTree as ET

import numpy as np
import pytest

import make_calibration_mod as cal
from buildup.palette import Material, Palette
from buildup.project import Axle, Project, WheelLayout, box_shape, build_assembly
from buildup.teardown import Assembly, PlacedObject, Wheel, meters, skeleton_xml, xml_vec


def _solid(size: tuple[int, int, int], index: int = 121) -> np.ndarray:
    return np.full(size, index, dtype=np.uint8)


def _palette() -> Palette:
    palette = Palette()
    palette.index_for(Material.WEAK_METAL, (200, 0, 0))
    return palette


def calibration_assembly() -> Assembly:
    """The calibration car rebuilt as an assembly (same sizes, origins, axles, locations)."""
    bx, by, bz = cal.BODY_VOX_POS
    sx, _, sz = cal.BODY_SIZE
    body = PlacedObject("car_body", _solid(cal.BODY_SIZE), (bx - sx // 2, by, bz - sz // 2))
    wheels = []
    for w in cal.WHEELS:
        cx, cy, cz = w.center_vox
        d, width = cal.WHEEL_DIAMETER, cal.WHEEL_WIDTH
        origin = (cx - width // 2, cy - d // 2, cz - d // 2)
        obj = PlacedObject(w.object_name, _solid((width, d, d)), origin)
        wheels.append(Wheel(w.name, obj, (float(cx), float(cy), float(cz)), w.steer, w.drive))
    anchors = {tag: (float(x), float(y), float(z)) for tag, (x, y, z) in cal.LOCATIONS.items()}
    return Assembly(
        "calibration", "vehicle", (body,), tuple(wheels), anchors, _palette(), {}, "basic"
    )


def _find(element: ET.Element, path: str) -> ET.Element:
    found = element.find(path)
    assert found is not None, path
    return found


def _floats(text: str | None) -> tuple[float, ...]:
    assert text is not None
    return tuple(float(v) for v in text.split())


def test_skeleton_matches_the_car_verified_in_game() -> None:
    ours = ET.fromstring(skeleton_xml(calibration_assembly(), "calibration"))
    verified = ET.fromstring(cal.car_xml())
    our_body = ours.find("./group/vehicle/body")
    their_body = verified.find(".//vehicle/body")
    assert our_body is not None
    assert their_body is not None
    assert our_body.get("dynamic") == their_body.get("dynamic") == "true"

    our_vox = our_body.find("vox")
    their_vox = their_body.find("vox")
    assert our_vox is not None
    assert their_vox is not None
    assert _floats(our_vox.get("pos")) == _floats(their_vox.get("pos"))
    for location in their_vox.findall("location"):
        mine = our_vox.find(f"location[@tags='{location.get('tags')}']")
        assert mine is not None
        assert _floats(mine.get("pos")) == _floats(location.get("pos"))

    their_wheels = {w.get("name"): w for w in their_body.findall("wheel")}
    our_wheels = {w.get("name"): w for w in our_body.findall("wheel")}
    assert our_wheels.keys() == their_wheels.keys()
    for name, theirs in their_wheels.items():
        mine = our_wheels[name]
        for attribute in ("drive", "steer", "travel"):
            assert mine.get(attribute) == theirs.get(attribute)
        assert _floats(mine.get("pos")) == _floats(theirs.get("pos"))
        assert _floats(_find(mine, "vox").get("pos")) == _floats(_find(theirs, "vox").get("pos"))
        assert _find(mine, "vox").get("object") == _find(theirs, "vox").get("object")

    vehicle = ours.find("./group/vehicle")
    assert vehicle is not None
    their_vehicle = verified.find(".//vehicle")
    assert their_vehicle is not None
    for attribute in ("spring", "damping", "topspeed"):
        assert vehicle.get(attribute) == their_vehicle.get(attribute)
    assert ours.get("version") == verified.get("version") == "2.0.0"


def test_project_api_reproduces_the_calibration_car() -> None:
    """End to end: the car drawn with the modelling API gives the verified XML values."""
    project = Project("calibration", "vehicle")
    project.define_color("paint", "weak metal", (200, 0, 0))
    project.define_color("tire", "plastic", (20, 20, 20))
    project.add_part("car_body")
    sx, sy, sz = cal.BODY_SIZE
    bx, by, bz = cal.BODY_VOX_POS
    start = (bx - sx // 2, by, bz - sz // 2)
    project.draw(
        "car_body", box_shape(start, (start[0] + sx, by + sy, start[2] + sz)), "add", "paint"
    )
    inner = abs(cal.WHEELS[0].center_vox[0]) - cal.WHEEL_WIDTH // 2
    axles = sorted({(w.center_vox[2], w.steer, w.drive) for w in cal.WHEELS})
    project.add_wheels(
        [Axle(z, steer=steer, drive=drive) for z, steer, drive in axles],
        WheelLayout(cal.WHEEL_DIAMETER, cal.WHEEL_WIDTH, inner),
        "tire",
    )
    for tag, (x, y, z) in cal.LOCATIONS.items():
        project.set_anchor(tag, (x, y, z))
    assembly, _ = build_assembly(project)
    ours = ET.fromstring(skeleton_xml(assembly, "calibration"))
    verified = ET.fromstring(cal.car_xml())
    pairs = [
        (_find(ours, ".//body/vox"), _find(verified, ".//body/vox")),
        *(
            (_find(ours, f".//location[@tags='{t}']"), _find(verified, f".//location[@tags='{t}']"))
            for t in cal.LOCATIONS
        ),
    ]
    for w in cal.WHEELS:
        mine = _find(ours, f".//wheel[@name='{w.name}']")
        theirs = _find(verified, f".//wheel[@name='{w.name}']")
        pairs += [(mine, theirs), (_find(mine, "vox"), _find(theirs, "vox"))]
        for attribute in ("drive", "steer", "travel"):
            assert mine.get(attribute) == theirs.get(attribute)
    for mine, theirs in pairs:
        assert _floats(mine.get("pos")) == _floats(theirs.get("pos"))


def test_every_vox_references_the_model_file() -> None:
    root = ET.fromstring(skeleton_xml(calibration_assembly(), "calibration"))
    files = {v.get("file") for v in root.iter("vox")}
    assert files == {"MOD/vox/calibration.vox"}
    assert _find(root, "group").get("name") == "calibration"


def test_odd_sizes_and_odd_wheel_width_use_the_measured_origin() -> None:
    # 5 x 7 x 9 body with its first cell at (-2, 3, -5): pos point = origin + (2, 0, 5).
    body = PlacedObject("body", _solid((5, 7, 9)), (-2, 3, -5))
    assert body.vox_pos == (0, 3, 0)
    # Wheel 3 wide, 8 high: cells x -11..-8, axle at x = -9.5; pos point x = -11 + 1 = -10.
    wheel_obj = PlacedObject("wheel_fl", _solid((3, 8, 8)), (-11, 0, -17))
    wheel = Wheel("fl", wheel_obj, (-9.5, 4.0, -13.0), steer=True, drive=False)
    assert wheel.vox_offset == (-0.5, -4.0, 0.0)
    xml = skeleton_xml(Assembly("odd", "vehicle", (body,), (wheel,), {}, _palette(), {}), "odd")
    root = ET.fromstring(xml)
    assert _find(root, ".//wheel/vox").get("pos") == "-0.05 -0.4 0"
    assert _find(root, ".//wheel").get("pos") == "-0.95 0.4 -1.3"
    assert root.find(".//location") is None  # no anchors, no locations


def test_prop_skeleton_is_one_dynamic_body() -> None:
    a = PlacedObject("base", _solid((4, 2, 4)), (-2, 0, -2))
    b = PlacedObject("top", _solid((2, 2, 2)), (-1, 2, -1))
    root = ET.fromstring(
        skeleton_xml(Assembly("crate", "prop", (a, b), (), {}, _palette(), {}), "crate")
    )
    assert root.find(".//vehicle") is None
    body = root.find("./group/body")
    assert body is not None
    assert body.get("dynamic") == "true"
    assert [(v.get("object"), v.get("pos")) for v in body.findall("vox")] == [
        ("base", "0 0 0"),
        ("top", "0 0.2 0"),
    ]


def test_seats_and_lights() -> None:
    car = calibration_assembly()
    anchors = {
        **car.anchors,
        "driver_seat": (-4.0, 6.0, 1.0),
        "passenger_seat_2": (4.0, 6.0, 9.0),
        "passenger_seat": (4.0, 6.0, 1.0),
        "headlight_l": (-6.0, 7.0, -21.0),
        "taillight_r": (6.0, 7.0, 21.0),
        "hinge_door": (0.0, 5.0, 0.0),
    }
    seated = Assembly(car.name, car.kind, car.body, car.wheels, anchors, car.palette, {})
    root = ET.fromstring(skeleton_xml(seated, "calibration"))
    body = _find(root, "./group/vehicle/body")
    vox = _find(body, "vox")
    px, py, pz = car.body[0].vox_pos
    # Lights are children of the first body vox, relative to its pos point.
    head, tail = vox.findall("light")
    assert _floats(head.get("pos")) == tuple(float(meters(v)) for v in (-6 - px, 7 - py, -21 - pz))
    assert head.get("type") == "cone"
    assert head.get("rot") == "0 180 0"  # shines towards -Z, the front
    assert tail.get("type") == "area"
    assert tail.get("rot") is None
    assert tail.get("color") == "1 .1 .1"
    # Rigs come after the wheels, in the body, at the seat points.
    tags = [child.tag for child in body]
    assert tags == ["vox", "wheel", "wheel", "wheel", "wheel", "rig", "rig", "rig"]
    driver, first, second = body.findall("rig")
    assert driver.get("name") == "driver"
    assert driver.get("tags") == "driver sort=0"
    assert _floats(driver.get("pos")) == (-0.4, 0.6, 0.1)
    names = [loc.get("name") for loc in driver.findall("location")]
    assert names == [
        "seat",
        "ik_head",
        "ik_hand_l",
        "ik_hand_r",
        "ik_foot_l",
        "ik_foot_r",
        "steeringwheel",
    ]
    for loc in driver.findall("location"):
        assert loc.get("tags") == loc.get("name")
    seat = _find(driver, "location[@name='seat']")
    assert _floats(seat.get("pos")) == (0.0, 0.0, 0.0)
    assert seat.get("rot") == "80 0 0"
    assert _floats(_find(driver, "location[@name='ik_head']").get("pos")) == (0.0, 0.55, 0.3)
    assert first.get("tags") == "sort=1"
    assert _floats(first.get("pos")) == (0.4, 0.6, 0.1)
    assert second.get("tags") == "sort=2"
    assert _floats(second.get("pos")) == (0.4, 0.6, 0.9)
    assert [loc.get("name") for loc in second.findall("location")] == [
        "seat",
        "ik_head",
        "ik_foot_l",
        "ik_foot_r",
    ]
    assert "hinge" not in skeleton_xml(seated, "calibration")


def test_prop_skeleton_ignores_seats_and_lights() -> None:
    crate = PlacedObject("crate", _solid((4, 4, 4)), (-2, 0, -2))
    anchors = {"driver_seat": (0.0, 5.0, 0.0), "headlight": (0.0, 2.0, -2.0)}
    text = skeleton_xml(Assembly("crate", "prop", (crate,), (), anchors, _palette(), {}), "crate")
    assert "rig" not in text
    assert "light" not in text


@pytest.mark.parametrize(
    ("vox", "text"),
    [(0, "0"), (-12, "-1.2"), (5.5, "0.55"), (-0.5, "-0.05"), (-0.0, "0"), (100, "10")],
)
def test_meters(vox: float, text: str) -> None:
    assert meters(vox) == text


def test_xml_vec() -> None:
    assert xml_vec((-9.5, 4, 0)) == "-0.95 0.4 0"


def test_handling_presets_set_the_vehicle_attributes() -> None:
    car = calibration_assembly()
    for preset, speed in (("car", "90"), ("sports", "120"), ("truck", "70")):
        tuned = Assembly(
            car.name, car.kind, car.body, car.wheels, car.anchors, car.palette, {}, preset
        )
        vehicle = _find(ET.fromstring(skeleton_xml(tuned, "x")), "./group/vehicle")
        assert vehicle.get("topspeed") == speed
        assert vehicle.get("sound") is not None
    basic = _find(ET.fromstring(skeleton_xml(car, "x")), "./group/vehicle")
    assert basic.attrib == {"spring": "0.5", "damping": "0.7", "topspeed": "60"}
