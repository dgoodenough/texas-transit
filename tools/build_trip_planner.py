"""The statewide trip planner's data (study/site_parity.md, phase 3): docs/data/intercity.json.

    python tools/build_trip_planner.py

The map page (docs/map.html) plans a trip between any two high-speed stations in the year and schedule shown,
as the intercity model times it (texas/intercity.py RailNetwork): the fastest path over the open corridors,
each link at its design standard's speed with a stop at every intermediate station, the wait for the trains of
every service pattern calling at both ends (texas/hsr.py services_for), and a change of trains where no single
pattern runs the whole way. At each end it hands over to the metro's own map (docs/metros/<id>.html, the
door-to-door planner) at the metro station nearest the high-speed one, or to DFW Transit's map.
"""
import csv
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from texas import hsr, intercity  # noqa: E402

LOCAL_KM = 2.0     # a metro station this close to the high-speed one is its connection
DRIVE_CIRCUITY, DRIVE_KMH = 1.25, 100.0   # the car comparison: road km per straight km, average speed


def km(a, b):
    return math.hypot((a[0] - b[0]) * 110.57, (a[1] - b[1]) * 111.32 * math.cos(math.radians((a[0] + b[0]) / 2)))


def metro_connections(stations):
    """{high-speed station: {page, station id, name, km}} for the metro pages' networks."""
    reg = {m["id"]: m for m in json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))["metros"]}
    out = {}
    for mid in reg:
        page = os.path.join(ROOT, "docs", "metros", f"{mid}.html")
        sp = os.path.join(ROOT, "urban", "generated", mid, "stations.csv")
        if not (os.path.exists(page) and os.path.exists(sp)):
            continue
        sts = [(r["station_id"], r["name"], float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open(sp, encoding="utf-8"))]
        for name, (lat, lon, _) in stations.items():
            sid, nm, la, lo = min(sts, key=lambda s: km((lat, lon), (s[2], s[3])))
            d = km((lat, lon), (la, lo))
            if d <= LOCAL_KM and (name not in out or d < out[name]["km"]):
                out[name] = {"page": f"metros/{mid}.html", "metro": reg[mid]["name"].split(",")[0].split("(")[0].split("-")[0].strip(),
                             "station": sid, "name": nm, "km": round(d, 2)}
    dfw = "https://dgoodenough.github.io/dfw-transit/map.html"
    for name in ("Dallas", "Fort Worth", "Denton"):
        if name in stations and name not in out:
            out[name] = {"page": dfw, "metro": "Dallas-Fort Worth", "station": None, "name": None, "km": None}
    return out


EXAMPLES = [("Dallas", "Houston"), ("Houston", "Austin"), ("San Antonio", "Dallas"), ("Houston", "McAllen"),
            ("El Paso", "Dallas"), ("Amarillo", "Austin")]


def plan(d, a, b, year, scen):
    """The page's planner in Python (docs/map.html planTrip), for the story's examples: (minutes station to
    station, changes, fare $, car minutes) or None."""
    import heapq
    sc = d["scenarios"][scen]
    built = {c for c, (y, _) in sc.items() if y <= year}
    speed = {}
    for c in built:
        sp = d["speeds"].get(sc[c][1], d["speeds"]["S1"])
        for x, y, k in d["links"][c]:
            key = tuple(sorted((x, y)))
            if key not in speed or speed[key][0] < sp:
                speed[key] = (sp, k)
    adj = {}
    for (x, y), (sp, k) in speed.items():
        adj.setdefault(x, []).append((y, k / sp * 60, k))
        adj.setdefault(y, []).append((x, k / sp * 60, k))
    best, prev, pq = {a: (0.0, 0.0)}, {a: None}, [(0.0, a)]
    while pq:
        t, u = heapq.heappop(pq)
        if u == b:
            break
        if t > best[u][0]:
            continue
        for v, dt, k in adj.get(u, []):
            nt = t + dt + (d["svc"]["stop_min"] if u != a else 0)
            if v not in best or nt < best[v][0]:
                best[v], prev[v] = (nt, best[u][1] + k), u
                heapq.heappush(pq, (nt, v))
    if b not in best:
        return None
    route = [b]
    while prev[route[0]]:
        route.insert(0, prev[route[0]])
    svc, covered = [], set()
    for cids, chain, h in d["patterns"]:
        if set(cids) <= built:
            svc.append((chain, h))
            covered |= set(cids)
    svc += [(d["chains"][c], d["shuttle"].get(c, 60)) for c in built if c not in covered]
    legs, i = [], 0
    while i < len(route) - 1:
        pick, reach = None, i
        for chain, h in svc:
            j = i
            while j < len(route) - 1 and route[j] in chain and route[j + 1] in chain and \
                    abs(chain.index(route[j + 1]) - chain.index(route[j])) == 1:
                j += 1
            if j > reach or (j == reach and j > i and pick and h < pick[1]):
                reach, pick = j, (chain, h)
        if not pick:
            break
        legs.append(pick[1])
        i = reach
    direct = sum(60 / h for chain, h in svc if a in chain and b in chain)
    h = 60 / direct if direct else max(legs)
    wait = min(h * d["svc"]["wait_share"], d["svc"]["max_wait_min"])
    changes = max(len(legs) - 1, 0)
    ride, track = best[b]
    A, B = d["stations"][a], d["stations"][b]
    car = km(A, B) * d["drive"]["circuity"] / d["drive"]["kmh"] * 60
    return ride + wait + changes * d["svc"]["transfer_min"], changes, d["svc"]["fare_fixed"] + d["svc"]["fare_per_km"] * track, car


def main():
    T = json.load(open(os.path.join(ROOT, "docs", "data", "timeline.json"), encoding="utf-8"))
    p = intercity.load_params()["hsr"]
    used = {s for _, chain in hsr.CORRIDORS.values() for s in chain}
    stations = {s: v for s, v in hsr.STATIONS.items() if s in used}
    links = {cid: [[a, b, round(t, 1)] for a, b, t in hsr.links(chain)] for cid, (_, chain) in hsr.CORRIDORS.items()}
    wm_std = {p_["id"].split(":", 1)[1]: p_.get("standard") or "S1" for p_ in T.get("whole_map_projects", [])}
    scen = {}
    for key, s in T["scenarios"].items():
        scen[key] = {pid.split(":", 1)[1]: [w[1], wm_std.get(pid.split(":", 1)[1], "S1") if key == "whole_map" else "S1"]
                     for pid, w in s["when"].items() if pid.startswith("hsr:") and w}
    data = {"_doc": "tools/build_trip_planner.py: texas/hsr.py corridors, standards and service patterns; the "
                    "intercity model's timing (texas/intercity.py); metro connections for the hand-over",
            "stations": {s: [round(v[0], 4), round(v[1], 4), v[2]] for s, v in stations.items()},
            "corridors": {cid: name for cid, (name, _) in hsr.CORRIDORS.items()},
            "links": links,
            "speeds": {k: v[1] for k, v in hsr.STANDARDS.items()},
            "patterns": [[cids, chain, h] for cids, chain, h in hsr.PATTERNS],
            "shuttle": hsr.SHUTTLE_HEADWAY,
            "chains": {cid: chain for cid, (_, chain) in hsr.CORRIDORS.items()},
            "svc": {k: p[k] for k in ("stop_min", "max_wait_min", "transfer_min", "access_min", "egress_min",
                                      "terminal_min", "fare_fixed", "fare_per_km")} | {"wait_share": p.get("wait_share", 0.5)},
            "drive": {"circuity": DRIVE_CIRCUITY, "kmh": DRIVE_KMH},
            "scenarios": scen,
            "local": metro_connections(stations)}
    data["examples"] = []
    for a, b in EXAMPLES:
        row = {"from": a, "to": b}
        for key in data["scenarios"]:
            for y in (2050, 2100):
                r = plan(data, a, b, y, key)
                row[f"{key}_{y}"] = None if r is None else [round(r[0]), r[1], round(r[2]), round(r[3])]
        data["examples"].append(row)
    out = os.path.join(ROOT, "docs", "data", "intercity.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"wrote {out}: {len(stations)} stations, {len(data['local'])} with a metro connection")


if __name__ == "__main__":
    main()
