# backend/routes/hospital.py
from flask import Blueprint, request, jsonify
import math
from shapely.geometry import Point, mapping

from services.overpass import get_hospitals
from services.osrm import full_route, distance_km
from services.alerts import get_active_flood_polygons 
from services.fim import get_fim_polygons           
from services.transtar import get_transtar_points   

from utils.geo import (
    union_polygons,
    buffer_meters,
    haversine_km,
    line_intersects_polygons,
    line_near_points,
    points_buffered,
)

bp = Blueprint("hospital", __name__)

# ---------- small helpers ----------
def _bearing_deg(lat1, lon1, lat2, lon2):
    """Initial bearing from (lat1,lon1) -> (lat2,lon2), degrees [0,360)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    theta = math.degrees(math.atan2(y, x))
    return (theta + 360.0) % 360.0

def _dest_point(lat, lon, bearing_deg, dist_m):
    """Destination lat/lon given start, bearing (deg), and distance (meters)."""
    R = 6_371_000.0
    delta = dist_m / R
    theta = math.radians(bearing_deg)
    phi1, lam1 = math.radians(lat), math.radians(lon)
    sin_phi1, cos_phi1 = math.sin(phi1), math.cos(phi1)
    sin_delta, cos_delta = math.sin(delta), math.cos(delta)

    sin_phi2 = sin_phi1 * cos_delta + cos_phi1 * sin_delta * math.cos(theta)
    phi2 = math.asin(sin_phi2)
    y = math.sin(theta) * sin_delta * cos_phi1
    x = cos_delta - sin_phi1 * sin_phi2
    lam2 = lam1 + math.atan2(y, x)
    lat2 = math.degrees(phi2)
    lon2 = (math.degrees(lam2) + 540) % 360 - 180
    return lat2, lon2

def _initial_heading_from_route_geojson(route_geojson):
    """
    Get heading (deg) from the first useful segment of a GeoJSON LineString.
    Returns None if geometry is too short.
    """
    try:
        coords = route_geojson["coordinates"]
    except Exception:
        return None
    if not coords or len(coords) < 2:
        return None
    # coords are [lon, lat]
    lon1, lat1 = coords[0]
    # find the first point far enough to avoid noise
    for i in range(1, min(6, len(coords))):
        lon2, lat2 = coords[i]
        if abs(lat2 - lat1) + abs(lon2 - lon1) > 1e-5:  # ~ few meters
            return _bearing_deg(lat1, lon1, lat2, lon2)
    # fallback to second point
    lon2, lat2 = coords[1]
    return _bearing_deg(lat1, lon1, lat2, lon2)

# ---------- main endpoint ----------
@bp.get("/nearest-hospital")
def nearest_hospital():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except Exception:
        return jsonify({"error": "lat/lon required"}), 400

    try:
        radius_km = float(request.args.get("radius_km", 20))
    except Exception:
        radius_km = 20.0
    radius_km = max(1.0, min(radius_km, 50.0))  # clamp

    # risk tube around route for proximity checks to point sensors
    tube_m = int(request.args.get("tube_m", 75))
    # simulation params
    simulate = request.args.get("simulate", "0") == "1"
    sim_radius_m = int(request.args.get("sim_radius_m", 600))
    sim_offset_m = int(request.args.get("sim_offset_m", 20))
    sim_lat_q = request.args.get("sim_lat")
    sim_lon_q = request.args.get("sim_lon")

    origin = (lat, lon)

    # 1) fetch hospitals (OSM/Overpass)
    try:
        hospitals = get_hospitals(lat, lon, radius_km)
    except Exception as e:
        print("[OVERPASS ERROR]", e)
        hospitals = []

    if not hospitals:
        return jsonify({
            "origin": {"lat": lat, "lon": lon},
            "best": None,
            "route": None,
            "radius_km": radius_km,
            "warning": "No hospitals found in the area. Try increasing the radius.",
            "sim_polygon": None
        })

    # shortlist by straight-line distance for speed
    hospitals.sort(key=lambda h: haversine_km(origin, (h["lat"], h["lon"])))
    candidates = hospitals[:10]

    # 2) base flood mask (alerts + optional FIM)
    alert_polys = get_active_flood_polygons() or []
    fim_polys = get_fim_polygons() or []
    mask = union_polygons(alert_polys + fim_polys)
    if mask:
        mask = buffer_meters(mask, 100)  # be conservative

    # TranStar: buffered points and raw points (for near-line checks)
    transtar_pts = get_transtar_points() or []        # [(lat,lon), ...]
    transtar_buffer = points_buffered(transtar_pts, tube_m) if transtar_pts else None

    # 3) Option 2 simulation logic (route-based tangent)
    sim_polygon = None
    if simulate:
        # 3a) if explicit sim center provided, honor it
        if sim_lat_q is not None and sim_lon_q is not None:
            try:
                s_lat = float(sim_lat_q); s_lon = float(sim_lon_q)
                sim_polygon = buffer_meters(Point(s_lon, s_lat), sim_radius_m)
            except Exception:
                sim_polygon = None
        else:
            # 3b) otherwise, compute a PRELIM route (ignoring simulation), get initial heading,
            # and place circle tangent to the origin tube along that heading.
            prelim_route = None
            prelim_h = None

            # pick the first candidate for which OSRM returns a route (by haversine order)
            for h in candidates:
                rt = full_route(origin, (h["lat"], h["lon"]))
                if rt and rt.get("geometry"):
                    prelim_route = rt["geometry"]
                    prelim_h = h
                    break

            if prelim_route:
                heading = _initial_heading_from_route_geojson(prelim_route)
            else:
                heading = None

            if heading is None:
                # fallback to bearing toward nearest candidate center if route heading unknown
                h0 = prelim_h or candidates[0]
                heading = _bearing_deg(lat, lon, h0["lat"], h0["lon"])

            center_dist_m = tube_m + sim_radius_m + sim_offset_m
            c_lat, c_lon = _dest_point(lat, lon, heading, center_dist_m)
            sim_polygon = buffer_meters(Point(c_lon, c_lat), sim_radius_m)

    # 4) Merge simulated flood + transtar buffer into mask
    if sim_polygon is not None:
        mask = sim_polygon if mask is None else mask.union(sim_polygon)
    if transtar_buffer is not None:
        mask = transtar_buffer if mask is None else mask.union(transtar_buffer)

    # 5) Evaluate candidates with mask: pick first route that avoids polygons + near points
    chosen = None
    chosen_route = None
    warning = None

    best_by_road = None   # fallback: closest by road if all unsafe
    best_by_road_rt = None

    for h in candidates:
        rt = full_route(origin, (h["lat"], h["lon"]))
        if not rt or not rt.get("geometry"):
            continue

        # remember best by road distance
        if not best_by_road_rt or rt["distance_km"] < best_by_road_rt["distance_km"]:
            best_by_road = h
            best_by_road_rt = rt

        geom = rt["geometry"]  # GeoJSON LineString

        # polygon avoid (alerts/FIM + sim + transtar buffer area)
        crosses_poly = line_intersects_polygons(geom, mask) if mask is not None else False

        # near point sensors (raw points) within tube_m
        near_sensors = False
        if transtar_pts:
            # line_near_points accepts shapely Points or (lat,lon) tuples; we pass tuples
            near_sensors = line_near_points(geom, transtar_pts, meters=tube_m)

        if not crosses_poly and not near_sensors:
            chosen = h
            chosen_route = rt
            break

    if not chosen:
        # fallback to best-by-road, warn user
        chosen = best_by_road
        chosen_route = best_by_road_rt
        if chosen:
            warning = "No fully clear route found. Route may cross areas under flood or near sensors."

    resp = {
        "origin": {"lat": lat, "lon": lon},
        "best": chosen,
        "route": chosen_route,
        "radius_km": radius_km,
        "warning": warning,
        "sim_polygon": mapping(sim_polygon) if sim_polygon is not None else None
    }
    return jsonify(resp)
