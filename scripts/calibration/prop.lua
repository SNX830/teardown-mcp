#version 2
-- Buildup calibration probe for the calibration prop (milestone 0.2.0).
-- Template filled by scripts/make_calibration_mod.py: "$$name" placeholders are replaced there.
-- Read-only: it measures what the engine did with our .vox and XML and shows it on screen
-- (DebugWatch). Interpretation: docs/TESTING_IN_GAME.md, protocol C.

local VOXEL = 0.1

-- Marker voxels. O: grid corner (0, 0, 0), black; X, Y, Z: the opposite end of the grid along
-- +X (red), +Y (green), +Z (blue) of our Teardown frame (Y up, front is -Z). The rest is grey.
-- Markers are recognised by color, so the result does not depend on how the engine numbers
-- palette entries; the raw entry is shown too (our .vox indices are listed below).
local MARKER_ORDER = { "O", "X", "Y", "Z" }
local MARKER_ENTRIES = { O = $marker_o, X = $marker_x, Y = $marker_y, Z = $marker_z }

-- One entry per vox element of prop.xml: tag, label, XML pos (body frame, meters),
-- XML rot (degrees), grid size in our Teardown frame, marker cells (0-based grid indices).
local SHAPES = {
$shapes
}

local function round(value)
	return math.floor(value + 0.5)
end

local function f3(v)
	return string.format("%.3f %.3f %.3f", v[1], v[2], v[3])
end

-- Marker letter from a voxel color (components 0 to 1): "-" empty, "." grey base, "?" unknown.
local function classify(kind, r, g, b)
	if kind == "" then
		return "-"
	end
	local high = math.max(r, g, b)
	local low = math.min(r, g, b)
	if high < 0.2 then
		return "O"
	elseif r > g + 0.3 and r > b + 0.3 then
		return "X"
	elseif g > r + 0.3 and g > b + 0.3 then
		return "Y"
	elseif b > r + 0.3 and b > g + 0.3 then
		return "Z"
	elseif high - low < 0.1 then
		return "."
	end
	return "?"
end

-- Where a local axis of the shape points in body space, rounded: for example "+x" or "-z".
local function axisImage(rot, axis)
	local v = QuatRotateVec(rot, axis)
	local names = { "x", "y", "z" }
	for i = 1, 3 do
		if round(v[i]) == 1 then
			return "+" .. names[i]
		elseif round(v[i]) == -1 then
			return "-" .. names[i]
		end
	end
	return "?"
end

-- Marker letter and raw palette entry at the 8 corners of the engine's own voxel grid.
local function corners(handle, sx, sy, sz)
	local text = ""
	for _, c in ipairs({ { 0, 0, 0 }, { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 },
		{ 1, 1, 0 }, { 1, 0, 1 }, { 0, 1, 1 }, { 1, 1, 1 } }) do
		local kind, r, g, b, _, entry = GetShapeMaterialAtIndex(handle,
			c[1] * (sx - 1), c[2] * (sy - 1), c[3] * (sz - 1))
		text = text .. c[1] .. c[2] .. c[3] .. "=" .. classify(kind, r, g, b) .. entry .. " "
	end
	return text
end

-- Probe the world position where each marker voxel center should be if our conventions hold:
-- the vox origin is at XML pos, the grid's bottom center (x and z centered on size / 2, y at the
-- bottom), the XML rot is QuatEuler(rot) around that origin, and the markers sit where our
-- Teardown-frame grid puts them. (Measured 2026-10-06: the origin follows the MagicaVoxel pivot,
-- so for odd sizes these points fall on voxel boundaries; see docs/TEARDOWN_REFERENCE.md §5.)
local function probe(shape)
	local body = GetBodyTransform(GetShapeBody(shape.handle))
	local vox = Transform(shape.pos, QuatEuler(shape.rot[1], shape.rot[2], shape.rot[3]))
	local text = ""
	local all = true
	for _, name in ipairs(MARKER_ORDER) do
		local cell = shape.markers[name]
		local p = Vec((cell[1] + 0.5) * VOXEL - shape.size[1] * VOXEL / 2,
			(cell[2] + 0.5) * VOXEL,
			(cell[3] + 0.5) * VOXEL - shape.size[3] * VOXEL / 2)
		local world = TransformToParentPoint(body, TransformToParentPoint(vox, p))
		local kind, r, g, b = GetShapeMaterialAtPosition(shape.handle, world)
		local found = classify(kind, r, g, b)
		text = text .. name .. "=" .. found .. " "
		if found ~= name then
			all = false
		end
	end
	if all then
		return "OK " .. text
	end
	return "MISMATCH " .. text
end

-- Handles are searched again until found, in case the shapes are not ready at init time.
local function findShapes()
	for _, shape in ipairs(SHAPES) do
		if not shape.handle or shape.handle == 0 then
			shape.handle = FindShape(shape.tag)
		end
	end
end

function client.init()
	findShapes()
end

function client.tick()
	findShapes()
	DebugWatch("BUILDUP PROP", "calibration $version, our entries O" .. MARKER_ENTRIES.O
		.. " X" .. MARKER_ENTRIES.X .. " Y" .. MARKER_ENTRIES.Y .. " Z" .. MARKER_ENTRIES.Z)
	for _, shape in ipairs(SHAPES) do
		local label = shape.label
		if shape.handle == 0 then
			DebugWatch(label, "shape not found: " .. shape.tag)
		else
			local sx, sy, sz, scale = GetShapeSize(shape.handle)
			local t = GetShapeLocalTransform(shape.handle)
			DebugWatch(label .. " size", sx .. " " .. sy .. " " .. sz
				.. string.format(" scale %.2f", scale))
			DebugWatch(label .. " pos-xml", f3(VecSub(t.pos, shape.pos)))
			DebugWatch(label .. " axes", "x>" .. axisImage(t.rot, Vec(1, 0, 0))
				.. " y>" .. axisImage(t.rot, Vec(0, 1, 0))
				.. " z>" .. axisImage(t.rot, Vec(0, 0, 1)))
			DebugWatch(label .. " corners", corners(shape.handle, sx, sy, sz))
			DebugWatch(label .. " probe", probe(shape))
		end
	end
	-- Body axes, drawn 1 m long at the body origin (the XML body pos).
	if SHAPES[1].handle ~= 0 then
		DebugTransform(GetBodyTransform(GetShapeBody(SHAPES[1].handle)), 1.0)
	end
end
