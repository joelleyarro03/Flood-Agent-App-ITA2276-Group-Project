import requests
from utils.cache import alerts_cache

BASE ="https://api.weather.gov/alerts"

def flood_alert_polygons(bbox=None):
    """
     Returns a list of GeoJSON Polygon/MultiPolygon geometries for active Flood/Flash Flood Warnings.

    """
    key = ("alerts", bbox)
    if key in alerts_cache:
        return alerts_cache[key]
    params = {
        "status": "actual",
        "message_type": "alert",
        "event": "Flood Warning",
        "limit": 200
    }
    if bbox:
        #format: west, south, east, north
        params["bbox"] = ",".join(map(str, bbox))

    geoms = []
    for event in ["Flood Warning", "Flash Flood Warning"]:
        params["event"] = event
        r = requests.get(BASE, params=params, timeout=20, headers={"Accept": "application/geo+json"})
        if r.status_code != 200:
            continue
        data = r.json()
        for f in data.get("feature", []):
            g = f.get("geometry")
            if g and g.get("type") in ("Polygon","MultiPolygon"):
                geoms.append(g)
    alerts_cache[key] = geoms
    return geoms