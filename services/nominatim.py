import requests, time
from utils.cache import overpass_cache  # reuse cache infra
from config import DEFAULT_BBOX

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

def _inside_bbox(lat: float, lon: float, bbox):
    w, s, e, n = bbox
    return (s <= lat <= n) and (w <= lon <= e)

def geocode(q: str, limit: int = 5, bbox=DEFAULT_BBOX, hard_bound: bool = True):
    """
    Forward geocoding via Nominatim (OSM), biased/bounded to Houston bbox.
    Returns a list of {label, lat, lon}.
    """
    qkey = ("geocode", q.strip().lower(), limit, bbox, hard_bound)
    if qkey in overpass_cache:
        return overpass_cache[qkey]

    params = {
        "q": q,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": limit,
        "countrycodes": "us",
        # Bias/bound to Houston
        "viewbox": f"{bbox[0]},{bbox[3]},{bbox[2]},{bbox[1]}",  # left,top,right,bottom (lon,lat)
        "bounded": 1 if hard_bound else 0,
    }
    headers = {
        "User-Agent": "panaceas-passage/0.1 (contact: youremail@example.com)"
    }
    time.sleep(0.2)  # be polite
    r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()

    results = []
    for item in data:
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, ValueError):
            continue
        # Post-filter to bbox to be strict for the demo
        if not _inside_bbox(lat, lon, bbox):
            continue
        label = item.get("display_name") or q
        results.append({"label": label, "lat": lat, "lon": lon})

    # If nothing found and we were strict, relax once
    if not results and hard_bound:
        return geocode(q, limit=limit, bbox=bbox, hard_bound=False)

    overpass_cache[qkey] = results
    return results
