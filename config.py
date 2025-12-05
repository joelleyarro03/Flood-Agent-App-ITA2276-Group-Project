# Basic config / constants
DEFAULT_RADIUS_KM = 20
FLOOD_BUFFER_METERS = 100           # expand/contract polygons slightly
TRANSTAR_POINT_BUFFER_METERS = 75   # avoidance radius around flood-prone points

# To estrict alert fetch by bbox (Houston-ish)
# west, south, east, north (lon/lat)
DEFAULT_BBOX = (-95.9, 29.4, -95.0, 30.2)
