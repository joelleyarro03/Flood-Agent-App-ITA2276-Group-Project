from flask import Blueprint, request, jsonify
from shapely.geometry import mapping
from config import DEFAULT_BBOX, FLOOD_BUFFER_METERS, TRANSTAR_POINT_BUFFER_METERS
from services.nws import flood_alert_polygons
from services.fim import fim_polygons
from services.transtar import get_transtar_points
from utils.geo import union_polygons, buffer_meters, points_buffered

bp = Blueprint("flood", __name__)

@bp.get("/flood-mask")
def flood_mask():
    """
    Returns a unioned flood polygon (alerts + fim, buffered) and TranStar buffered points.
    Response:
      { "polygon": <GeoJSON or null>, "transtar": <GeoJSON or null> }
    """
    # optional bbox query
    bbox = request.args.get("bbox")
    if bbox:
        parts = [float(x) for x in bbox.split(",")]
        bbox = tuple(parts)
    else:
        bbox = DEFAULT_BBOX

    alert_polys = flood_alert_polygons(bbox=bbox)  # list of geojson geoms
    fim_polys = fim_polygons(bbox=bbox)            # list of geojson geoms (may be empty)

    unioned = union_polygons(alert_polys + fim_polys)
    if unioned:
        unioned = buffer_meters(unioned, FLOOD_BUFFER_METERS)
        union_geojson = mapping(unioned)
    else:
        union_geojson = None

    points = get_transtar_points()
    transtar_union = points_buffered(points, TRANSTAR_POINT_BUFFER_METERS) if points else None
    transtar_geojson = mapping(transtar_union) if transtar_union else None

    return jsonify({"polygon": union_geojson, "transtar": transtar_geojson})
