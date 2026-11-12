"""The statewide map's data: docs/data/state.json, for docs/map.html.

    python tools/build_state_map.py      (after tools/build_metro_maps.py and study/timing.py)

  hsr          the high-speed corridors (texas/hsr.py), drawn along texas/hsr_alignments.json, with the
               model's track km and the drawn alignment's km
  conv         the conventional corridors (texas/conventional.py) through their stations (straight between
               them; they run on today's freight track). Not the Dallas-Fort Worth connector: DFW's plan has TRE.
  stations     high-speed and conventional stations
  lines        every metro's rail, BRT and streetcar lines from docs/data/metros/<id>.json (today's and
               proposed; DFW's plan with its own opening years), simplified for a statewide view
  metros       name and a label point for each metro with lines
Opening years per scenario come from docs/data/timeline.json, which the page reads too.
"""
import glob
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from texas import conventional as cv  # noqa: E402
from texas import hsr  # noqa: E402

OUT = os.path.join(ROOT, "docs", "data", "state.json")
TOL_M = 40   # line simplification for the statewide view (the metro maps keep their detail)


def km(a, b):
    return math.hypot((a[0] - b[0]) * 110.57, (a[1] - b[1]) * 111.32 * math.cos(math.radians((a[0] + b[0]) / 2)))


def simplify(pts, tol_m):
    """Douglas-Peucker on (lat, lon), tolerance in metres."""
    if len(pts) < 3:
        return pts
    k = math.cos(math.radians(pts[0][0]))

    def d(p, a, b):
        ax, ay, bx, by, px, py = a[1] * k, a[0], b[1] * k, b[0], p[1] * k, p[0]
        vx, vy = bx - ax, by - ay
        L = vx * vx + vy * vy
        t = 0 if not L else max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / L))
        return math.hypot(px - ax - t * vx, py - ay - t * vy) * 110570
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        best, bi = 0, None
        for m in range(i + 1, j):
            dm = d(pts[m], pts[i], pts[j])
            if dm > best:
                best, bi = dm, m
        if bi is not None and best > tol_m:
            keep[bi] = True
            stack += [(i, bi), (bi, j)]
    return [p for p, k_ in zip(pts, keep) if k_]


def rnd(pts):
    return [[round(a, 4), round(b, 4)] for a, b in pts]


def main():
    al = json.load(open(os.path.join(ROOT, "texas", "hsr_alignments.json"), encoding="utf-8"))
    stations = {}
    out_hsr = []
    for cid, (name, sts, *_rest) in hsr.CORRIDORS.items():
        pts = []
        for a, b in zip(sts, sts[1:]):
            pa, pb = list(hsr.STATIONS[a][:2]), list(hsr.STATIONS[b][:2])
            mid = hsr._alignments().get((a, b))
            seg = [pa] + (mid or []) + [pb]
            pts += seg if not pts else seg[1:]
        for s in sts:
            la, lo, kind = hsr.STATIONS[s]
            stations.setdefault(s, {"name": s, "lat": la, "lon": lo, "hsr": [], "conv": [], "kind": kind})["hsr"].append(cid)
        out_hsr.append({"id": f"hsr:{cid}", "name": name, "stations": sts, "pts": rnd(pts),
                        "km_map": round(sum(km(a, b) for a, b in zip(pts, pts[1:]))), "km_model": round(sum(k for _, _, k in hsr.links(sts))), "standard": hsr.standard_of(cid),
                        "source": al["source"].get(cid, "drawn along the highway it is named for")})
    out_cv = []
    for cid, (name, sts, *_rest) in cv.CORRIDORS.items():
        if cid == "DFW":
            continue
        pts = [list(cv.point(s)) for s in sts]
        for s in sts:
            la, lo = cv.point(s)
            stations.setdefault(s, {"name": s, "lat": la, "lon": lo, "hsr": [], "conv": [], "kind": "minor"})["conv"].append(cid)
        out_cv.append({"id": f"conv:{cid}", "name": name, "stations": sts, "pts": rnd(pts)})
    lines, metros = [], []
    for p in sorted(glob.glob(os.path.join(ROOT, "docs", "data", "metros", "*.json"))):
        d = json.load(open(p, encoding="utf-8"))
        mid = d["id"]
        if not d["lines"]:
            continue
        lat = lon = n = 0.0
        for ln in d["lines"]:
            pts = simplify(ln["pts"], TOL_M)
            lines.append({"metro": mid, "name": ln["name"], "mode": ln["mode"], "status": ln["status"], "color": ln.get("color"),
                          "project": ln.get("project"), "year": ln.get("year"), "pts": rnd(pts)})
            for a, b in ln["pts"]:
                lat, lon, n = lat + a, lon + b, n + 1
        metros.append({"id": mid, "lat": round(lat / n, 4), "lon": round(lon / n, 4)})
    data = {"_doc": __doc__.strip().splitlines()[0], "hsr": out_hsr, "conv": out_cv,
            "stations": list(stations.values()), "lines": lines, "metros": metros,
            "hsr_doc": al["_doc"]}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(out_hsr)} high-speed, {len(out_cv)} conventional, {len(lines)} metro line "
          f"pieces, {os.path.getsize(OUT) / 1e6:.1f} MB")
    for h in out_hsr:
        print(f"  {h['id']:10s} map {h['km_map']:5d} km  model {h['km_model']:5d} km  {h['name']}")


if __name__ == "__main__":
    main()
