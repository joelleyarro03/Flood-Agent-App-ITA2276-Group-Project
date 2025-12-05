import requests, math, time

OSRM_BASE = "https://router.project-osrm.org"

def _get(url, tries=3, sleep=0.4):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last = str(e)
        time.sleep(sleep * (i + 1))
    # print for server logs; don’t crash the endpoint
    print("[OSRM ERROR]", url, "->", last)
    return None

def distance_km(origin, dest):
    lat1, lon1 = origin; lat2, lon2 = dest
    url = f"{OSRM_BASE}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false&alternatives=false"
    js = _get(url)
    if not js or not js.get("routes"):
        return math.inf
    return js["routes"][0]["distance"]/1000.0

def full_route(origin, dest):
    lat1, lon1 = origin; lat2, lon2 = dest
    # Try a few param variants that sometimes dodge demo-server quirks
    variants = [
        "overview=full&geometries=geojson&steps=false&alternatives=false",
        "overview=full&geometries=geojson&steps=false&continue_straight=true",
        "overview=simplified&geometries=geojson&steps=false",
    ]
    for q in variants:
        url = f"{OSRM_BASE}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?{q}"
        js = _get(url)
        if js and js.get("routes"):
            r = js["routes"][0]
            return {
                "distance_km": r["distance"]/1000.0,
                "duration_min": r["duration"]/60.0,
                "geometry": r["geometry"]
            }
    # As a last resort, provide a straight line so the UI can still draw something
    print("[OSRM] no route; falling back to straight line geometry")
    return None
