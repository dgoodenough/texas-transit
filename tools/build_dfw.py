"""Dallas-Fort Worth's own plan, as the statewide plan uses it: data/dfw/dfw_plan.json.

    python tools/build_dfw.py

From DFW Transit (vendor/dfw-transit), its default scenario, the 2 million riders plan
(scenarios/two_million, results/two_million):
  yearly    capital spent (results years.csv spent_busd, cumulative, at its falling unit costs), its
            budget, operating cost and daily transit trips, each against the current track (today's
            network, no expansion: results/current_track) so the plan's own trips and operating
            cost are what it adds
  lines     every line with its first and last opening year, km and capital (results lines.csv),
            and its geometry by segment and year (the network the DFW tools build for 2100)
  stations  every station with its opening year and modes (results stations.csv)
  zones     people + jobs on a 1 km grid (data/metroplex_density.csv) for the site's map
"""
import csv
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DFW = os.path.join(ROOT, "vendor", "dfw-transit")
SCENARIO = "two_million"
OUT = os.path.join(ROOT, "data", "dfw", "dfw_plan.json")


def read(*parts):
    with open(os.path.join(DFW, *parts), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def thin(pts, tol_deg=0.0012):
    out = [pts[0]]
    for p in pts[1:-1]:
        if math.dist(p, out[-1]) >= tol_deg:
            out.append(p)
    out.append(pts[-1])
    return out


def main():
    plan = {int(r["year"]): r for r in read("results", SCENARIO, "years.csv")}
    base = {int(r["year"]): r for r in read("results", "current_track", "years.csv")}
    yearly = []
    prev = 0.0
    for y in sorted(plan):
        r, b = plan[y], base.get(y)
        spent = float(r["spent_busd"]) * 1000
        yearly.append({"year": y, "spend": round(spent - prev, 1), "budget_cum": float(r["budget_busd"]) * 1000,
                       "trips_day": float(r["daily_trips"]), "base_trips_day": float(b["daily_trips"]) if b else None,
                       "opex": float(r["opex_busd_per_year"]) * 1000,
                       "base_opex": float(b["opex_busd_per_year"]) * 1000 if b else None, "pop_m": float(r["pop_m"])})
        prev = spent
    sys.path.insert(0, DFW)
    cwd = os.getcwd()
    os.chdir(DFW)
    try:
        from dfwt import config, network
        cfg = config.load(scenario=SCENARIO)
        net = network.Network.load(SCENARIO, cfg)
    finally:
        os.chdir(cwd)
    info = {r["line_id"]: r for r in read("results", SCENARIO, "lines.csv")}
    lines = []
    for lid, ln in net.lines.items():
        r = info.get(lid, {})
        segs = [{"year": s.year, "pts": [[round(x, 5), round(y, 5)] for x, y in thin(list(s.pts))]} for s in ln.segments if s.pts]
        lines.append({"id": lid, "name": ln.name, "mode": ln.mode, "status": ln.status, "first_year": ln.first_year,
                      "last_year": ln.last_year, "km": round(ln.km, 1),
                      "capital": float(r["cost_musd"]) if r.get("cost_musd") else None, "segments": segs})
    stations = [{"id": r["station_id"], "name": r["name"], "lat": float(r["lat"]), "lon": float(r["lon"]),
                 "year": int(r["year_opens"]), "lines": r["lines"], "modes": r["modes"],
                 "pop_1km": float(r["pop_1km"] or 0), "jobs_1km": float(r["jobs_1km"] or 0)}
                for r in read("results", SCENARIO, "stations.csv")]
    zones = [{"lat": float(r["lat"]), "lon": float(r["lon"]), "pop": float(r["pop"] or 0), "jobs": float(r["jobs"] or 0)}
             for r in read("data", "metroplex_density.csv")]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"scenario": SCENARIO, "yearly": yearly, "lines": lines, "stations": stations, "zones": zones}, f,
                  separators=(",", ":"))
    print(f"wrote data/dfw/dfw_plan.json: {len(lines)} lines, {len(stations)} stations, {len(zones)} zones "
          f"({os.path.getsize(OUT) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
