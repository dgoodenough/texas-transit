"""Where the generated BRT runs: on highways or on streets people live and work along.

    python study/brt_streets.py [BEFORE_DIR]

For every metro's generated BRT (urban/generated/<id>/), samples each line every 100 m and finds
the road it runs on (the nearest Overture segment within 40 m, urban/data/metros/<id>/osm/roads.parquet)
and the people + jobs within 400 m (2020 block groups). Reports the share of BRT km on motorways and
highway-class trunk roads, and the people + jobs along each km. With BEFORE_DIR (a copy of
urban/generated from an earlier run), compares the two. Writes study/brt_streets.md.

DFW Transit's generator routed BRT on DFW's hand-plan profile (freeways x1.6, trunk x1.15) until
its street profile (metro/routing.py brt_path: freeways x5, trunk x2, cheaper where people and
jobs line the street), the change this checks.
"""
import collections
import csv
import json
import math
import os
import sys

import numpy as np
import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor", "dfw-transit"))
from dfwt.osmroute import wkb_linestring  # noqa: E402

STEP_M, NEAR_M, CATCH_M = 100.0, 40.0, 400.0
HIGHWAY = {"motorway", "trunk"}


class Roads:
    def __init__(self, path, lat0):
        self.k = math.cos(math.radians(lat0))
        t = pq.read_table(path, columns=["geometry", "class"])
        self.segs, self.cls = [], []
        self.grid = collections.defaultdict(list)
        for g, c in zip(t.column("geometry").to_pylist(), t.column("class").to_pylist()):
            pts = wkb_linestring(g) if g else None
            if not pts:
                continue
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                i = len(self.segs)
                self.segs.append((self.m(x1, y1), self.m(x2, y2)))
                self.cls.append(c)
                for cell in {self.cell(x1, y1), self.cell(x2, y2)}:
                    self.grid[cell].append(i)

    def m(self, lon, lat):
        return lon * 111320 * self.k, lat * 110540

    def cell(self, lon, lat):
        return int(lon * 200), int(lat * 200)   # about 500 m

    def road_at(self, lon, lat):
        p = self.m(lon, lat)
        cx, cy = self.cell(lon, lat)
        best, cls = NEAR_M, None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in self.grid.get((cx + dx, cy + dy), ()):
                    (ax, ay), (bx, by) = self.segs[i]
                    vx, vy = bx - ax, by - ay
                    L2 = vx * vx + vy * vy or 1e-9
                    t = max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / L2))
                    d = math.hypot(p[0] - ax - t * vx, p[1] - ay - t * vy)
                    if d < best:
                        best, cls = d, self.cls[i]
        return cls


def brt_lines(folder):
    csv.field_size_limit(1 << 28)
    if not os.path.exists(os.path.join(folder, "lines.csv")):
        return []
    meta = {r["line_id"]: r for r in csv.DictReader(open(os.path.join(folder, "lines.csv"), encoding="utf-8"))}
    out = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(folder, "line_segments.csv"), encoding="utf-8")):
        m = meta.get(r["line_id"])
        if not m or m["mode"] != "brt" or m["status"] == "existing":
            continue
        body = r["geometry_wkt"][r["geometry_wkt"].index("(") + 1:-1]
        out[r["line_id"]].extend(tuple(map(float, q.split())) for q in body.split(","))
    return list(out.values())


def samples(pts):
    """(lon, lat) every STEP_M along a polyline."""
    out = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        d = math.hypot((x2 - x1) * 111320 * math.cos(math.radians(y1)), (y2 - y1) * 110540)
        n = max(1, int(d // STEP_M))
        out += [(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n) for i in range(n)]
    return out


def measure(mid, folder):
    lines = brt_lines(folder)
    if not lines:
        return None
    zs = list(csv.DictReader(open(os.path.join(ROOT, "urban", "data", "metros", mid, "zones.csv"), encoding="utf-8")))
    lat = np.array([float(z["lat"]) for z in zs])
    lon = np.array([float(z["lon"]) for z in zs])
    act = np.array([float(z["pop"] or 0) + float(z["jobs"] or 0) for z in zs])
    roads = Roads(os.path.join(ROOT, "urban", "data", "metros", mid, "osm", "roads.parquet"), float(np.mean(lat)))
    by_cls = collections.Counter()
    near = np.zeros(len(zs), dtype=bool)
    for pts in lines:
        for lo, la in samples(pts):
            by_cls[roads.road_at(lo, la) or "off-network"] += STEP_M / 1000
            d = np.hypot((lat - la) * 110.54, (lon - lo) * 111.32 * math.cos(math.radians(la)))
            near |= d <= CATCH_M / 1000
    km = sum(by_cls.values())
    return {"km": km, "highway_share": sum(v for k, v in by_cls.items() if k in HIGHWAY) / km,
            "by_class": dict(by_cls), "catch_per_km": float(act[near].sum()) / km, "catch": float(act[near].sum())}


def main():
    before_dir = sys.argv[1] if len(sys.argv) > 1 else None
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))
    rows = []
    for m in reg["metros"]:
        after = measure(m["id"], os.path.join(ROOT, "urban", "generated", m["id"]))
        before = measure(m["id"], os.path.join(before_dir, m["id"])) if before_dir else None
        if after or before:
            rows.append((m, before, after))
            print(m["id"], before and f"{before['highway_share']:.0%}", after and f"{after['highway_share']:.0%}")
    L = ["# Where the generated BRT runs", "",
         "Generated by `python study/brt_streets.py`. Each metro's generated BRT, sampled every 100 m: the share of its km "
         "on motorways and highway-class trunk roads (the nearest Overture road within 40 m), and the people + jobs "
         "within 400 m of the line (2020 block groups; each counted once) per km of BRT. A station beside a highway has "
         "no walk-up catchment and no frontage to develop; a bus on a busy arterial has both.", ""]
    if before_dir:
        L += ["Before: DFW Transit's hand-plan BRT profile (freeways x1.6, highway-class trunk roads x1.15). After: the "
              "generator's street profile (freeways x5, trunk x2, tertiary streets allowed, cheaper where people and jobs "
              "line the street).", "",
              "| Metro | BRT km before | On highways before | People + jobs within 400 m per km before | BRT km after | On highways after | Per km after |",
              "|---|---|---|---|---|---|---|"]
        for m, b, a in rows:
            f = lambda r, k, fmt: (fmt.format(r[k]) if r else "")  # noqa: E731
            L.append(f"| {m['name'].split(',')[0]} | {f(b, 'km', '{:,.0f}')} | {f(b, 'highway_share', '{:.0%}')} | "
                     f"{f(b, 'catch_per_km', '{:,.0f}')} | {f(a, 'km', '{:,.0f}')} | {f(a, 'highway_share', '{:.0%}')} | "
                     f"{f(a, 'catch_per_km', '{:,.0f}')} |")
        tb = [b for _, b, _ in rows if b]
        ta = [a for _, _, a in rows if a]
        hw = lambda rs: sum(r["highway_share"] * r["km"] for r in rs) / sum(r["km"] for r in rs)  # noqa: E731
        L += ["", f"**All metros:** {hw(tb):.0%} of BRT km on highways before, {hw(ta):.0%} after; people + jobs within "
              f"400 m, {sum(r['catch'] for r in tb) / 1e6:.2f}M before and {sum(r['catch'] for r in ta) / 1e6:.2f}M after.", ""]
    else:
        L += ["| Metro | BRT km | On highways | People + jobs within 400 m per km |", "|---|---|---|---|"]
        for m, _, a in rows:
            L.append(f"| {m['name'].split(',')[0]} | {a['km']:,.0f} | {a['highway_share']:.0%} | {a['catch_per_km']:,.0f} |")
    with open(os.path.join(ROOT, "study", "brt_streets.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
