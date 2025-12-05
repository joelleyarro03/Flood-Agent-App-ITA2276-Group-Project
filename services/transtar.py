import requests
from utils.cache import transtar_cache

# URL for the TranStar Roadway Flood Warning data feed.
# The official API documentation points to this sample URL.
TRANSTAR_URL = "https://traffic.houstontranstar.org/api/roadwayfloodwarning_sample.json"

def get_transtar_points():
    """
    Fetches and returns a list of (lat, lon) tuples for active flood sensors
    from the Houston TranStar API.

    This function caches the results to avoid excessive API calls. It filters
    for sensors that have a "stream elevation alert" to only return points
    that are actively reporting flooding.
    """
    key = "transtar_alert_points"
    if key in transtar_cache:
        return transtar_cache[key]

    try:
        r = requests.get(TRANSTAR_URL, timeout=15)
        r.raise_for_status()  # Raise an exception for bad status codes
        data = r.json()

        points = []
        # The API returns a dictionary with a 'result' key containing the list of sensors
        for item in data.get("result", []):
            # We only want to include points that are actively alerting
            if item.get("IsStreamElevationAlert") == "True":
                lat = item.get("Latitude")
                lon = item.get("Longitude")
                if lat is not None and lon is not None:
                    points.append((float(lat), float(lon)))

        transtar_cache[key] = points
        return points
    except (requests.RequestException, ValueError) as e:
        # Log the error for debugging purposes
        print(f"Error fetching or parsing TranStar data: {e}")
        return []
