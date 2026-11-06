"""A minimal ESRI shapefile reader for polygons (enough for the NextGen OD zones), and a
point-in-polygon test. No GIS libraries needed."""
import struct


def read_polygons(shp_bytes):
    """Polygon records from a .shp file's bytes, in file order: a list of rings per record, each
    ring a list of (x, y)."""
    out, pos = [], 100   # 100-byte file header
    while pos < len(shp_bytes):
        _, length = struct.unpack_from(">ii", shp_bytes, pos)   # record number, content length (16-bit words)
        start = pos + 8
        shape_type = struct.unpack_from("<i", shp_bytes, start)[0]
        rings = []
        if shape_type in (5, 15, 25):   # polygon, polygonZ, polygonM: box, parts, points
            nparts, npts = struct.unpack_from("<ii", shp_bytes, start + 36)
            parts = list(struct.unpack_from(f"<{nparts}i", shp_bytes, start + 44))
            p0 = start + 44 + 4 * nparts
            pts = [struct.unpack_from("<2d", shp_bytes, p0 + 16 * k) for k in range(npts)]
            for a, b in zip(parts, parts[1:] + [npts]):
                rings.append(pts[a:b])
        out.append(rings)
        pos = start + 2 * length
    return out


def contains(rings, x, y):
    """Even-odd rule over every ring, so holes work."""
    inside = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def bbox(rings):
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    return min(xs), min(ys), max(xs), max(ys)
