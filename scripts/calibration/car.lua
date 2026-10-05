#version 2
-- Buildup calibration probe for the calibration car (milestone 0.2.0).
-- Template filled by scripts/make_calibration_mod.py: "$$name" placeholders are replaced there.
-- Read-only: it measures what the engine did with our .vox and XML and shows it on screen
-- (DebugWatch). Interpretation: docs/TESTING_IN_GAME.md, protocol C.

local VEHICLE_TAG = "$vehicle_tag"
local BODY_TAG = "$body_tag"
-- XML pos of the body vox in the body frame (meters).
local BODY_VOX_POS = $body_vox_pos
-- Wheels: tag, label, wheel center in the body frame from car.xml (meters).
local WHEELS = {
$wheels
}
local WHEEL_RADIUS = $wheel_radius
-- Locations (children of the body vox in car.xml): tag and intended position in the body frame.
-- Locations may stay fixed in the world while the body moves (the official turret.lua converts
-- them to body space once, at init), so their body-space position is computed once, at the first
-- find, right after spawning. The vehicle API gives the positions the vehicle actually uses, in
-- vehicle space (= body frame here: neither the vehicle nor the body has a pos or rot).
local LOCATIONS = {
$locations
}

local vehicle = 0
local bodyShape = 0

local function f3(v)
	return string.format("%.3f %.3f %.3f", v[1], v[2], v[3])
end

-- Handles are searched again until found, in case the entities are not ready at init time.
local function findAll()
	if vehicle == 0 then
		vehicle = FindVehicle(VEHICLE_TAG)
	end
	if bodyShape == 0 then
		bodyShape = FindShape(BODY_TAG)
	end
	for _, wheel in ipairs(WHEELS) do
		if not wheel.handle or wheel.handle == 0 then
			wheel.handle = FindShape(wheel.tag)
		end
	end
	if vehicle ~= 0 then
		for _, location in ipairs(LOCATIONS) do
			if not location.handle or location.handle == 0 then
				location.handle = FindLocation(location.tag)
				if location.handle ~= 0 then
					local body = GetBodyTransform(GetVehicleBody(vehicle))
					local p = GetLocationTransform(location.handle).pos
					location.found = VecSub(TransformToLocalPoint(body, p), location.pos)
				end
			end
		end
	end
end

-- Position used by the vehicle for a location tag, in vehicle space, or nil.
local function vehiclePos(tag)
	if tag == "player" then
		return GetVehicleDriverPos(vehicle)
	end
	local list = nil
	if tag == "exhaust" then
		list = GetVehicleExhaustTransforms(vehicle)
	elseif tag == "vital" then
		list = GetVehicleVitalTransforms(vehicle)
	end
	if list and #list > 0 then
		return list[1].pos
	end
	return nil
end

function client.init()
	findAll()
end

function client.tick()
	findAll()
	DebugWatch("BUILDUP CAR", "calibration $version")
	if vehicle == 0 or bodyShape == 0 then
		DebugWatch("CAR", "vehicle or body shape not found")
		return
	end
	local sx, sy, sz, scale = GetShapeSize(bodyShape)
	local t = GetShapeLocalTransform(bodyShape)
	DebugWatch("CAR body size", sx .. " " .. sy .. " " .. sz .. string.format(" scale %.2f", scale))
	DebugWatch("CAR body pos-xml", f3(VecSub(t.pos, BODY_VOX_POS)))

	local bodyTransform = GetBodyTransform(GetVehicleBody(vehicle))
	DebugTransform(bodyTransform, 1.0)
	for _, wheel in ipairs(WHEELS) do
		if wheel.handle == 0 then
			DebugWatch("CAR " .. wheel.label, "shape not found: " .. wheel.tag)
		else
			-- The wheel grid is a disc centered on its box, so the box center is the axle even
			-- while the wheel spins.
			local low, high = GetShapeBounds(wheel.handle)
			local center = VecLerp(low, high, 0.5)
			local offset = VecSub(TransformToLocalPoint(bodyTransform, center), wheel.pos)
			-- Ground height under the axle, ignoring the car and this wheel.
			QueryRejectVehicle(vehicle)
			QueryRejectShape(wheel.handle)
			local origin = Vec(center[1], high[2] + 0.05, center[3])
			local hit, dist = QueryRaycast(origin, Vec(0, -1, 0), 5)
			local gap = "no ground"
			if hit then
				local ground = origin[2] - dist
				local cm = math.floor((center[2] - WHEEL_RADIUS - ground) * 100 + 0.5)
				gap = string.format("%+d cm", cm)
			end
			DebugWatch("CAR " .. wheel.label, "axle-xml " .. f3(offset) .. " | gap " .. gap)
		end
	end
	for _, location in ipairs(LOCATIONS) do
		local text = "entity not found"
		if location.found then
			text = "entity " .. f3(location.found)
		end
		local used = vehiclePos(location.tag)
		if used then
			text = text .. " | vehicle " .. f3(VecSub(used, location.pos))
		else
			text = text .. " | vehicle none"
		end
		DebugWatch("CAR loc " .. location.tag, text)
	end
end
