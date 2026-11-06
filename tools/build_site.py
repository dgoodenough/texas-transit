"""The site's map data: docs/data/map.json (docs/index.html reads it with docs/data/timeline.json,
which study/timing.py writes).

    python tools/build_site.py

Contents: state outlines (Census cartographic boundaries 1:20M, cached in data/raw/), high-speed and
conventional stations and corridors, and each metro's generated network (urban/generated/<id>/)
with every line tagged with its timeline project id, plus a 1 km grid of people + jobs. Coordinates
are projected: the statewide map in hundredths of a degree of latitude (longitude scaled at 31N),
each metro in km around its population centre.
"""
import csv
import json
import math
import os
import re
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor", "dfw-transit"))
from metro import census  # noqa: E402
from texas import conventional as cv, hsr, shapes  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
STATES_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip"
SHOW = ("TX", "OK", "LA", "AR", "NM", "KS", "MS", "CO", "MO", "TN", "AL")
LAT0 = 31.0
K = math.cos(math.radians(LAT0))


def xy(lon, lat):
    return [round((lon + 100) * K * 100, 1), round((LAT0 - lat) * 100, 1)]


def thin(pts, tol):
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for p in pts[1:-1]:
        if math.dist(p, out[-1]) >= tol:
            out.append(p)
    out.append(pts[-1])
    return out


def states():
    path = os.path.join(RAW, STATES_URL.rsplit("/", 1)[1])
    if not os.path.exists(path):
        os.makedirs(RAW, exist_ok=True)
        urllib.request.urlretrieve(STATES_URL, path + ".part")
        os.replace(path + ".part", path)
    with zipfile.ZipFile(path) as z:
        shp = z.read("cb_2023_us_state_20m.shp")
        dbf = census.read_dbf(z.read("cb_2023_us_state_20m.dbf"))
    out = {}
    for rec, rings in zip(dbf, shapes.read_polygons(shp)):
        if rec["STUSPS"] in SHOW:
            out[rec["STUSPS"]] = [r for r in (thin([xy(x, y) for x, y in ring], 2.0) for ring in rings) if len(r) > 3]
    return out


def metros():
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))
    csv.field_size_limit(1 << 28)
    out = []
    for m in reg["metros"]:
        d = os.path.join(ROOT, "urban", "generated", m["id"])
        zs = list(csv.DictReader(open(os.path.join(ROOT, "urban", "data", "metros", m["id"], "zones.csv"), encoding="utf-8")))
        w = sum(int(z["pop"]) for z in zs) or 1
        lat0 = sum(float(z["lat"]) * int(z["pop"]) for z in zs) / w
        lon0 = sum(float(z["lon"]) * int(z["pop"]) for z in zs) / w
        k = math.cos(math.radians(lat0))

        def local(lon, lat):
            return [round((lon - lon0) * k * 111.2, 2), round((lat0 - lat) * 111.2, 2)]
        lines = []
        if os.path.exists(os.path.join(d, "lines.csv")):
            meta = {r["line_id"]: r for r in csv.DictReader(open(os.path.join(d, "lines.csv"), encoding="utf-8"))}
            segs = {}
            for r in csv.DictReader(open(os.path.join(d, "line_segments.csv"), encoding="utf-8")):
                body = r["geometry_wkt"][r["geometry_wkt"].index("(") + 1:-1]
                segs.setdefault(r["line_id"], []).extend(tuple(map(float, q.split())) for q in body.split(","))
            for lid, pts in segs.items():
                r = meta[lid]
                if r["mode"] == "bus":
                    continue
                cand = re.search(r"generated \(([A-Z]\d+)\)", r["notes"] or "")
                lines.append({"project": f"{m['id']}:{cand.group(1)}" if cand else None, "status": r["status"],
                              "mode": r["mode"], "name": r["name"],
                              "pts": thin([local(*p) for p in pts], 0.15)})
        cells = {}
        for z in zs:
            x, y = local(float(z["lon"]), float(z["lat"]))
            key = (round(x), round(y))
            cells[key] = cells.get(key, 0) + int(z["pop"]) + float(z["jobs"] or 0)
        out.append({"id": m["id"], "name": m["name"].split(",")[0], "xy": xy(lon0, lat0), "pop": m["texas_pop"],
                    "budget": m["budget_musd"], "net": lines,
                    "dots": [[a, b, round(v)] for (a, b), v in cells.items() if v >= 2000]})
    return out


def main():
    data = {
        "states": states(),
        "hsr_stations": {s: {"xy": xy(v[1], v[0]), "kind": v[2]} for s, v in hsr.STATIONS.items()},
        "hsr": {f"hsr:{k}": [xy(hsr.STATIONS[s][1], hsr.STATIONS[s][0]) for s in v[1]] for k, v in hsr.CORRIDORS.items()},
        "conv": {f"conv:{k}": [xy(cv.STATIONS[s][1], cv.STATIONS[s][0]) for s in v[1]]
                 for k, v in cv.CORRIDORS.items() if k != "DFW"},
        "conv_ends": {n: xy(cv.STATIONS[n][1], cv.STATIONS[n][0]) for n in
                      ("Kansas City", "Memphis", "Jackson", "Albuquerque", "Monterrey")},
        "dfw": {"name": "Dallas-Fort Worth", "xy": xy(-96.9454, 32.8628)},
        "metros": metros(),
    }
    os.makedirs(os.path.join(ROOT, "docs", "data"), exist_ok=True)
    path = os.path.join(ROOT, "docs", "data", "map.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"wrote docs/data/map.json ({os.path.getsize(path) / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
