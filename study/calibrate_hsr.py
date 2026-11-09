"""Calibrating high-speed rail's constant against car (texas/intercity.json hsr.asc_vs_car).

    python study/calibrate_hsr.py [--save]

The constant is how much travellers like a train beyond its time, cost and frequency. It had been
an assumption (-0.5, "tested at 0 and -1"), and the plan's ratios turn on it (study/cabinet/audit.md).
Here it is fitted, within the model's own structure (the pivot-point nested logit of
texas/intercity.py, today's parameters), to three American markets where fast intercity trains
run today, using the same national NextGen NHTS 2022 origin-destination data the Texas model
uses for car and air:

  New York - Washington   Amtrak's share of the air-rail market, 65-75% (Amtrak, 2010-2014)
  New York - Boston       52-54%
  Miami - Orlando         Brightline's riders on the Orlando extension in 2024: about 765,000
                          in the first half, so about 1.3-1.7M for the year (opened Sept 2023)

For the Northeast pairs rail already runs in the 2022 data, but the NHTS's rail counts are not
reliable on long pairs (it gives Chicago - New York 20% rail), so rail is rebuilt from NHTS air
x Amtrak's market share, and the shares without rail are recovered by inverting the nest. Miami -
Orlando had no fast train in 2022, so it is a forecast from the 2022 car and air split, as the
Texas model does. Train times, frequencies and fares are each service's own (sources inline).

The answers bracket the constant: the Northeast's legacy, car-light, rail-habituated markets from
above, Brightline from below. Texas is car-dependent like Florida, so the central value is
Brightline's (a new service in a driving state, its first full year: if anything low, as it is
still ramping up), and the range runs from Brightline's low to the Northeast's high. --save writes
both to texas/intercity.json (asc_vs_car, asc_range). Writes study/calibrate_hsr.md.
"""
import collections
import csv
import io
import json
import math
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from texas import intercity as ic  # noqa: E402

NHTS = os.path.join(ROOT, "data", "raw", "nhts", "2022_Passenger_OD_Annual.zip")
COMPARABLES = [
    # name, zone-id prefixes (a, b), stations (lat, lon) a, b, track km, run minutes, headway, fare,
    # target: ("market", low, central, high) = rail share of air + rail; ("riders", ...) = rail trips a year
    {"name": "New York - Washington", "a": "35620_", "b": "47900_",
     "sa": (40.7506, -73.9935), "sb": (38.8973, -77.0063),   # Penn Station, Union Station
     # 362 km; Acela about 2h50, Northeast Regional about 3h20, about 40 trains a day each way:
     # a blended 3h05, every 27 minutes; a blended fare of about $110 (Acela $150-250, Regional $50-120)
     "track_km": 362, "run_min": 185, "headway": 27, "fare": 110, "target": ("market", 0.65, 0.70, 0.75)},
    {"name": "New York - Boston", "a": "35620_", "b": "14460_",
     "sa": (40.7506, -73.9935), "sb": (42.3523, -71.0552),   # Penn Station, South Station
     # 372 km; Acela about 3h45, Regional about 4h15, about 19 trains a day each way
     "track_km": 372, "run_min": 240, "headway": 57, "fare": 100, "target": ("market", 0.52, 0.53, 0.54)},
    {"name": "Miami - Orlando (Brightline)", "a": "33100_", "b": "36740_",
     "sa": (25.7781, -80.1955), "sb": (28.4312, -81.3081),   # MiamiCentral, Orlando airport
     # 378 km; about 3h30, 16 round trips a day; long-distance fares about $80-90 on average
     "track_km": 378, "run_min": 210, "headway": 68, "fare": 85,
     "target": ("riders", 1.3e6, 1.5e6, 1.7e6), "forecast": True},
]


def nhts_pair(prefix_a, prefix_b):
    """Daily car, air and NHTS-rail person-trips (both directions) and work share between two
    metros given as zone-id prefixes (the NextGen zones split metros by state)."""
    acc = collections.Counter()
    with zipfile.ZipFile(NHTS) as z:
        name = next(x for x in z.namelist() if x.lower().endswith(".csv"))
        with z.open(name) as src:
            for r in csv.DictReader(io.TextIOWrapper(src, encoding="utf-8")):
                o, d = r["origin_zone_id"], r["destination_zone_id"]
                if (o.startswith(prefix_a) and d.startswith(prefix_b)) or (o.startswith(prefix_b) and d.startswith(prefix_a)):
                    for k in ("annual_total_trips", "mode_air", "mode_vehicle", "mode_rail", "purpose_work"):
                        acc[k] += float(r[k] or 0)
    return {"car": acc["mode_vehicle"] / 365, "air": acc["mode_air"] / 365, "rail_nhts": acc["mode_rail"] / 365,
            "work_share": acc["purpose_work"] / acc["annual_total_trips"]}


def metro_zone(prefix):
    """A zone dict (as texas/intercity.load_zones) merging every state part of a metro."""
    parts = []
    with open(os.path.join(ROOT, "data", "zones", "county_zones.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["zone_id"].startswith(prefix):
                parts.append(((float(r["lat"]), float(r["lon"])), int(r["pop_2020"])))
    people = sum(n for _, n in parts)
    at = (sum(a[0] * n for a, n in parts) / people, sum(a[1] * n for a, n in parts) / people)
    return {"name": prefix, "state": "", "pop": people, "at": at, "parts": parts, "fips": []}


def shares_without_rail(c, a, r, scale):
    """Car and air shares before rail, from today's car, air and rail shares, by inverting the nest
    (car alone; air and rail together with `scale`)."""
    n = a + r
    inclusive = math.log(n / c)                 # car's utility set to 0
    v_air = scale * math.log(a / n) + inclusive
    s_air = math.exp(v_air) / (1 + math.exp(v_air))
    return 1 - s_air, s_air


def rail_share(asc, base, za, zb, net, p):
    """Rail's share of all trips (car + air + rail) at constant `asc`, trip-weighted over purposes."""
    s_car, s_air = base["s_car0"], base["s_air0"]
    out = 0.0
    for purpose, w in (("work", base["work_share"]), ("nonwork", 1 - base["work_share"])):
        net.svc["asc_vs_car"] = asc
        odds = net.odds(za, zb, purpose, p)
        out += w * ic.nested_split(s_car, s_air, odds, p["nest_public_scale"])[2]
    return out


def fit(target_share, base, za, zb, net, p):
    lo, hi = -6.0, 6.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if rail_share(mid, base, za, zb, net, p) < target_share:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def comparable(c, p):
    d = nhts_pair(c["a"], c["b"])
    za, zb = metro_zone(c["a"]), metro_zone(c["b"])
    svc = dict(p["hsr"])
    svc["speed_kmh"] = c["track_km"] / (c["run_min"] / 60)   # the service's own end-to-end time
    svc["headway_min"] = c["headway"]
    svc["fare_fixed"], svc["fare_per_km"] = c["fare"], 0.0
    net = ic.RailNetwork({"A": c["sa"], "B": c["sb"]}, [("A", "B", c["track_km"])], svc, reach_km=80)
    kind, *vals = c["target"]
    res = {"name": c["name"], "car": d["car"], "air": d["air"], "rail_nhts": d["rail_nhts"], "work_share": d["work_share"],
           "asc": []}
    for v in vals:
        if kind == "market":   # rail rebuilt from air x the market share; shares without rail by inversion
            rail = d["air"] * v / (1 - v)
            tot = d["car"] + d["air"] + rail
            s_car0, s_air0 = shares_without_rail(d["car"] / tot, d["air"] / tot, rail / tot, p["nest_public_scale"])
            target = rail / tot
            res["rail"] = rail if v == vals[1] else res.get("rail")
        else:                  # a forecast from 2022's car and air: rail's riders (with induced trips) / the market
            tot = d["car"] + d["air"]
            s_car0, s_air0 = d["car"] / tot, d["air"] / tot
            target = v / 365 / (1 + svc["induced_share"]) / tot
            res["rail"] = v / 365 if v == vals[1] else res.get("rail")
        base = {"s_car0": s_car0, "s_air0": s_air0, "work_share": d["work_share"]}
        res["asc"].append(fit(target, base, za, zb, net, p))
    car_min = ic.car_los(ic.km(za["at"], zb["at"]), "work", p)[0]
    res["car_hours"] = car_min / 60
    return res


def write(rows, central, p):
    L = ["# Calibrating high-speed rail's constant", "",
         "Generated by `python study/calibrate_hsr.py`. The constant against car (`texas/intercity.json` "
         "hsr.asc_vs_car) is how much travellers like a train beyond its time, cost and frequency. It was an assumption "
         "(-0.5); the plan's ratios turn on it (`study/cabinet/audit.md`). Here it is fitted, inside the model's own "
         "structure, to American markets with fast trains today, with the same national NHTS 2022 data the Texas "
         "model uses for car and air, after the Phase 1 fixes (station access counted once; roads 1.1 times the "
         "straight line).", "",
         "| Market | Car trips a day (NHTS 2022) | Air | Rail (target) | Target | Constant: low | central | high |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        c = next(x for x in COMPARABLES if x["name"] == r["name"])
        kind, lo, mid, hi = c["target"]
        tgt = (f"{lo:.0%}-{hi:.0%} of air + rail (Amtrak)" if kind == "market"
               else f"{lo / 1e6:.1f}-{hi / 1e6:.1f}M riders a year (Brightline 2024)")
        L.append(f"| {r['name']} | {r['car']:,.0f} | {r['air']:,.0f} | {r['rail']:,.0f} | {tgt} | "
                 f"{min(r['asc']):+.2f} | {r['asc'][1]:+.2f} | {max(r['asc']):+.2f} |")
    lo = min(min(r["asc"]) for r in rows)
    hi = max(max(r["asc"]) for r in rows)
    L += ["", f"**Central constant: {central:+.2f}** (Brightline's central fit), **range {lo:+.2f} to {hi:+.2f}**. "
          f"Before: {p['_previous_asc']:+.2f}, an assumption.", "",
          "Each market says something different, which is why the plan carries a range, not a point:", "",
          "- **The Northeast** is a ceiling: rail habits a century old, downtowns where driving and parking are hard, "
          "and car-free households the model's car utility can't see (the pivot keeps each pair's car and air split, "
          "but not who can drive). Its constant soaks all of that up.",
          "- **Brightline** is a floor: car-dependent Florida, a 3.5-hour trip to an airport station, in its first full "
          "year, still ramping up, and a private operator's fares.",
          "- **Texas** is car-dependent like Florida, so the central value is Brightline's, though Texas's lines "
          "would be faster and serve downtowns. The range runs to the Northeast's high; the plan reports ratios at "
          "both ends (`study/timing.md`).", "",
          "Caveats: Amtrak's market shares are its own (2010-2014), on its own definitions; the NHTS's car and air "
          "counts are modelled from location data; Brightline's 2024 riders are reported by half-year and month, so the "
          "year is an estimate; the fit holds the rest of the model (time and cost weights, the nest) at its "
          "assumptions.", "",
          "Sources: [Amtrak air-rail shares (CNBC)](https://www.cnbc.com/id/48690841); "
          "[Amtrak 65%/52% (Progressive Railroading)](https://progressiverailroading.com/amtrak/news.aspx?id=24740); "
          "[Brightline first-half 2024 (Yahoo/WFTV)](https://www.yahoo.com/news/brightline-record-orlando-miami-ridership-172634417.html); "
          "[Brightline 2024 (iHeart)](https://wiod.iheart.com/alternate/amp/2025-05-05-brightline-doubles-ridership-in-2024-despite-losing-549-million-in-2024-despite).", ""]
    with open(os.path.join(ROOT, "study", "calibrate_hsr.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))


def main():
    p = ic.load_params()
    rows = [comparable(c, p) for c in COMPARABLES]
    central = next(r["asc"][1] for r in rows if "Brightline" in r["name"])
    p["_previous_asc"] = p["hsr"]["asc_vs_car"]
    for r in rows:
        print(f"{r['name']}: car {r['car']:,.0f}/day, air {r['air']:,.0f}, NHTS rail {r['rail_nhts']:,.0f}, "
              f"car {r['car_hours']:.1f} h; asc {[round(a, 3) for a in r['asc']]}")
    write(rows, central, p)
    if "--save" in sys.argv:
        lo = min(min(r["asc"]) for r in rows)
        hi = max(max(r["asc"]) for r in rows)
        path = ic.PARAMS
        with open(path, encoding="utf-8") as f:
            text = f.read()
        q = json.loads(text)
        old = q["hsr"]["asc_vs_car"]
        text = text.replace(f'"asc_vs_car": {json.dumps(old)},\n    "speed_kmh": 260',
                            f'"asc_vs_car": {round(central, 3)},\n    "asc_range": [{round(lo, 3)}, {round(hi, 3)}],\n    "speed_kmh": 260', 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"saved asc_vs_car {central:+.3f} (range {lo:+.3f} to {hi:+.3f}) to {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
