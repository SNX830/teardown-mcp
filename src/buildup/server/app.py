"""The Buildup MCP server: thin tool wrappers over ``buildup.project``, ``render`` and ``teardown``.

Tool docstrings and argument descriptions are what the AI user reads (AGENTS.md §6): they state
units, ranges and examples. Errors the AI can fix are raised as ``ToolError`` (shown to it);
anything else is a bug and is logged with its traceback.
"""

import io
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Final, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import TextContent, ToolAnnotations
from pydantic import BaseModel, Field

from buildup import __version__
from buildup.palette import PaletteError
from buildup.project import (
    WORLD_MAX,
    WORLD_MIN,
    Axle,
    Project,
    ProjectError,
    ProjectStore,
    Shape,
    WheelLayout,
    box_shape,
    clip_to_world,
    cylinder_shape,
    default_mod_name,
    edge_cut_shape,
    ellipsoid_shape,
    export_project,
    wedge_shape,
)
from buildup.render import (
    DEFAULT_VIEWS,
    Annotations,
    Marker,
    as_view,
    ascii_slices,
    describe,
    preview_sheet,
)
from buildup.server import text
from buildup.teardown import AssemblyError, reference
from buildup.voxcore import VoxcoreError
from buildup.voxio import VoxFormatError

logger = logging.getLogger(__name__)

#: Errors caused by the arguments or the state of a project: the AI reads the message and can
#: fix the call. Every other exception is a bug.
USER_ERRORS: Final = (ProjectError, VoxcoreError, PaletteError, AssemblyError, VoxFormatError)

MAX_SLICES: Final = 8

INSTRUCTIONS: Final = """\
Buildup builds Teardown voxel models (vehicles and props) and exports a ready-to-test mod folder.

Model frame (used by every tool): Teardown's frame, X = right, Y = up, front of a vehicle = -Z,
in voxels (1 voxel = 0.1 m). Convention: ground at Y = 0, center line at X = 0. Boxes use
start (inclusive) and end (exclusive) cells: start [0, 0, 0], end [10, 5, 20] fills 10 x 5 x 20
voxels; points (centers, anchors) are continuous coordinates (voxel i spans i to i + 1).

Workflow: create_project -> define_color (materials decide physics) -> add_part + draw_* tools
-> add_wheels -> set_anchor (player, vital, exhaust) -> preview / inspect (look at the images:
the views are true views, the front view shows the model's right side on the image left) ->
export_model -> write info.txt and spawn.txt. Read teardown_reference('workflow') first, and
teardown_reference('vehicle_xml') before editing XML. Every edit can be undone with undo.
"""

ProjectName = Annotated[str, Field(description="Project name, for example 'red_pickup'.")]
PartName = Annotated[str, Field(description="Part name, for example 'body' or 'wheel_fl'.")]
Cell = tuple[int, int, int]
StartCell = Annotated[
    Cell, Field(description="First cell [x, y, z] in voxels (inclusive), model frame.")
]
EndCell = Annotated[
    Cell,
    Field(description="Cell after the last one [x, y, z] (exclusive): end - start is the size."),
]
ColorName = Annotated[
    str | None,
    Field(description="Color name from define_color; required for modes 'add' and 'paint'."),
]
Mode = Literal["add", "paint", "carve"]
ModeArg = Annotated[
    Mode,
    Field(
        description="'add' fills the shape with the color (replacing voxels there, growing the "
        "part); 'paint' recolors only the part's existing voxels inside the shape; 'carve' "
        "removes the part's voxels inside the shape."
    ),
]
FaceName = Literal["left", "right", "bottom", "top", "front", "back"]
MaterialName = Literal[
    "glass",
    "grass",
    "dirt",
    "rock",
    "wood",
    "concrete",
    "brick",
    "plaster",
    "weak metal",
    "heavy metal",
    "plastic",
    "hard metal",
    "hard masonry",
    "unphysical",
]
ViewName = Literal["front", "back", "left", "right", "top", "bottom", "iso_front", "iso_back"]
Topic = Literal["workflow", "frame", "materials", "vehicle_xml", "prop_xml", "mod_files"]

READ_ONLY: Final = ToolAnnotations(read_only_hint=True, open_world_hint=False)
EDIT: Final = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
#: Edits that delete or overwrite (undo can bring a removed part back, not an undone edit).
DESTRUCTIVE: Final = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, open_world_hint=False
)
#: Reads the model and writes preview.png (a regenerated output) in the project folder.
RENDER: Final = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class AxleSpec(BaseModel):
    """One axle: a left and a right wheel at the same Z."""

    z: int = Field(description="Z of the axle in voxels (front axles have negative Z).")
    steer: bool = Field(default=False, description="Whether these wheels steer (front axle).")
    drive: bool = Field(default=False, description="Whether the engine drives these wheels.")


@contextmanager
def user_errors() -> Iterator[None]:
    """Turn the errors an AI can fix into ``ToolError`` (shown to the AI)."""
    try:
        yield
    except USER_ERRORS as error:
        raise ToolError(str(error)) from error
    except OSError as error:  # a file busy or not writable: worth telling the AI and the user
        raise ToolError(f"file error: {error}; the project was not changed, try again") from error


class Context:
    """What every tool needs: the project store, the mods folder and the edit lock.

    Args:
        workspace: Folder for projects (``workspace/projects``) and exported mods
            (``workspace/mods``). Never the game's mods folder (decision D-010).
    """

    def __init__(self, workspace: Path) -> None:
        self.store = ProjectStore(workspace)
        self.mods_dir = workspace / "mods"
        # Tools run in worker threads and hosts call them in parallel; every access to project
        # files holds this lock (re-entrant, so a locked tool may call ``read``).
        self.lock = threading.RLock()

    def edit(self, project: str, action: str, change: Callable[[Project], str]) -> str:
        """Apply ``change`` to a project and save it with an undo step, if it succeeds."""
        with self.lock, user_errors(), self.store.edit(project, action) as loaded:
            return change(loaded)

    def read(self, project: str) -> Project:
        """Load a project (errors become ``ToolError``)."""
        with self.lock, user_errors():
            return self.store.load(project)


def draw_result(
    project: Project, part: str, shapes: list[Shape], mode: str, color: str | None
) -> str:
    """Apply shapes to a part and describe the result, noting shapes cut at model space limits."""
    changed = sum(project.draw(part, shape, mode, color) for shape in shapes)
    result = text.edit_result(project.part(part), changed)
    if any(clip_to_world(s.start, s.end) != (s.start, s.end) for s in shapes):
        result += (
            f" Note: the shape's bounding box went beyond model space ({WORLD_MIN} to "
            f"{WORLD_MAX - 1} voxels on every axis); any part of the shape beyond it was cut."
        )
    return result


def create_server(workspace: Path) -> MCPServer:
    """Build the MCP server.

    Args:
        workspace: Folder for projects (``workspace/projects``) and exported mods
            (``workspace/mods``). Never the game's mods folder (decision D-010).
    """
    ctx = Context(workspace)
    mcp = MCPServer("buildup", instructions=INSTRUCTIONS, version=__version__)
    for register in (
        _project_tools,
        _drawing_tools,
        _assembly_tools,
        _inspection_tools,
        _export_tools,
    ):
        register(mcp, ctx)
    return mcp


def _project_tools(mcp: MCPServer, ctx: Context) -> None:
    """Projects, colors and parts."""

    @mcp.tool(annotations=EDIT, structured_output=False)
    def create_project(
        project: ProjectName,
        kind: Annotated[
            Literal["vehicle", "prop"],
            Field(description="'vehicle' (a body with wheels) or 'prop' (one dynamic object)."),
        ] = "vehicle",
        description: Annotated[str, Field(description="Free text: what is being built.")] = "",
    ) -> str:
        """Create an empty modelling project, saved in the workspace.

        Names: 1-40 lower-case letters, digits or '_', starting with a letter.
        Next: define_color, then add_part and the draw_* tools.
        """
        with ctx.lock, user_errors():
            created = ctx.store.create(project, kind, description)
        return f"Created project {created.name!r} ({created.kind}) in {ctx.store.folder(project)}."

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    def list_projects() -> str:
        """List the projects of the workspace."""
        names = ctx.store.names()
        if not names:
            return f"No projects yet in {ctx.store.projects_dir}. Use create_project."
        return "Projects: " + ", ".join(names)

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    def project_summary(project: ProjectName) -> str:
        """Show a project's colors, parts (extent in voxels and meters), wheels and anchors."""
        with ctx.lock, user_errors():
            loaded = ctx.read(project)
            steps = len(ctx.store.history(project))
        return text.project_summary(loaded, ctx.store.folder(project), steps)

    @mcp.tool(annotations=DESTRUCTIVE, structured_output=False)
    def undo(
        project: ProjectName,
        steps: Annotated[int, Field(ge=1, le=100, description="Edits to revert.")] = 1,
    ) -> str:
        """Revert the last edits of a project (any tool that changed it). Cannot be redone."""
        with ctx.lock, user_errors():
            undone = ctx.store.undo(project, steps)
        return f"Reverted {len(undone)} edit(s), most recent first: " + "; ".join(undone)

    # --- Colors and parts ----------------------------------------------------------------

    @mcp.tool(annotations=EDIT, structured_output=False)
    def define_color(
        project: ProjectName,
        name: Annotated[str, Field(description="Color name, for example 'body_paint'.")],
        material: Annotated[
            MaterialName,
            Field(description="Physical material in game (decides strength and behaviour)."),
        ],
        rgb: Annotated[
            tuple[int, int, int], Field(description="Displayed color [red, green, blue], 0-255.")
        ],
        finish: Annotated[
            Literal["auto", "matte", "metal", "glass", "emissive"],
            Field(
                description="Rendering only: 'auto' = glass finish for glass (like official "
                "windows), matte otherwise; 'emissive' glows (lights)."
            ),
        ] = "auto",
    ) -> str:
        """Define a named color: a material plus a displayed color, used by the drawing tools.

        In Teardown the material decides how a voxel breaks; the color is only its look.
        Typical: body paint 'weak metal' (official cars), windows 'glass', lights finish
        'emissive'. Redefining an existing name changes its rgb/finish everywhere it is used
        (its material cannot change). Each material has 8 or 16 color slots.
        Example: name 'body_paint', material 'weak metal', rgb [180, 30, 30].
        """

        def change(p: Project) -> str:
            c = p.define_color(name, material, rgb, finish)
            return (
                f"Color {c.name!r}: {c.material.value}, rgb{c.rgb}, {c.finish.kind.value} "
                f"(palette index {c.index})."
            )

        return ctx.edit(project, f"define_color {name}", change)

    @mcp.tool(annotations=EDIT, structured_output=False)
    def add_part(project: ProjectName, name: PartName) -> str:
        """Add an empty part to the body (one named object in the .vox file).

        Use one part for the main body; separate parts only for pieces that are separate
        objects in the XML. Draw into it with the draw_* tools; its size follows its voxels.
        """

        def change(p: Project) -> str:
            part = p.add_part(name)
            return f"Added empty part {part.name!r}. Draw into it with draw_box and the others."

        return ctx.edit(project, f"add_part {name}", change)

    @mcp.tool(annotations=DESTRUCTIVE, structured_output=False)
    def remove_part(project: ProjectName, part: PartName) -> str:
        """Delete a part and all its voxels (undo brings it back)."""

        def change(p: Project) -> str:
            p.remove_part(part)
            return f"Removed part {part!r}."

        return ctx.edit(project, f"remove_part {part}", change)


def _drawing_tools(mcp: MCPServer, ctx: Context) -> None:
    """Shapes drawn into parts."""

    @mcp.tool(annotations=EDIT, structured_output=False)
    def draw_box(
        project: ProjectName,
        part: PartName,
        start: StartCell,
        end: EndCell,
        color: ColorName = None,
        mode: ModeArg = "add",
    ) -> str:
        """Add, paint or carve a rectangular block of cells start <= cell < end.

        Example: a body 1.6 m wide, 0.6 m high and 4.0 m long, 0.3 m above the ground, front at
        -Z: start [-8, 3, -20], end [8, 9, 20] (16 x 6 x 40 voxels).
        Carve a cabin interior or wheel arches with mode 'carve'.
        """
        with user_errors():
            shape = box_shape(start, end)
        return ctx.edit(
            project,
            f"draw_box {mode} on {part}",
            lambda p: draw_result(p, part, [shape], mode, color),
        )

    @mcp.tool(annotations=EDIT, structured_output=False)
    def draw_cylinder(
        project: ProjectName,
        part: PartName,
        axis: Annotated[
            Literal["x", "y", "z"],
            Field(description="Cylinder axis: 'x' across the vehicle, 'y' vertical, 'z' along."),
        ],
        center: Annotated[
            tuple[float, float],
            Field(
                description="Axis position on the two other axes, in x, y, z order (for axis "
                "'x': [y, z]). Whole numbers for an even diameter, n + 0.5 for an odd one."
            ),
        ],
        radius: Annotated[
            float, Field(gt=0, le=128, description="Radius in voxels (voxel centers inside).")
        ],
        span: Annotated[
            tuple[int, int],
            Field(description="First cell and the cell after the last one along the axis."),
        ],
        color: ColorName = None,
        mode: ModeArg = "add",
    ) -> str:
        """Add, paint or carve a cylinder (pipes, headlights, exhausts, round details).

        Example: an exhaust pipe along Z, 2 voxels across, at x = 5.0, y = 4.0, from z = 20 to
        24: axis 'z', center [5, 4], radius 1, span [20, 24].
        Wheels: use add_wheels instead.
        """
        with user_errors():
            shape = cylinder_shape(axis, center, radius, span)
        return ctx.edit(
            project,
            f"draw_cylinder {mode} on {part}",
            lambda p: draw_result(p, part, [shape], mode, color),
        )

    @mcp.tool(annotations=EDIT, structured_output=False)
    def draw_ellipsoid(
        project: ProjectName,
        part: PartName,
        center: Annotated[
            tuple[float, float, float],
            Field(description="Center [x, y, z] in voxels (continuous coordinates)."),
        ],
        radii: Annotated[
            tuple[float, float, float],
            Field(description="Half sizes [rx, ry, rz] in voxels; equal values make a sphere."),
        ],
        color: ColorName = None,
        mode: ModeArg = "add",
    ) -> str:
        """Add, paint or carve an ellipsoid or a sphere (voxel centers inside the surface).

        Example: a dome 1.2 m wide, 0.4 m high, 2 m long on a roof whose top is y = 14:
        center [0, 14, 0], radii [6, 4, 10] (the lower half lands inside the roof).
        """
        with user_errors():
            shape = ellipsoid_shape(center, radii)
        return ctx.edit(
            project,
            f"draw_ellipsoid {mode} on {part}",
            lambda p: draw_result(p, part, [shape], mode, color),
        )

    @mcp.tool(annotations=EDIT, structured_output=False)
    def draw_wedge(
        project: ProjectName,
        part: PartName,
        start: StartCell,
        end: EndCell,
        faces: Annotated[
            tuple[FaceName, FaceName],
            Field(
                description="The block edge that is cut away, as two faces on different axes: "
                "left (-X), right (+X), bottom (-Y), top (+Y), front (-Z), back (+Z)."
            ),
        ],
        color: ColorName = None,
        mode: ModeArg = "add",
    ) -> str:
        """Add, paint or carve a ramp: the block start..end cut diagonally across its extent.

        The edge between faces[0] and faces[1] is removed as deep as the block goes. Example: a
        hood sloping down to the front, full height at the back: faces ['top', 'front'].
        """
        with user_errors():
            shape = wedge_shape(start, end, faces)
        return ctx.edit(
            project,
            f"draw_wedge {mode} on {part}",
            lambda p: draw_result(p, part, [shape], mode, color),
        )

    @mcp.tool(annotations=EDIT, structured_output=False)
    def cut_edges(
        project: ProjectName,
        part: PartName,
        start: StartCell,
        end: EndCell,
        edges: Annotated[
            list[tuple[FaceName, FaceName]],
            Field(
                min_length=1,
                max_length=12,
                description="Edges of the block start..end, each as two faces, e.g. "
                "[['top', 'front'], ['top', 'back']].",
            ),
        ],
        depths: Annotated[
            tuple[float, float],
            Field(
                description="How far each cut goes into the block from the first and from the "
                "second face of each edge, in voxels (equal values: 45 degrees)."
            ),
        ],
        mode: Annotated[
            Literal["carve", "paint"],
            Field(description="'carve' removes the cut voxels; 'paint' recolors them."),
        ] = "carve",
        color: ColorName = None,
    ) -> str:
        """Bevel or slope edges of a block of the part (windshields, hoods, rounded roofs).

        A voxel is cut when d1 / depths[0] + d2 / depths[1] < 1, d being the distance from its
        center to each face. Example: windshield slope on a cabin start [-8, 9, -6], end
        [8, 15, 10]: edges [['top', 'front']], depths [5, 6] (5 voxels down, 6 back).
        """
        with user_errors():
            shapes = [edge_cut_shape(start, end, pair, depths) for pair in edges]

        return ctx.edit(
            project,
            f"cut_edges {mode} on {part}",
            lambda p: draw_result(p, part, shapes, mode, color),
        )


def _assembly_tools(mcp: MCPServer, ctx: Context) -> None:
    """Whole-part operations, wheels and anchors."""

    @mcp.tool(annotations=EDIT, structured_output=False)
    def mirror_part(
        project: ProjectName,
        part: PartName,
        keep: Annotated[
            Literal["left", "right"],
            Field(description="Side copied onto the other: 'left' = X below the plane."),
        ] = "left",
        plane_x: Annotated[
            float, Field(description="X of the mirror plane (whole or half voxel).")
        ] = 0,
    ) -> str:
        """Make a body part left-right symmetric: copy one side, mirrored, over the other side.

        With the default plane X = 0, a body spanning X -8..8 stays -8..8. Model details on the
        left side, then mirror. Voxels on the replaced side are discarded. Wheel parts cannot be
        mirrored (add_wheels already makes both sides).
        """

        def change(p: Project) -> str:
            p.mirror(part, keep, plane_x)
            return f"Mirrored. Part now: {text.part_line(p.part(part))}."

        return ctx.edit(project, f"mirror_part {part}", change)

    @mcp.tool(annotations=EDIT, structured_output=False)
    def hollow_part(
        project: ProjectName,
        part: PartName,
        thickness: Annotated[int, Field(ge=1, le=16, description="Shell thickness in voxels.")] = 1,
    ) -> str:
        """Empty the inside of a part, keeping a shell (fewer voxels, interiors).

        The shell stays joined by faces on slopes and curves. Carve openings (doors, windows)
        afterwards if needed.
        """

        def change(p: Project) -> str:
            removed = p.hollow(part, thickness)
            return f"Removed {removed} inner voxels. Part now: {text.part_line(p.part(part))}."

        return ctx.edit(project, f"hollow_part {part}", change)

    @mcp.tool(annotations=EDIT, structured_output=False)
    def move_part(
        project: ProjectName,
        part: PartName,
        offset: Annotated[Cell, Field(description="Shift [dx, dy, dz] in voxels.")],
    ) -> str:
        """Move a part (a wheel's axle moves with it; anchors stay where they are)."""

        def change(p: Project) -> str:
            p.move(part, offset)
            return f"Moved. Part now: {text.part_line(p.part(part))}."

        return ctx.edit(project, f"move_part {part}", change)

    @mcp.tool(annotations=EDIT, structured_output=False)
    def add_wheels(
        project: ProjectName,
        axles: Annotated[
            list[AxleSpec],
            Field(
                min_length=1,
                max_length=4,
                description="Axles, any order; usually front [z<0, steer] and back [z>0, drive].",
            ),
        ],
        diameter: Annotated[
            int,
            Field(ge=4, le=64, description="Even number of voxels; the calibration car used 8."),
        ],
        width: Annotated[int, Field(ge=1, le=32, description="Wheel width along X (voxels).")],
        inner_x: Annotated[
            int,
            Field(
                ge=0,
                description="Distance from X = 0 to the inner face of each wheel: half the "
                "body width + 1 leaves a 1-voxel gap outside the body (as on the car verified "
                "in game).",
            ),
        ],
        tire_color: Annotated[str, Field(description="Color name of the tire.")],
        rim_color: Annotated[
            str | None, Field(description="Color name of the rim (center); default: tire.")
        ] = None,
        axle_height: Annotated[
            int | None,
            Field(description="Y of the axles; default diameter / 2 (wheels touch Y = 0)."),
        ] = None,
    ) -> str:
        """Add a left and a right wheel per axle, as separate parts with axle data for the XML.

        Wheels are cylinders along X named wheel_fl, wheel_fr, wheel_bl, wheel_br (f = front,
        b = back, l = left -X, r = right +X; 1 axle: m, 3 axles: f, m, b; 4: f, m1, m2, b).
        Example for a body 16 voxels wide and 40 long: axles [{z: -13, steer: true},
        {z: 13, drive: true}], diameter 8, width 2, inner_x 9 (wheels at X -11..-9 and 9..11).
        The body must not overlap the wheels: raise the body or carve wheel arches.
        """
        layout = WheelLayout(diameter, width, inner_x, axle_height)

        def change(p: Project) -> str:
            specs = [Axle(a.z, a.steer, a.drive) for a in axles]
            created = p.add_wheels(specs, layout, tire_color, rim_color)
            return "Added wheels:\n" + "\n".join(f"  {text.part_line(w)}" for w in created)

        return ctx.edit(project, "add_wheels", change)

    @mcp.tool(annotations=EDIT, structured_output=False)
    def set_anchor(
        project: ProjectName,
        name: Annotated[
            str,
            Field(
                description="'player' (driver), 'vital', 'exhaust' become vehicle locations "
                "in the skeleton; other names are only exported in the manifest."
            ),
        ],
        position: Annotated[
            tuple[float, float, float] | None,
            Field(description="Point [x, y, z] in voxels (continuous); null deletes the anchor."),
        ],
    ) -> str:
        """Set a named point of the model (driver position, exhaust, lights...).

        Official vehicles use player (the driver is shown near it; official cars put it on the
        left, negative X), vital (meaning not documented) and exhaust (exhaust smoke comes out
        there, verified in game). Anchors stay put when parts move. Example: player [-4, 9, 2].
        """

        def change(p: Project) -> str:
            p.set_anchor(name, position)
            if position is None:
                return f"Deleted anchor {name!r}."
            return f"Anchor {name!r} at {text.point_text(p.anchors[name])}."

        return ctx.edit(project, f"set_anchor {name}", change)


def _inspection_tools(mcp: MCPServer, ctx: Context) -> None:
    """Previews, text descriptions and slices (read only)."""

    @mcp.tool(annotations=RENDER)
    def preview(
        project: ProjectName,
        part: Annotated[
            str | None, Field(description="Only this part; default: the whole model.")
        ] = None,
        views: Annotated[
            list[ViewName] | None,
            Field(description="Panels to draw; default: front, left, top, back and two 3/4."),
        ] = None,
    ) -> list[Image | TextContent]:
        """Render the model as an image with several annotated views. Look at it after edits.

        Orthographic views are true views from outside: the front view (camera at -Z) shows the
        model's right side (+X) on the image LEFT; each panel names the side every image edge
        shows. Rulers are model-frame meters. Magenta markers: wheel axles and anchors.
        The image is also saved as preview.png in the project folder.
        """
        loaded = ctx.read(project)
        with user_errors():
            composed = loaded.composed(part)
            if composed is None:
                raise ProjectError(f"nothing to preview: {part or 'the model'} has no voxels")
            grid, origin = composed
            end = [origin[i] + grid.shape[i] for i in range(3)]
            markers = tuple(
                Marker(label, point)
                for label, point in loaded.markers()
                if all(origin[i] <= point[i] <= end[i] for i in range(3))
            )
            title = f"{loaded.name}" + (f" / part {part}" if part else "")
            image = preview_sheet(
                grid,
                loaded.palette().rgba(),
                origin=origin,
                views=[as_view(v) for v in views] if views else DEFAULT_VIEWS,
                annotations=Annotations(title=title, markers=markers),
            )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        png = buffer.getvalue()
        path = ctx.store.folder(project) / "preview.png"
        with ctx.lock, user_errors():
            path.write_bytes(png)
        hidden = len(loaded.markers()) - len(markers)
        caption = f"Preview of {title}: {image.width} x {image.height} px, saved to {path}." + (
            f" {hidden} marker(s) outside the shown voxels are not drawn." if hidden else ""
        )
        return [Image(data=png, format="png"), TextContent(type="text", text=caption)]

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    def inspect(
        project: ProjectName,
        part: Annotated[
            str | None, Field(description="Only this part; default: the whole model.")
        ] = None,
    ) -> str:
        """Describe the model in text: sizes, materials, colors and connectivity.

        Gives the size in voxels and meters, the filled extent, voxel counts per material and
        palette index, and the face-connected pieces (voxels touching only by edges or corners
        may fall apart when damaged in game).
        """
        with ctx.lock, user_errors():
            loaded = ctx.read(project)
            composed = loaded.composed(part)
            header = (
                text.part_line(loaded.part(part))
                if part
                else text.project_summary(
                    loaded, ctx.store.folder(project), len(ctx.store.history(project))
                )
            )
            if composed is None:
                return header + "\nNo voxels yet."
            grid, origin = composed
            body = describe(grid, origin=origin, palette=loaded.palette())
        note = (
            ""
            if part
            else "\n(Whole model: parts are merged, so connectivity counts every part; wheels "
            "are separate pieces by design. Inspect a single part to check it.)"
        )
        return f"{header}\n\n{body}\n{text.color_legend(loaded)}{note}"

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    def slice_layers(
        project: ProjectName,
        axis: Annotated[
            Literal["x", "y", "z"],
            Field(
                description="'y': horizontal layers seen from above (front at the top, +X on "
                "the right); 'z': cross-sections seen from the front (+X, the right side, on "
                "the LEFT); 'x': side sections seen from the left (front on the left)."
            ),
        ],
        positions: Annotated[
            list[int],
            Field(min_length=1, max_length=MAX_SLICES, description="Layer coordinates (voxels)."),
        ],
        part: Annotated[
            str | None, Field(description="Only this part; default: the whole model.")
        ] = None,
    ) -> str:
        """Print layers of the model as text grids, one symbol per voxel ('.' = empty).

        Rows and columns are labelled with model-frame voxel coordinates; the legend gives the
        palette index and material of each symbol.
        """
        loaded = ctx.read(project)
        a = "xyz".index(axis)
        with user_errors():
            composed = loaded.composed(part)
            if composed is None:
                raise ProjectError(f"nothing to slice: {part or 'the model'} has no voxels")
            grid, origin = composed
            low, high = origin[a], origin[a] + grid.shape[a] - 1
            outside = [v for v in positions if not low <= v <= high]
            if outside:
                raise ProjectError(
                    f"layers {outside} are outside the voxels: {axis} goes from {low} to {high}"
                )
            body = ascii_slices(grid, axis, [v - origin[a] for v in positions], origin=origin)
        return f"{body}\n{text.color_legend(loaded)}"


def _export_tools(mcp: MCPServer, ctx: Context) -> None:
    """Export and reference."""

    @mcp.tool(annotations=DESTRUCTIVE, structured_output=False)
    def export_model(
        project: ProjectName,
        mod_name: Annotated[
            str | None,
            Field(
                description="Mod folder and display name (Latin letters, digits, spaces); "
                "default: from the project name ('red_pickup' -> 'Red Pickup')."
            ),
        ] = None,
        skeleton: Annotated[
            Literal["if_missing", "overwrite", "never"],
            Field(
                description="When to write prefab/<project>.xml from the skeleton: only if "
                "missing (default, keeps your edits), always, or never."
            ),
        ] = "if_missing",
    ) -> str:
        """Export the model as a mod folder: .vox file, manifest (JSON) and XML skeleton.

        Writes workspace/mods/<mod name>/ (the user copies it into the game's mods folder).

        Reports the XML positions of every object, wheel and anchor, and warnings (missing
        anchors, overlapping parts, pieces that may fall apart). Then write info.txt and
        spawn.txt (teardown_reference 'mod_files').
        """
        with ctx.lock, user_errors():
            loaded = ctx.read(project)
            result = export_project(
                loaded,
                project_folder=ctx.store.folder(project),
                mods_dir=ctx.mods_dir,
                mod_name=mod_name or default_mod_name(loaded.name),
                skeleton=skeleton,
            )
        return text.export_summary(result)

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    def teardown_reference(
        topic: Annotated[
            Topic,
            Field(
                description="'workflow' (steps to build a vehicle), 'frame' (coordinates and "
                "XML positions), 'materials', 'vehicle_xml', 'prop_xml', 'mod_files' "
                "(info.txt, spawn.txt, folders)."
            ),
        ],
    ) -> str:
        """Teardown facts needed to write the mod's XML and text files.

        Each fact says whether it is verified in game or only seen in official files.
        """
        return reference(topic)
