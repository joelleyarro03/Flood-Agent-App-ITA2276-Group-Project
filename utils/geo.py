import math
from shapely.geometry import shape, Point, LineString, Polygon, MultiPolygon, mapping
from shapely.ops import unary_union

# This function returns the straight-line distance using the haversine formal
def haversine_km(a, b):
    (lat1, lon1), (lat2, lon2) = a, b
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(h))

# This combines all the sources of polygons from the different sources to test against routes
# Non-polygons are ignored, bad geo inputs are shipped
# This function returns a single shapely Polygon or none if non valid one found 
def union_polygons(geoms):
    polys = []
    for g in geoms:
        try:
            shp = shape(g) if isinstance(g, dict) else g
            if isinstance(shp, (Polygon, MultiPolygon)):
                polys.append(shp)
        except Exception:
            pass
    if not polys:
        return None
    return unary_union(polys)

# This function adds safety margin around a shape( this is for risk mitigation)
#  Also to find floods close to route
# input: a shaply goemetry, outputs the shapely geometry buffered 
def buffer_meters(geom, meters):
    if geom is None or meters == 0:
        return geom
    # Approx: 1 degree ~ 111,000 meters near Houston; fine for small buffers
    factor = meters / 111_000.0
    return geom.buffer(factor)

# Check if route crosses a flood polygon
# input OSRM route geometry and flood polygon, output: True if floor zoon, False otherwise 
def line_intersects_polygons(line_geojson, polygons):
    if polygons is None:
        return False
    line = shape(line_geojson)
    return line.intersects(polygons)

# creates a tiny tube around a routes to check if flood is around that tube
# Why?: Houston TranStar are points (risk locations) not polygons
# Input: routes, shapley Points and meters
# Output: True/False 
def line_near_points(line_geojson, points, meters=50):
    """
    Return True if any point (Point or (lat,lon) tuple) lies within `meters` of the line.
    """
    if not points:
        return False
    line = shape(line_geojson)
    buf = buffer_meters(line, meters)

    for p in points:
        if isinstance(p, Point):
            pt = p
        else:
            # assume tuple (lat, lon)
            lat, lon = p
            pt = Point(lon, lat)  # shapely expects (x=lon, y=lat)
        if buf.contains(pt):
            return True
    return False

# Function turns points into a shap by making each point a small circle and then unioning all points
# why: TranStar road-flood points are represented as a single geometric area to draw on the map
# input: (lat, lon)
# output: the radius for each circle in meters
def points_buffered(points_lonlat, meters):
    pts = [Point(lon, lat) for (lat, lon) in points_lonlat]
    buffers = [buffer_meters(p, meters) for p in pts]
    return unary_union(buffers)


