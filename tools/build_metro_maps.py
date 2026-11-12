"""Zoomable metro maps for the site: docs/data/metros/<id>.json, one per metro (and DFW), loaded when
a reader picks the metro.

    python tools/build_metro_maps.py

Each file has:
  lines     every line at full alignment (lat, lon to 5 decimals, thinned to SIMPLIFY_M), with its
            mode, today's or proposed, and the timeline project it belongs to (study/timing.py),
            or for DFW the year each segment opens (DFW Transit's 2 million riders plan)
  stations  name, lat, lon, the lines and projects that serve it (DFW: its opening year)
  roads     motorways, trunk roads and major arterials from the Overture data the generator routed on
            (urban/data/metros/<id>/osm/roads.parquet; DFW: DFW Transit's data/osm), for orientation;
            the page draws them as its own basemap, since the site can't rely on outside map tiles
"""
import csv
import json
import math
import os
import re
import sys

import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor", "dfw-transit"))
from dfwt.osmroute import wkb_linestring  # noqa: E402

OUT = os.path.join(ROOT, "docs", "data", "metros")
SIMPLIFY_M = 8.0
ROAD_SIMPLIFY_M = 40.0
ROAD_CLASSES = {"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3}


def simplify(pts, tol_m):
    """Douglas-Peucker on (lon, lat) points, tolerance in metres."""
    if len(pts) < 3:
        return pts
    k = math.cos(math.radians(pts[0][1]))
    xy = [(lo * 111320 * k, la * 110540) for lo, la in pts]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = xy[a], xy[b]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1e-9
        best, idx = 0.0, None
        for i in range(a + 1, b):
            d = abs(dy * (xy[i][0] - x1) - dx * (xy[i][1] - y1)) / L
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol_m:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k_ in zip(pts, keep) if k_]


def latlon(pts, tol):
    return [[round(la, 5), round(lo, 5)] for lo, la in simplify(pts, tol)]


MAX_ROADS = 40000   # above this, secondary roads are left out (DFW, Houston): the file stays a few MB


def roads(path):
    out = _roads(path)
    if len(out) > MAX_ROADS:
        out = [r for r in out if r[0] < ROAD_CLASSES["secondary"]]
    return out


def _roads(path):
    if not os.path.exists(path):
        return []
    t = pq.read_table(path, columns=["geometry", "class"])
    out = []
    for g, c in zip(t.column("geometry").to_pylist(), t.column("class").to_pylist()):
        if c not in ROAD_CLASSES or g is None:
            continue
        pts = wkb_linestring(g)
        if pts and len(pts) >= 2:
            out.append([ROAD_CLASSES[c], latlon(pts, ROAD_SIMPLIFY_M)])
    return out


def metro(mid):
    d = os.path.join(ROOT, "urban", "generated", mid)
    lines, stations = [], []
    if os.path.exists(os.path.join(d, "lines.csv")):
        csv.field_size_limit(1 << 28)
        meta = {r["line_id"]: r for r in csv.DictReader(open(os.path.join(d, "lines.csv"), encoding="utf-8"))}
        proj = {}
        for lid, r in meta.items():
            m = re.search(r"generated \(([A-Z]\d+)\)", r["notes"] or "")
            proj[lid] = f"{mid}:{m.group(1)}" if m else None
        geo = {}
        for r in csv.DictReader(open(os.path.join(d, "line_segments.csv"), encoding="utf-8")):
            body = r["geometry_wkt"][r["geometry_wkt"].index("(") + 1:-1]
            geo.setdefault(r["line_id"], []).append([tuple(map(float, q.split())) for q in body.split(",")])
        for lid, segs in geo.items():
            r = meta[lid]
            if r["mode"] == "bus":
                continue
            for pts in segs:
                lines.append({"id": lid, "name": r["name"], "mode": r["mode"], "status": r["status"], "color": r.get("color"),
                              "project": proj.get(lid), "pts": latlon(pts, SIMPLIFY_M)})
        serve = {}
        for r in csv.DictReader(open(os.path.join(d, "line_stops.csv"), encoding="utf-8")):
            if r["line_id"] in meta and meta[r["line_id"]]["mode"] != "bus":
                serve.setdefault(r["station_id"], set()).add(r["line_id"])
        for r in csv.DictReader(open(os.path.join(d, "stations.csv"), encoding="utf-8")):
            if r["station_id"] in serve:
                ls = sorted(serve[r["station_id"]])
                stations.append({"name": r["name"], "lat": round(float(r["lat"]), 5), "lon": round(float(r["lon"]), 5),
                                 "lines": [meta[x]["name"] for x in ls],
                                 "projects": [proj[x] for x in ls if proj.get(x)],
                                 "today": any(meta[x]["status"] == "existing" for x in ls)})
    return {"id": mid, "lines": lines, "stations": stations,
            "roads": roads(os.path.join(ROOT, "urban", "data", "metros", mid, "osm", "roads.parquet"))}


def dfw():
    plan = json.load(open(os.path.join(ROOT, "data", "dfw", "dfw_plan.json"), encoding="utf-8"))
    colors = {}   # DFW Transit's own line colours: its network, and the lines the 2 million plan adds
    for p in ("network/lines.csv", "scenarios/two_million/lines.add.csv", "scenarios/two_million/extra/lines.csv"):
        f = os.path.join(ROOT, "vendor", "dfw-transit", p)
        if os.path.exists(f):
            colors.update({r["line_id"]: r["color"] for r in csv.DictReader(open(f, encoding="utf-8")) if r.get("color")})
    lines = [{"id": ln["id"], "name": ln["name"], "mode": ln["mode"], "status": "existing" if sg["year"] <= 2025 else "proposed",
              "year": sg["year"], "color": colors.get(ln["id"]), "pts": latlon([tuple(p) for p in sg["pts"]], SIMPLIFY_M)}
             for ln in plan["lines"] for sg in ln["segments"] if len(sg["pts"]) >= 2]
    stations = [{"name": s["name"], "lat": round(s["lat"], 5), "lon": round(s["lon"], 5), "lines": s["lines"].split(";"),
                 "year": s["year"]} for s in plan["stations"]]
    return {"id": "dfw", "lines": lines, "stations": stations,
            "roads": roads(os.path.join(ROOT, "vendor", "dfw-transit", "data", "osm", "roads.parquet"))
            or roads(os.path.join(ROOT, "urban", "data", "metros", "dfw", "osm", "roads.parquet"))}


def main():
    os.makedirs(OUT, exist_ok=True)
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))
    for data in [dfw()] + [metro(m["id"]) for m in reg["metros"]]:
        path = os.path.join(OUT, f"{data['id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        print(f"  {data['id']:16s} {len(data['lines']):4d} line pieces, {len(data['stations']):4d} stations, "
              f"{len(data['roads']):6d} roads, {os.path.getsize(path) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
