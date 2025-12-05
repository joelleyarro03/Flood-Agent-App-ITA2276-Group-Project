import requests
from utils.cache import overpass_cache
import math

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

# helper: compute a square bbox ~ radius_km around (lat, lon)
def bbox_around(lat: float, lon: float, radius_km: float):
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.0001))
    south = lat - dlat
    north = lat + dlat
    west  = lon - dlon
    east  = lon + dlon
    return west, south, east, north  # Overpass wants (west,south,east,north)

def _post_overpass(query: str):
    headers = {
        "User-Agent": "panaceas-passage/0.1 (contact: demo@example.com)",
        "Accept": "application/json"
    }
    last_err = None
    for url in ENDPOINTS:
        try:
            r = requests.post(url, data={"data": query}, headers=headers, timeout=30)
            # Overpass sends 200 even for errors sometimes; check text too
            if r.status_code == 200:
                return r.json()
            else:
                last_err = f"{url} -> HTTP {r.status_code} :: {r.text[:200]}"
        except Exception as e:
            last_err = f"{url} -> EXC {e}"
    raise RuntimeError(last_err or "All Overpass endpoints failed")

def get_hospitals(lat: float, lon: float, radius_km: int = 20):
    key = (round(lat, 3), round(lon, 3), int(radius_km))
    if key in overpass_cache:
        return overpass_cache[key]

    radius_m = int(radius_km * 1000)

    # --- First attempt: around: query (fast and tight)
    around_query = f"""
                    [out:json][timeout:25];
                    (
                    node["amenity"="hospital"](around:{radius_m},{lat},{lon});
                    way["amenity"="hospital"](around:{radius_m},{lat},{lon});
                    relation["amenity"="hospital"](around:{radius_m},{lat},{lon});
                    );
                    out center tags;
                    """.strip()

    try:
        data = _post_overpass(around_query)
        elements = data.get("elements", [])
    except Exception:
        # --- Fallback: bbox query (Overpass sometimes rejects around)
        w, s, e, n = bbox_around(lat, lon, radius_km)
        bbox_query = f"""
                    [out:json][timeout:25];
                    (
                    node["amenity"="hospital"]({s},{w},{n},{e});
                    way["amenity"="hospital"]({s},{w},{n},{e});
                    relation["amenity"="hospital"]({s},{w},{n},{e});
                    );
                    out center tags;
                    """.strip()
        try:
            data = _post_overpass(bbox_query)
            elements = data.get("elements", [])
        except Exception as ee:
            # Return empty list instead of 500; the route layer can handle it
            # If you want to see the reason, print(ee)
            elements = []

    hospitals = []
    seen = set()
    for e in elements:
        if "lat" in e and "lon" in e:
            la, lo = e["lat"], e["lon"]
        elif "center" in e:
            la, lo = e["center"]["lat"], e["center"]["lon"]
        else:
            continue
        name = e.get("tags", {}).get("name", "Unnamed Hospital")
        sig = (round(la, 6), round(lo, 6), name)
        if sig in seen:
            continue
        seen.add(sig)
        hospitals.append({"name": name, "lat": la, "lon": lo})

    overpass_cache[key] = hospitals
    return hospitals
