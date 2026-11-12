"""Helpers to convert between lat/lon and PostGIS geography values."""
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape


def make_point(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({float(lon)} {float(lat)})", srid=4326)


def point_latlon(value) -> dict | None:
    if value is None:
        return None
    p = to_shape(value)
    return {"lat": p.y, "lon": p.x}


def make_polygon(coords) -> WKTElement | None:
    """coords: [[lat, lon], ...] (ring is closed automatically)."""
    if not coords or len(coords) < 3:
        return None
    ring = [(float(lon), float(lat)) for lat, lon in coords]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    wkt = "POLYGON((" + ", ".join(f"{x} {y}" for x, y in ring) + "))"
    return WKTElement(wkt, srid=4326)


def polygon_coords(value) -> list | None:
    if value is None:
        return None
    poly = to_shape(value)
    return [[y, x] for x, y in list(poly.exterior.coords)[:-1]]
