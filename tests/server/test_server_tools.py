"""The MCP tools, called through the SDK's in-memory client (what an MCP host sends)."""

import base64
import io
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, get_args

import pytest
from mcp import Client
from mcp.types import CallToolResult, Tool, ToolAnnotations
from PIL import Image

import buildup.project.store as store_module
from buildup.project.templates import DESIGNS
from buildup.server import INSTRUCTIONS, create_server
from buildup.server.app import HandlingName, TemplateName
from buildup.teardown.handling import HANDLING
from buildup.teardown.install import GamePaths

EXPECTED_TOOLS = {
    "create_project",
    "list_projects",
    "project_summary",
    "undo",
    "define_color",
    "add_part",
    "remove_part",
    "draw_box",
    "draw_cylinder",
    "draw_ellipsoid",
    "draw_profile",
    "draw_wedge",
    "start_from_template",
    "set_handling",
    "cut_edges",
    "mirror_part",
    "hollow_part",
    "move_part",
    "add_wheels",
    "set_anchor",
    "preview",
    "inspect",
    "slice_layers",
    "export_model",
    "teardown_reference",
    "validate_mod",
    "read_game_log",
    "lookup_api",
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[Client]:
    server = create_server(tmp_path / "ws", GamePaths(install=None, log=None))
    async with Client(server, raise_exceptions=True) as c:
        yield c


def hints(tool: Tool) -> ToolAnnotations:
    assert tool.annotations is not None
    return tool.annotations


def text_of(result: CallToolResult) -> str:
    return "\n".join(block.text for block in result.content if block.type == "text")


def image_bytes(result: CallToolResult) -> bytes:
    images = [block for block in result.content if block.type == "image"]
    assert len(images) == 1
    return base64.b64decode(images[0].data)


async def ok(client: Client, tool: str, **arguments: Any) -> str:
    result = await client.call_tool(tool, arguments)
    assert not result.is_error, text_of(result)
    return text_of(result)


async def error(client: Client, tool: str, **arguments: Any) -> str:
    result = await client.call_tool(tool, arguments)
    assert result.is_error
    return text_of(result)


async def build_car(client: Client) -> None:
    await ok(client, "create_project", project="car", description="test")
    await ok(
        client,
        "define_color",
        project="car",
        name="paint",
        material="weak metal",
        rgb=[200, 30, 30],
    )
    await ok(
        client, "define_color", project="car", name="window", material="glass", rgb=[120, 170, 220]
    )
    await ok(
        client, "define_color", project="car", name="tire", material="plastic", rgb=[20, 20, 20]
    )
    await ok(client, "add_part", project="car", name="body")
    await ok(
        client,
        "draw_box",
        project="car",
        part="body",
        start=[-8, 3, -20],
        end=[8, 9, 20],
        color="paint",
    )
    await ok(
        client,
        "add_wheels",
        project="car",
        axles=[{"z": -13, "steer": True}, {"z": 13, "drive": True}],
        diameter=8,
        width=2,
        inner_x=8,
        tire_color="tire",
    )
    for name, position in (("player", [-4, 9, 2]), ("vital", [0, 6, -15]), ("exhaust", [5, 4, 20])):
        await ok(client, "set_anchor", project="car", name=name, position=position)


@pytest.mark.anyio
async def test_tools_and_instructions(client: Client) -> None:
    listed = await client.list_tools()
    assert {t.name for t in listed.tools} == EXPECTED_TOOLS
    for tool in listed.tools:
        assert tool.description, tool.name
        assert tool.annotations is not None
    tools = {t.name: t for t in listed.tools}
    for name in ("remove_part", "undo", "export_model"):
        assert hints(tools[name]).destructive_hint is True
    for name in (
        "inspect",
        "slice_layers",
        "list_projects",
        "teardown_reference",
        "validate_mod",
        "read_game_log",
        "lookup_api",
    ):
        assert hints(tools[name]).read_only_hint is True
    assert hints(tools["preview"]).read_only_hint is False
    draw_box = tools["draw_box"]
    schema = draw_box.input_schema
    assert schema["required"] == ["project", "part", "start", "end"]
    assert "exclusive" in json.dumps(schema["properties"]["end"])
    assert client.server_info is not None
    assert "Teardown" in INSTRUCTIONS


@pytest.mark.anyio
async def test_build_and_export_a_car(client: Client, tmp_path: Path) -> None:
    await build_car(client)
    summary = await ok(client, "project_summary", project="car")
    assert "body (body): X -8..8, Y 3..9, Z -20..20 voxels; 1.6 x 0.6 x 4 m; 3840 voxels" in summary
    assert "wheel_fl (wheel fl)" in summary
    assert "player: (-4, 9, 2) vox = (-0.4, 0.9, 0.2) m" in summary
    assert "Undo steps available: 9." in summary  # 3 colors, part, box, wheels, 3 anchors

    exported = await ok(client, "export_model", project="car")
    mod = tmp_path / "ws" / "mods" / "Car"
    assert f"into the mod folder {mod}" in exported
    # The test car has no cabin: only the missing driver seat is reported.
    assert "no driver_seat anchor" in exported
    assert exported.count("\n  - ") == 1
    assert '<wheel name="fl" pos="-0.9 0.4 -1.3"' in exported
    assert (mod / "vox" / "car.vox").is_file()
    assert (mod / "prefab" / "car.xml").is_file()
    again = await ok(client, "export_model", project="car", mod_name="My Car 2")
    assert "My Car 2" in again
    assert await ok(client, "list_projects") == "Projects: car"


@pytest.mark.anyio
async def test_drawing_tools(client: Client) -> None:
    await build_car(client)
    out = await ok(
        client,
        "cut_edges",
        project="car",
        part="body",
        start=[-8, 3, -20],
        end=[8, 9, 20],
        edges=[["top", "front"], ["top", "back"]],
        depths=[3, 3],
    )
    assert out.startswith("96 voxels changed.")  # 2 edges x 16 columns x 3 voxels
    out = await ok(
        client,
        "cut_edges",
        project="car",
        part="body",
        start=[-8, 3, -20],
        end=[8, 9, 20],
        edges=[["bottom", "front"]],
        depths=[2, 2],
        mode="paint",
        color="window",
    )
    assert out.startswith("16 voxels changed.")
    out = await ok(
        client,
        "draw_cylinder",
        project="car",
        part="body",
        axis="z",
        center=[5, 4],
        radius=1,
        span=[20, 23],
        color="paint",
    )
    assert out.startswith("12 voxels changed.")
    assert "Z -20..23" in out
    out = await ok(
        client,
        "draw_ellipsoid",
        project="car",
        part="body",
        center=[0, 9, 0],
        radii=[3, 2, 3],
        color="window",
    )
    assert "voxels changed" in out
    out = await ok(
        client,
        "draw_wedge",
        project="car",
        part="body",
        start=[-4, 9, -10],
        end=[4, 12, -4],
        faces=["top", "front"],
        color="paint",
    )
    assert "voxels changed" in out
    out = await ok(
        client,
        "draw_box",
        project="car",
        part="body",
        start=[50, 50, 50],
        end=[51, 51, 51],
        mode="carve",
    )
    assert out.startswith("Nothing changed")
    assert "Mirrored." in await ok(client, "mirror_part", project="car", part="body", keep="right")
    assert "inner voxels" in await ok(client, "hollow_part", project="car", part="body")
    out = await ok(client, "move_part", project="car", part="wheel_fl", offset=[0, 1, 0])
    assert "axle (-9, 5, -13)" in out
    await ok(client, "add_part", project="car", name="roof")
    assert "Removed part 'roof'." in await ok(client, "remove_part", project="car", part="roof")
    assert "Deleted anchor 'vital'." in await ok(
        client, "set_anchor", project="car", name="vital", position=None
    )
    out = await ok(client, "undo", project="car", steps=2)
    assert out == "Reverted 2 edit(s), most recent first: set_anchor vital; remove_part roof"


@pytest.mark.anyio
async def test_preview_returns_an_image(client: Client, tmp_path: Path) -> None:
    await build_car(client)
    result = await client.call_tool("preview", {"project": "car"})
    assert not result.is_error
    image_block, text_block = result.content
    assert image_block.type == "image"
    assert image_block.mime_type == "image/png"
    image = Image.open(io.BytesIO(image_bytes(result)))
    assert image.width > 600
    assert text_block.type == "text"
    assert "saved to" in text_block.text
    assert (tmp_path / "ws" / "projects" / "car" / "preview.png").is_file()
    part = await client.call_tool(
        "preview", {"project": "car", "part": "wheel_fl", "views": ["left"]}
    )
    assert "marker(s) outside the shown voxels are not drawn" in text_of(part)
    small = Image.open(io.BytesIO(image_bytes(part)))
    assert small.width < image.width


@pytest.mark.anyio
async def test_inspect_and_slices(client: Client) -> None:
    await build_car(client)
    whole = await ok(client, "inspect", project="car")
    assert "Connectivity: 1 part" in whole  # the wheels touch the body sides
    assert "wheels are separate pieces by design" in whole
    assert "121 = paint" in whole
    body = await ok(client, "inspect", project="car", part="body")
    assert "Connectivity: 1 part" in body
    layers = await ok(client, "slice_layers", project="car", axis="y", positions=[3, 8])
    assert "Layer Y = 3 voxels" in layers
    assert "Layer Y = 8 voxels" in layers
    assert "Color names by palette index" in layers
    message = await error(client, "slice_layers", project="car", axis="y", positions=[30])
    assert "layers [30] are outside the voxels: y goes from 0 to 8" in message


@pytest.mark.anyio
async def test_clipped_shapes_are_reported(client: Client) -> None:
    await build_car(client)
    out = await ok(
        client,
        "draw_box",
        project="car",
        part="body",
        start=[100, 0, 0],
        end=[300, 1, 1],
        color="paint",
    )
    assert out.startswith("28 voxels changed.")
    assert "was cut." in out
    inside = await ok(
        client,
        "draw_box",
        project="car",
        part="body",
        start=[0, 9, 0],
        end=[1, 10, 1],
        color="paint",
    )
    assert "cut there" not in inside


@pytest.mark.anyio
async def test_file_errors_reach_the_ai(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    await build_car(client)

    def busy(temporary: Path, path: Path) -> None:
        raise PermissionError(13, "file in use", str(path))

    monkeypatch.setattr(store_module, "_commit", busy)
    message = await error(client, "add_part", project="car", name="roof")
    assert "file error" in message
    assert "file in use" in message
    monkeypatch.undo()
    assert "roof" not in await ok(client, "project_summary", project="car")


@pytest.mark.anyio
async def test_reference(client: Client) -> None:
    for topic in ("workflow", "frame", "materials", "vehicle_xml", "prop_xml", "mod_files"):
        assert len(await ok(client, "teardown_reference", topic=topic)) > 200
    await error(client, "teardown_reference", topic="lua")


@pytest.mark.anyio
async def test_errors_reach_the_ai(client: Client) -> None:
    assert "unknown project 'car'; projects: none yet" in await error(
        client, "project_summary", project="car"
    )
    assert "No projects yet" in await ok(client, "list_projects")
    await build_car(client)
    cases: list[tuple[str, dict[str, Any], str]] = [
        (
            "draw_box",
            {"part": "bdy", "start": [0, 0, 0], "end": [1, 1, 1], "color": "paint"},
            "unknown part 'bdy'",
        ),
        (
            "draw_box",
            {"part": "body", "start": [0, 0, 0], "end": [1, 0, 1], "color": "paint"},
            "below end",
        ),
        ("draw_box", {"part": "body", "start": [0, 0, 0], "end": [1, 1, 1]}, "needs a color"),
        (
            "draw_box",
            {"part": "body", "start": [0, 0], "end": [1, 1, 1], "color": "paint"},
            "start",
        ),
        ("define_color", {"name": "x", "material": "steel", "rgb": [1, 2, 3]}, "material"),
        ("define_color", {"name": "paint", "material": "wood", "rgb": [1, 2, 3]}, "cannot change"),
        ("create_project", {"kind": "vehicle"}, "already exists"),
        ("mirror_part", {"part": "body", "plane_x": 0.3}, "whole or half voxel"),
        (
            "add_wheels",
            {"axles": [{"z": 0}], "diameter": 7, "width": 2, "inner_x": 8, "tire_color": "tire"},
            "even",
        ),
        (
            "cut_edges",
            {
                "part": "body",
                "start": [0, 0, 0],
                "end": [2, 2, 2],
                "edges": [["top", "top"]],
                "depths": [1, 1],
            },
            "different axes",
        ),
        ("hollow_part", {"part": "body", "thickness": 0}, "greater than or equal to 1"),
        ("preview", {"part": "nothing"}, "unknown part"),
        ("export_model", {"mod_name": "bad_name"}, "invalid mod name"),
    ]
    for tool, arguments, message in cases:
        text = await error(client, tool, project="car", **arguments)
        assert message in text, (tool, text)
    assert "unknown project 'other'" in await error(client, "undo", project="other")
    await ok(client, "create_project", project="crate", kind="prop")
    await ok(
        client, "define_color", project="crate", name="wood", material="wood", rgb=[150, 100, 50]
    )
    await ok(client, "add_part", project="crate", name="box")
    assert "nothing to preview" in await error(client, "preview", project="crate")
    assert "No voxels yet." in await ok(client, "inspect", project="crate")
    assert "nothing to slice" in await error(
        client, "slice_layers", project="crate", axis="x", positions=[0]
    )
    assert "no body part" in await error(client, "export_model", project="crate")
    assert await ok(client, "undo", project="crate") == (
        "Reverted 1 edit(s), most recent first: add_part box"
    )
    assert "only vehicle projects" in await error(
        client,
        "add_wheels",
        project="crate",
        axles=[{"z": 0}],
        diameter=8,
        width=2,
        inner_x=8,
        tire_color="wood",
    )


@pytest.mark.anyio
async def test_draw_profile(client: Client) -> None:
    await build_car(client)
    out = await ok(
        client,
        "draw_profile",
        project="car",
        part="body",
        plane="side",
        span=[-8, 8],
        points=[[-20, 9], [20, 9], [12, 14], [-6, 14]],
        bevel=2,
        color="paint",
    )
    assert out.startswith("1")
    assert "voxels changed" in out
    out = await ok(
        client,
        "draw_profile",
        project="car",
        part="body",
        plane="side",
        span=[-7, 7],
        rows=["####", "####"],
        origin=[-5, 11],
        color="window",
        mode="paint",
    )
    assert out.startswith("112 voxels changed.")  # 4 x 2 cells across 14 layers
    assert "rows" in await error(
        client, "draw_profile", project="car", part="body", plane="side", span=[0, 1], color="paint"
    )
    assert "origin" in await error(
        client,
        "draw_profile",
        project="car",
        part="body",
        plane="side",
        span=[0, 1],
        rows=["#"],
        color="paint",
    )
    assert "bevel" in await error(
        client,
        "draw_profile",
        project="car",
        part="body",
        plane="side",
        span=[0, 1],
        rows=["#"],
        origin=[0, 0],
        bevel=40,
        color="paint",
    )


@pytest.mark.anyio
async def test_start_from_template_and_seat_hints(client: Client) -> None:
    await ok(client, "create_project", project="van", kind="vehicle")
    built = await ok(client, "start_from_template", project="van", template="van", length_m=5.0)
    assert built.startswith("Built template 'van'")
    assert "Z -25..25" in built
    exported = await ok(client, "export_model", project="van")
    assert "Warnings: none." in exported
    assert '<rig name="driver" tags="driver sort=0"' in exported
    again = await error(client, "start_from_template", project="van", template="sedan")
    assert "empty project" in again
    await ok(client, "create_project", project="crate", kind="prop")
    prop = await error(client, "start_from_template", project="crate", template="sedan")
    assert "kind 'vehicle'" in prop

    await ok(client, "create_project", project="kart", kind="vehicle")
    out = await ok(client, "set_anchor", project="kart", name="driver_seat", position=[-4, 5, 0])
    assert "driver's hip point" in out
    assert "player is not set: official cars put it at (-4, 11, 3) vox" in out
    out = await ok(client, "set_anchor", project="kart", name="headlight_l", position=[-6, 6, -20])
    assert "cone light shining forward" in out
    out = await ok(client, "set_anchor", project="kart", name="hinge_door", position=[0, 5, 0])
    assert "manifest only" in out


@pytest.mark.anyio
async def test_draw_profile_refuses_bevels_that_draw_nothing(client: Client) -> None:
    await build_car(client)
    base = {"project": "car", "part": "body", "plane": "side", "color": "paint"}
    square = [[0, 0], [4, 0], [4, 4], [0, 4]]
    assert "removes nothing" in await error(
        client, "draw_profile", **base, span=[0, 9], points=square, bevel=1, bevel_style="round"
    )
    assert "less than half the span" in await error(
        client, "draw_profile", **base, span=[0, 4], points=square, bevel=2
    )
    assert "origin goes with rows" in await error(
        client, "draw_profile", **base, span=[0, 4], points=square, origin=[0, 0]
    )
    await ok(client, "create_project", project="crate", kind="prop")
    out = await ok(client, "set_anchor", project="crate", name="headlight", position=[0, 2, 0])
    assert "vehicles only" in out


@pytest.mark.anyio
async def test_draw_profile_reports_an_empty_span_first(client: Client) -> None:
    await build_car(client)
    message = await error(
        client,
        "draw_profile",
        project="car",
        part="body",
        plane="side",
        span=[5, 2],
        points=[[0, 0], [4, 0], [4, 4]],
        bevel=2,
        color="paint",
    )
    assert "span 5..2 is empty" in message


@pytest.mark.anyio
async def test_set_handling(client: Client) -> None:
    await build_car(client)
    assert "Handling: car" in await ok(client, "project_summary", project="car")
    out = await ok(client, "set_handling", project="car", preset="sports")
    assert "Crownzygot" in out
    exported = await ok(client, "export_model", project="car")
    assert 'topspeed="120"' in exported
    await ok(client, "create_project", project="crate", kind="prop")
    assert "only vehicle" in await error(client, "set_handling", project="crate", preset="car")
    await ok(client, "create_project", project="van", kind="vehicle")
    await ok(client, "start_from_template", project="van", template="van")
    assert "Handling: van" in await ok(client, "project_summary", project="van")


def test_tool_literals_match_the_core_names() -> None:
    assert set(get_args(HandlingName)) == set(HANDLING)
    assert set(get_args(TemplateName)) == set(DESIGNS)
