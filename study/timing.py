"""Timing: every project, urban and intercity, under the one statewide budget, 2025-2100.

    python study/timing.py

Writes study/timing.md and docs/data/timeline.json (the site's data).

1. Projects.
   - Urban: each line the generator chose in the 25 metros (urban/generated/<id>/candidates.csv),
     its daily trips the model's metro total (study/urban_metros.md) shared out by the full model's
     value of each line (model_trips). Within a metro, lines open in the generator's order, best
     value per $ first.
   - High-speed rail: the 14 corridors in study/hsr_options.md's order, each counted on top of the
     ones before it (2050 travel).
   - Conventional: the seven corridors at four trains a day (study/interstate_rail.md), Kansas
     City after the Heartland Flyer and Memphis after I-20.
2. Value. What travellers gain, in dollars, from the same logit models that predict the riders:
   - intercity: the logsum gain of every traveller on every pair (texas/intercity.py logsum_gain);
   - urban: DFW Transit's commute logit, where transit's share is small, gains one money
     coefficient's worth per new transit trip, 1 / URBAN_B_PER_DOLLAR = $8, on 300 weekday-
     equivalent days a year (dfw-transit config.json); non-commute trips are assumed to gain as much.
   Fares and operating cost (urban fares URBAN_FARE a trip; urban operating cost includes the feeder buses
   the network adds, at DFW Transit's $ per feeder boarding). Benefit-cost ratio over 50 years at
   3% (PV_FACTOR): travellers' gain (plus any operating surplus) over capital plus the operating
   deficit, valued over the 50 years from each project's opening, with travel growing: intercity
   projects modelled at 2030, 2050, 2075 and 2100 travel (each county's trend, tools/build_growth.py);
   urban ones follow each metro's own model runs in 2026, 2050 and 2100
   (its growth and the 2 million plan's station-area land use; study/urban_metros.py).
3. Schedule. Dallas-Fort Worth keeps DFW Transit's $2.3B a year (its own plan and timetable); the rest
   of the $9.0B a year goes to the other projects, best ratio first (a project opens no earlier than the
   ones its value depends on), each spending evenly over its construction years and opening at the end, with
   carryover and no borrowing: spending to date never exceeds budget to date. The budget is spent
   whether or not a project's ratio reaches 1 (the plan spends DFW's rate); the ratios say which
   projects pay for themselves in travellers' gains alone.
"""
import copy
import csv
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "study"))
from texas import conventional as cv, finance, hsr, intercity as ic  # noqa: E402
import interstate_rail as ir  # noqa: E402

YEARS = list(range(2025, 2101))
DFW_MUSD, DFW_POP = 2300, 7_468_799
TEXAS_POP_2020 = 29_145_505
STATE_MUSD = DFW_MUSD / DFW_POP * TEXAS_POP_2020         # $9.0B a year
OTHER_MUSD = STATE_MUSD - DFW_MUSD
URBAN_B_PER_DOLLAR, URBAN_DAYS, URBAN_FARE = 0.125, 300, 1.25
PV_FACTOR = (1 - 1.03 ** -50) / 0.03                      # 25.7
BUILD_YEARS = {"metro": 5, "brt": 2, "commuter": 4, "streetcar": 3, "hsr": 8, "conventional": 3}
HSR_YEAR = 2050
URBAN_BASE_YEAR = HSR_YEAR   # urban values at 2050 travel too, when the metro has its 2050 run
HSR_HEADWAY = 30
METRO_YEARS = 30          # the metros-first scenario: each metro's budget over this many years from 2025
SCENARIOS = (("ratio", "Best ratio first"), ("metros_first", "Metros first"), ("whole_map", "The whole map"))
# The whole map (study/hsr_buildout.md, Phase 2): central unit costs with the learning curve, the thin legs
# built to lighter standards, and a ring-fenced Connectivity Program for the branches (texas/finance.py)
WHOLE_MAP_HSR = {"case": "central", "learning": True, "drawn": True,
                 "standards": {"OKC": "S2", "LRD": "S3", "VALLEY": "S3", "MFE": "S3", "BIGC": "S3", "PANH": "S4", "WEST": "S4"}}
UPGRADE_TRIPS = 3e6   # a leg built below full standard earns an upgrade at this many trips a year
GATE_YEARS = 3        # a Connectivity Program branch starts only after its trunk has run this long (study/hsr_buildout.md)


URBAN_GENERATED = os.path.join(ROOT, "urban", "generated")   # the metros' networks (study/fixed_point.py points it elsewhere)


def texas_pop():
    """{year: Texas population} from the county trend, linear between its years."""
    tot = {}
    with open(os.path.join(ROOT, "data", "zones", "county_growth.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["county_fips"].startswith("48"):
                for k, v in r.items():
                    if k.startswith("pop_"):
                        tot[int(k[4:])] = tot.get(int(k[4:]), 0.0) + float(v)
    ks = sorted(tot)
    out = {}
    for y in range(2020, 2101):
        lo = max(k for k in ks if k <= y)
        hi = min(k for k in ks if k >= y)
        out[y] = tot[lo] if lo == hi else tot[lo] + (tot[hi] - tot[lo]) * (y - lo) / (hi - lo)
    return out


BEN = json.load(open(os.path.join(ROOT, "texas", "benefits.json"), encoding="utf-8"))
LT = BEN["land_tax"]


def ext_per_vkm(kind):
    return sum(BEN["car_externality_per_vkm"][kind].values())


def annuity(rate, years):
    return (1 - (1 + rate) ** -years) / rate


URBAN_VKM_PER_TRIP = BEN["urban_from_car_share"] * BEN["urban_car_km_per_new_trip"] / BEN["urban_car_occupancy"]
URBAN_WIDER_PER_TRIP = URBAN_VKM_PER_TRIP * ext_per_vkm("urban")      # $ a new urban trip


def land_tax(pop, jobs, mode):
    """(a year, bond at opening) $M from a new line's station district: TIRZ on the uplift plus PID on
    all property (texas/benefits.json land_tax)."""
    value = pop * LT["value_per_resident"] + jobs * LT["value_per_job"]
    year = value * (LT["uplift"].get(mode, 0.0) * LT["tirz_tax_rate"] + LT["pid_rate"]) / 1e6
    return year, year * annuity(LT["bond_rate"], LT["years"])


def districts(metro_id, order):
    """{cand_id: (people, jobs, new stations)} within land_tax.radius_km of each project's new stations;
    a station, and a block group, belongs to the first project (in `order`) that reaches it."""
    import numpy as np
    d = os.path.join(URBAN_GENERATED, metro_id)
    lines = list(csv.DictReader(open(os.path.join(d, "lines.csv"), encoding="utf-8")))
    cand = {}
    for r in lines:
        m = re.search(r"generated \(([A-Z]\d+)\)", r["notes"] or "")
        if m:
            cand[r["line_id"]] = m.group(1)
    stops = list(csv.DictReader(open(os.path.join(d, "line_stops.csv"), encoding="utf-8")))
    st = {r["station_id"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open(os.path.join(d, "stations.csv"), encoding="utf-8"))}
    existing = {r["station_id"] for r in stops if r["line_id"] not in cand}
    zs = list(csv.DictReader(open(os.path.join(ROOT, "urban", "data", "metros", metro_id, "zones.csv"), encoding="utf-8")))
    lat = np.array([float(z["lat"]) for z in zs])
    lon = np.array([float(z["lon"]) for z in zs])
    pop = np.array([float(z["pop"] or 0) for z in zs])
    jobs = np.array([float(z["jobs"] or 0) for z in zs])
    taken = np.zeros(len(zs), dtype=bool)
    seen = set(existing)
    out = {}
    by_line = {}
    for r in stops:
        if r["line_id"] in cand:
            by_line.setdefault(cand[r["line_id"]], []).append(r["station_id"])
    for cid in order:
        P = J = 0.0
        n = 0
        for sid in by_line.get(cid, []):
            if sid in seen or sid not in st:
                continue
            seen.add(sid)
            n += 1
            la, lo = st[sid]
            dist = np.hypot((lat - la) * 111.2, (lon - lo) * 111.2 * math.cos(math.radians(la)))
            near = (dist <= LT["radius_km"]) & ~taken
            P += pop[near].sum()
            J += jobs[near].sum()
            taken |= near
        out[cid] = (float(P), float(J), n)
    return out


def shift(res, p):
    """(car vehicle-km, air passenger-km) a day that rail takes off the road and out of the air."""
    vkm = sum((r["base"]["car"] - r["new"]["car"]) * r["km"] for r in res.values()) * BEN["intercity_car_circuity"] / \
        BEN["intercity_car_occupancy"]
    pkm = sum((r["base"]["air"] - r["new"]["air"]) * r["km"] for r in res.values())
    return vkm, pkm


def intercity_wider(vkm_day, pkm_day):
    return (vkm_day * ext_per_vkm("intercity") + pkm_day * BEN["air_externality_per_pkm"]) * 365 / 1e6


# ---------------------------------------------------------------- projects
def urban_trajectory(s):
    """(new daily trips in the base year, {year: trips / base-year trips}, base year) for one metro's network from
    its summary.json: the model runs on today's land use (2026) and, with the metro's own growth and the station-area
    land use, in 2050 and 2100 (study/urban_metros.py), linear between them. New = the network's trips less today's
    lines' under the same growth. The base year is 2050, as the intercity layer's; without the future runs, 2026
    and Texas's population growth."""
    today = max(s.get("trips", 0) - s.get("trips_today", 0), 0)
    fut = s.get("future") or {}
    if not fut:
        return today, None, 2026
    pts = {2026: today, **{int(y): max(f["trips"] - f["trips_today_lines"], 0) for y, f in fut.items()}}
    ks = sorted(pts)
    base = pts[URBAN_BASE_YEAR]
    traj = {}
    for y in range(ks[0], ks[-1] + 1):
        lo = max(k for k in ks if k <= y)
        hi = min(k for k in ks if k >= y)
        v = pts[lo] if lo == hi else pts[lo] + (pts[hi] - pts[lo]) * (y - lo) / (hi - lo)
        traj[y] = v / base if base else 0.0
    return base, traj, URBAN_BASE_YEAR


def urban_projects():
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))
    out = []
    for m in reg["metros"]:
        d = os.path.join(URBAN_GENERATED, m["id"])
        s = json.load(open(os.path.join(d, "summary.json"), encoding="utf-8"))
        cpath = os.path.join(d, "candidates.csv")
        if not os.path.exists(cpath):   # no corridor dense enough for a candidate (study/urban_metros.md)
            continue
        rows = [r for r in csv.DictReader(open(cpath, encoding="utf-8")) if r["status"] == "chosen"]
        rows.sort(key=lambda r: int(r["order"]))
        # each line's share of the metro's riders: the full model's value of it (model_trips, DFW Transit's
        # metro/modelselect.py) when the generator chose by the full model, else the sketch's new trips
        share_of = (lambda r: float(r["model_trips"])) if all(r.get("model_trips") for r in rows) else \
            (lambda r: float(r["new_trips"]))
        sketch = sum(share_of(r) for r in rows)
        model, traj, base_year = urban_trajectory(s)
        # the feeder buses the network adds (study/urban_metros.py), in the base year, shared out like the riders
        feeder = ((s.get("future") or {}).get(str(base_year)) or s).get("feeder_opex_musd", 0.0)
        dist = districts(m["id"], [r["cand_id"] for r in rows])
        prev = None
        for r in rows:
            trips = model * share_of(r) / sketch if sketch else 0.0
            dp, dj, dn = dist.get(r["cand_id"], (0.0, 0.0, 0))
            tax_year, bond = land_tax(dp, dj, r["mode"])
            benefit = trips / URBAN_B_PER_DOLLAR * URBAN_DAYS / 1e6
            fares = trips * URBAN_FARE * URBAN_DAYS / 1e6
            pid = f"{m['id']}:{r['cand_id']}"
            out.append({"id": pid, "layer": "urban", "metro": m["id"], "metro_name": m["name"].split(",")[0],
                        "name": r["name"], "mode": r["mode"], "km": float(r["km"]),
                        "capital": float(r["capital_musd"]),
                        "opex": float(r["opex_musd_yr"]) + max(feeder, 0.0) * (share_of(r) / sketch if sketch else 0.0),
                        "fares": fares,
                        "benefit": benefit, "trips_day": trips, "trips_year": trips * URBAN_DAYS,
                        "wider": trips * URBAN_WIDER_PER_TRIP * URBAN_DAYS / 1e6,
                        "agglom": benefit * BEN["agglomeration_share"]["urban"],
                        "district_pop": dp, "district_jobs": dj, "new_stations": dn,
                        "land_tax_year": tax_year, "bond": min(bond, float(r["capital_musd"])),
                        "base_year": base_year, "traj": traj, "after": [prev] if prev else [], "build": BUILD_YEARS[r["mode"]]})
            prev = pid
    return out


def hsr_projects(log=print, asc=None, year=HSR_YEAR):
    order = []
    names = {v[0]: k for k, v in hsr.CORRIDORS.items()}
    with open(os.path.join(ROOT, "study", "hsr_options.md"), encoding="utf-8") as f:
        for line in f:
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(c) == 9 and c[0].isdigit() and c[1] in names:
                order.append(names[c[1]])
    p = ic.load_params()
    if asc is not None:   # a sensitivity run at another constant against car
        p["hsr"]["asc_vs_car"] = asc
    zones = ic.load_zones()
    base = ic.base_trips(zones, p)
    tx = {k: v for k, v in base.items() if "TX" in (zones[k[0]]["state"], zones[k[1]]["state"])}
    growth = ic.zone_growth(zones, year)
    prev = {"rail": 0.0, "benefit": 0.0, "fares": 0.0, "air": 0.0, "flights": 0.0, "vkm": 0.0, "pkm": 0.0}
    out = []
    for i, cid in enumerate(order):
        built = order[:i + 1]
        net = ic.RailNetwork({s: hsr.point(s) for s in hsr.stations_of(built)}, hsr.network_links(built, with_speed=True),
                             p["hsr"], services=hsr.services_for(built))
        res = ic.run(tx, zones, p, net, growth, year=year)
        tot = {"rail": sum(r["new"]["rail"] + r["new"]["induced"] for r in res.values()),
               "benefit": sum(r["benefit_usd"] for r in res.values()),
               "air": sum(r["base"]["air"] - r["new"]["air"] for r in res.values()),
               "flights": sum(ic.flights_per_day(r["base"]["air"] - r["new"]["air"], p) for r in res.values()),
               "fares": 0.0}
        tot["vkm"], tot["pkm"] = shift(res, p)
        for k, r in res.items():
            if r["new"]["rail"] > 0:
                los = net.los(zones[k[0]], zones[k[1]], "nonwork", p)
                if los:
                    tot["fares"] += (r["new"]["rail"] + r["new"]["induced"]) * los[2]
        d = {k: tot[k] - prev[k] for k in tot}
        prev = tot
        cap = hsr.capital_musd([cid], built=order[:i])
        out.append({"id": f"hsr:{cid}", "layer": "hsr", "name": hsr.CORRIDORS[cid][0], "mode": "hsr",
                    "km": hsr.track_km([cid]), "capital": cap,
                    # the track outside Texas: paid by the state it runs in, with the federal money that comes with it
                    "outside": finance.paid_by_others(cap, finance.corridor_shares(cid)),
                    # the network's operating cost as run in service patterns (hsr.services_for), with it less without it
                    "opex": hsr.pattern_opex_musd(built) - (hsr.pattern_opex_musd(order[:i]) if i else 0.0),
                    "fares": d["fares"] * 365 / 1e6, "benefit": d["benefit"] * 365 / 1e6,
                    "trips_day": d["rail"], "trips_year": d["rail"] * 365, "air_day": d["air"], "flights_day": d["flights"],
                    "wider": intercity_wider(d["vkm"], d["pkm"]),
                    "agglom": d["benefit"] * 365 / 1e6 * BEN["agglomeration_share"]["hsr"],
                    # it opens no earlier than the trunk it hangs off (hsr.REQUIRES); its value was measured with the
                    # corridors before it in the ranking built, an approximation when it opens before some of them
                    "base_year": HSR_YEAR, "after": [f"hsr:{r}" for r in hsr.REQUIRES.get(cid, [])],
                    "build": BUILD_YEARS["hsr"], "standard": hsr.standard_of(cid),
                    "chain": hsr.CORRIDORS[cid][1]})
        if log:
            log(f"  hsr {cid}: +{d['rail'] * 365 / 1e6:.2f}M trips, ${d['benefit'] * 365 / 1e6:,.0f}M benefit a year")
    return out


def conventional_projects(log=print, year=HSR_YEAR):
    p = ic.load_params()
    zones = ic.load_zones()
    base = ic.base_trips(zones, p)
    tx = {k: v for k, v in base.items() if "TX" in (zones[k[0]]["state"], zones[k[1]]["state"])}
    trips, _, _ = ir.add_monterrey(tx, zones, p, ir.BORDER_FACTOR)
    growth = ic.zone_growth({k: v for k, v in zones.items() if k != "MTY"}, year)
    growth["MTY"] = growth["41700_TX"]
    out = []

    def totals(ids, tpd):
        if not ids or tpd <= 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        rail, fares, air, res = ir.evaluate(ids, tpd, trips, zones, p, growth)
        return (rail, fares, air, sum(r["benefit_usd"] for r in res.values())) + shift(res, p)

    for cid, under, against in ir.PLAN:
        today = cv.CORRIDORS[cid][2]
        after = totals(under + [cid], 4)
        before = totals(under, 4) if against == "under" else (totals(under + [cid], today) if against == "today" else (0,) * 6)
        rail, fares, air, ben, vkm, pkm = (after[i] - before[i] for i in range(6))
        opex = cv.opex_musd(cid, 4) - (cv.opex_musd(cid, today) if against == "today" else 0.0)
        dep = {"KC": ["conv:FLYER"], "EAGLE": ["conv:I20"]}.get(cid, [])
        cap = cv.capital_musd(cid, 4, p["conventional"])
        out.append({"id": f"conv:{cid}", "layer": "conventional", "name": cv.CORRIDORS[cid][0], "mode": "conventional",
                    "km": cv.route_km(cid), "capital": cap, "opex": opex,
                    # the track outside Texas is paid by the state it runs in, with the federal money that comes with
                    # it; Mexico pays for its side (texas/finance.py paid_by_others)
                    "outside": finance.paid_by_others(cap, finance.conventional_shares(cid)),
                    "fares": fares * 365 / 1e6, "benefit": ben * 365 / 1e6, "trips_day": rail, "trips_year": rail * 365,
                    "air_day": air, "wider": intercity_wider(vkm, pkm),
                    "agglom": ben * 365 / 1e6 * BEN["agglomeration_share"]["conventional"],
                    "base_year": HSR_YEAR, "after": dep, "build": BUILD_YEARS["conventional"],
                    "chain": cv.CORRIDORS[cid][1]})
        if log:
            log(f"  conventional {cid}: +{rail * 365 / 1e6:.2f}M trips, ${ben * 365 / 1e6:,.0f}M benefit a year")
    return out


TRAVEL_YEARS = (2030, 2050, 2075, 2100)   # intercity travel years modelled (zone_growth has each county's trend)


def with_trajectories(make, log=print):
    """Intercity projects from `make(year=...)` at HSR_YEAR, each with its own travel trajectory
    (traj: {year: value / value at HSR_YEAR}) from the same projects modelled at TRAVEL_YEARS, linear
    between them, flat before the first and after the last. Before, every intercity project was scaled
    from 2050 by Texas's population, so a corridor to a fast-growing metro grew like one to a slow one."""
    runs = {y: make(log=log if y == HSR_YEAR else None, year=y) for y in TRAVEL_YEARS}
    base = runs[HSR_YEAR]
    for i, pr in enumerate(base):
        def val(q):
            return q["benefit"] + q.get("wider", 0.0) + q.get("agglom", 0.0)
        b0 = val(pr)
        pts = {y: (val(runs[y][i]) / b0 if b0 > 0 else 1.0) for y in TRAVEL_YEARS}
        ks = sorted(pts)
        traj = {}
        for y in range(2025, 2101):
            if y <= ks[0]:
                traj[y] = pts[ks[0]]
            elif y >= ks[-1]:
                traj[y] = pts[ks[-1]]
            else:
                lo = max(k for k in ks if k <= y)
                hi = min(k for k in ks if k >= y)
                traj[y] = pts[lo] if lo == hi else pts[lo] + (pts[hi] - pts[lo]) * (y - lo) / (hi - lo)
        pr["traj"] = traj
        pr["travel_points"] = {str(y): round(v, 3) for y, v in pts.items()}
    return base


# ---------------------------------------------------------------- Dallas-Fort Worth
def dfw_layer():
    """DFW Transit's 2 million riders plan (data/dfw/dfw_plan.json, tools/build_dfw.py) as a fixed layer:
    its own timetable and spending. Its trips and operating cost are what it adds to the current track;
    they are valued like the other metros'. Its new stations' land tax is borrowed against when they
    open, like the other metros' lines, and since DFW's timetable is fixed the proceeds go to the
    statewide pot. Returns {year: {...}} and the plan."""
    import numpy as np
    plan = json.load(open(os.path.join(ROOT, "data", "dfw", "dfw_plan.json"), encoding="utf-8"))
    z = plan["zones"]
    lat = np.array([q["lat"] for q in z])
    lon = np.array([q["lon"] for q in z])
    pop = np.array([q["pop"] for q in z])
    jobs = np.array([q["jobs"] for q in z])
    taken = np.zeros(len(z), dtype=bool)
    bonds, tax_year = {}, {}
    for st in sorted(plan["stations"], key=lambda q: q["year"]):
        if st["year"] <= YEARS[0]:
            dist = np.hypot((lat - st["lat"]) * 111.2, (lon - st["lon"]) * 111.2 * math.cos(math.radians(st["lat"])))
            taken |= dist <= LT["radius_km"]   # today's station areas: already priced in
            continue
        dist = np.hypot((lat - st["lat"]) * 111.2, (lon - st["lon"]) * 111.2 * math.cos(math.radians(st["lat"])))
        near = (dist <= LT["radius_km"]) & ~taken
        taken |= near
        mode = max(st["modes"].split(";"), key=lambda m: LT["uplift"].get(m, 0.0))
        yr, bond = land_tax(float(pop[near].sum()), float(jobs[near].sum()), mode)
        bonds[st["year"]] = bonds.get(st["year"], 0.0) + bond
        tax_year[st["year"]] = tax_year.get(st["year"], 0.0) + yr
    rows = {}
    for r in plan["yearly"]:
        y = r["year"]
        if y not in YEARS:
            continue
        new = max(r["trips_day"] - (r["base_trips_day"] or r["trips_day"]), 0.0)
        ben = new / URBAN_B_PER_DOLLAR * URBAN_DAYS / 1e6
        rows[y] = {"spend": r["spend"], "trips_day": new, "benefit": ben,
                   "wider": new * URBAN_WIDER_PER_TRIP * URBAN_DAYS / 1e6 + ben * BEN["agglomeration_share"]["urban"],
                   "opex": r["opex"] - (r["base_opex"] or 0.0), "fares": new * URBAN_FARE * URBAN_DAYS / 1e6,
                   "bond": bonds.get(y, 0.0)}
    return rows, plan, sum(tax_year.values())


def other_budget(dfw):
    """$M a year for everything outside DFW: the statewide rate minus what DFW spends that year, plus
    DFW's station-area bonds."""
    return {y: STATE_MUSD - dfw[y]["spend"] + dfw[y]["bond"] for y in YEARS}


CONNECT = [   # (statewide station, layer, (lat, lon))
    ("Dallas (high-speed, beside Union Station)", "hsr", hsr.point("Dallas")),
    ("Fort Worth (high-speed)", "hsr", hsr.point("Fort Worth")),
    ("Denton (high-speed, to Oklahoma City)", "hsr", hsr.point("Denton")),
    ("Dallas Union Station (conventional, I-20)", "conventional", cv.point("Dallas")),
    ("Fort Worth Central (conventional, Heartland Flyer)", "conventional", cv.point("Fort Worth")),
]


def connections(plan, opens=None):
    """For each statewide station in DFW, DFW's nearest station open by the time the statewide line opens
    (`opens`: {name: year}; any year if not given): name, distance, opening year, modes."""
    out = []
    for name, layer, (la, lo) in CONNECT:
        by = (opens or {}).get(name) or 9999
        cands = [q for q in plan["stations"] if q["year"] <= by] or plan["stations"]
        best = min(cands, key=lambda q: ic.km((la, lo), (q["lat"], q["lon"])))
        out.append({"name": name, "layer": layer, "dfw": best["name"], "km": ic.km((la, lo), (best["lat"], best["lon"])),
                    "year": best["year"], "modes": best["modes"].replace(";", ", ")})
    return out


# ---------------------------------------------------------------- schedule
_POP = {}


def growth_at(pr, year):
    """A project's travel in `year` relative to its base year (the year its values were estimated):
    its metro's model runs for an urban line (urban_trajectory), Texas's population for intercity
    ones. Flat after 2100, the last year either reaches."""
    y = min(year, 2100)
    if pr.get("traj"):
        return pr["traj"].get(y, pr["traj"][max(pr["traj"])])
    if not _POP:
        _POP.update(texas_pop())
    return _POP[y] / _POP[pr["base_year"]]


def uplift(pr):
    """Mean travel over the 50 years from the year a project is valued from (`value_year`: its
    opening year once scheduled, else its base year), discounted at 3%, relative to its base year:
    the factor on its yearly benefits and fares in the ratio. Before Phase 1 the ratio held 2050's
    travel for 50 years, so a line opening in 2090 was valued on 2050 Texas (study/cabinet/audit.md)."""
    y0 = pr.get("value_year") or pr["base_year"]
    return sum(growth_at(pr, y0 + t - 1) / 1.03 ** t for t in range(1, 51)) / PV_FACTOR   # as PV_FACTOR, end of year


def ratio(pr):
    """Benefit-cost ratio over the 50 years from opening at 3%: all benefits (travellers' gain, wider
    benefits, agglomeration, plus any operating surplus) over capital plus the operating deficit
    (operating cost minus fares), benefits and fares growing with travel (uplift), operating cost
    flat. Land-tax bonds change who pays, not the ratio."""
    u = uplift(pr)
    pr["uplift"] = u
    margin = pr["fares"] * u - pr["opex"]
    pr["all_benefit"] = pr["benefit"] + pr.get("wider", 0.0) + pr.get("agglom", 0.0)
    pr["net"] = pr["all_benefit"] + pr["fares"] - pr["opex"]
    pv_benefit = (pr["all_benefit"] * u + max(margin, 0.0)) * PV_FACTOR
    pv_cost = pr["capital"] + max(-margin, 0.0) * PV_FACTOR
    pr["bcr"] = pv_benefit / pv_cost if pv_cost > 0 else 0.0
    pr["bcr_users"] = (pr["benefit"] * u + max(margin, 0.0)) * PV_FACTOR / pv_cost if pv_cost > 0 else 0.0
    return pr["bcr"]


def settle(projects, plan_fn, rounds=6):
    """Run a scheduler until opening years settle: each project is valued from its opening year (or
    2100 if it doesn't open by then), which can change the order, which changes the years. Returns
    the last (built, spend)."""
    for p in projects:
        p["value_year"] = None
    for _ in range(rounds):
        built, spend = plan_fn(projects)
        years = {p["id"]: p.get("open") or YEARS[-1] for p in projects}
        if all(p.get("value_year") == years[p["id"]] for p in projects):
            break
        for p in projects:
            p["value_year"] = years[p["id"]]
    for p in projects:
        ratio(p)
    return built, spend


PIPELINE_KM = None   # a cap on high-speed km under construction at once (study/session2_tests.py: a steady pipeline); None: none


def schedule(projects, budget, spend=None, order=None, busy=None):
    """Schedule `projects` (sets each one's start and open years; None if it doesn't fit by 2100).
    `budget`: $M a year, a number or {year: $M}; `spend`: {year: $M} already committed (counted
    against the same budget). Each project starts in the first year its spending fits: cumulative
    spending never exceeds cumulative budget (carryover, no borrowing), no earlier than what it depends
    on starts, and it opens no earlier than that opens. Order: best ratio first (a dependent's priority
    capped at its parent's), or the given list `order`. With PIPELINE_KM, a high-speed project also
    starts only when the km under construction each year it builds (`busy`, {year: km}, updated) stay
    within it."""
    by = {p["id"]: p for p in projects}
    busy = {} if busy is None else busy
    for p in projects:
        ratio(p)

    def prio(p):
        r = p["bcr"]
        for d in p["after"]:
            if d in by:
                r = min(r, prio(by[d]))
        return r
    for p in projects:
        p["priority"] = prio(p)
    per_year = budget if isinstance(budget, dict) else {y: budget for y in YEARS}
    cum_budget, c = {}, 0.0
    for y in YEARS:
        c += per_year.get(y, 0.0)
        cum_budget[y] = c
    spend = dict(spend) if spend else {y: 0.0 for y in YEARS}
    built = []
    for p in (order if order is not None else sorted(projects, key=lambda p: -p["priority"])):
        p["start"] = p["open"] = None
        deps = [by[d] for d in p["after"] if d in by]
        if any(d["open"] is None for d in deps):
            continue
        # a project's value assumes the ones before it are there: it may be built alongside them, but
        # opens no earlier than they do
        first = max([YEARS[0]] + [max(d["start"], d["open"] - p["build"]) for d in deps])
        if p.get("gate_years"):   # the Auditor's gate: a branch starts only after its trunk has run this long
            first = max([first] + [d["open"] + p["gate_years"] for d in deps])
        # land-tax bonds pay part of an urban line; federal and partner-state money part of a high-speed one
        per = (p["capital"] - p.get("bond", 0.0) - p.get("outside", 0.0)) / p["build"]
        for y in range(first, YEARS[-1] - p["build"] + 1):   # opens by the last year
            if PIPELINE_KM and p["layer"] == "hsr" and any(
                    busy.get(y + k, 0.0) + p["km"] > PIPELINE_KM for k in range(p["build"])) and \
                    p["km"] <= PIPELINE_KM:
                continue
            trial = dict(spend)
            for k in range(p["build"]):
                trial[y + k] += per
            cum_s, ok = 0.0, True
            for yy in YEARS:
                cum_s += trial[yy]
                if cum_s > cum_budget[yy] + 1e-6:
                    ok = False
                    break
            if ok:
                spend = trial
                p["start"], p["open"] = y, y + p["build"]
                if p["layer"] == "hsr":
                    for k in range(p["build"]):
                        busy[y + k] = busy.get(y + k, 0.0) + p.get("km", 0.0)
                built.append(p)
                break
    return built, spend


def metro_pop(metro_id, y):
    """A metro's people in `y`: its generated network's model runs (today, 2050, 2100), straight lines
    between, flat after 2100; None without them."""
    p = os.path.join(URBAN_GENERATED, metro_id, "summary.json")
    if not os.path.exists(p):
        return None
    s = json.load(open(p, encoding="utf-8"))
    pts = {2020: s.get("pop")}   # the census population the network was generated on
    pts.update({int(k): v.get("pop") for k, v in (s.get("future") or {}).items()})
    pts = {k: v for k, v in pts.items() if v}
    if not pts:
        return None
    ks = sorted(pts)
    if y <= ks[0]:
        return pts[ks[0]]
    if y >= ks[-1]:
        return pts[ks[-1]]
    lo = max(k for k in ks if k <= y)
    hi = min(k for k in ks if k >= y)
    return pts[lo] if lo == hi else pts[lo] + (pts[hi] - pts[lo]) * (y - lo) / (hi - lo)


def metro_stream(m, n, pop=None):
    """{year: $M} for a metro over its first n years from 2025: its budget (urban/metros.json budget_musd,
    DFW's rate per 2020 resident) spread evenly, times how much faster than Texas it has grown by that year
    (study/second_session.md, item 8: a metro that quadruples, as Austin does, gets the stream of its share
    of the state as it grows, not as it was in 2020). A metro growing as fast as Texas keeps its stream; the
    statewide budget doesn't change. `pop`: Texas's people by year (texas_pop); evenly without it or
    without the metro's own trajectory."""
    pop = pop or texas_pop()
    base = m["budget_musd"] / n
    p0 = metro_pop(m["id"], 2020)
    out = {}
    for y in YEARS:
        if y >= YEARS[0] + n:
            out[y] = 0.0
            continue
        py = metro_pop(m["id"], y)
        out[y] = base * ((py / p0) / (pop[y] / pop[2020]) if p0 and py and 2020 in pop else 1.0)
    return out


def metros_first(projects, budget, pop=None):
    """Scenario: each metro gets its own stream, its generator budget (urban/metros.json budget_musd)
    over METRO_YEARS from 2025 (the whole horizon for the build-out and policy metros), shared out by its
    growth against Texas's each year (metro_stream), and builds its lines in the generator's order as that stream
    allows. Intercity projects take what's left of the statewide budget (including whatever the metros
    don't spend), best ratio first."""
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))
    spend = {y: 0.0 for y in YEARS}
    built = []
    for m in reg["metros"]:
        ps = [p for p in projects if p.get("metro") == m["id"]]
        if not ps:
            continue
        n = len(YEARS) if m.get("buildout") or m.get("policies") else METRO_YEARS   # 75-year budgets cover DFW's whole horizon
        stream = metro_stream(m, n, pop)
        b, s_m = schedule(ps, stream, order=ps)   # generator order (the list is already in it)
        built += b
        for y in YEARS:
            spend[y] += s_m[y]
    inter = [p for p in projects if p["layer"] != "urban"]
    b, spend = schedule(inter, budget, spend=spend)
    for p in projects:
        ratio(p)
    return built + b, spend


def yearly(projects, spend, pop, dfw):
    rows = []
    for y in YEARS:
        open_ = [p for p in projects if p.get("open") and p["open"] <= y]
        f = {p["id"]: p["traj"].get(y, 0.0) if p.get("traj") else pop[y] / pop[p["base_year"]]
             for p in open_}
        d = dfw[y]
        rows.append({"year": y, "spend": spend[y], "dfw_spend": d["spend"],
                     "land_tax": sum(p.get("bond", 0.0) for p in projects if p.get("open") == y) + d["bond"],
                     "urban_trips_day": sum(p["trips_day"] * f[p["id"]] for p in open_ if p["layer"] == "urban"),
                     "dfw_trips_day": d["trips_day"],
                     "intercity_trips_year": sum(p["trips_year"] * f[p["id"]] for p in open_ if p["layer"] != "urban"),
                     "benefit": sum(p["benefit"] * f[p["id"]] for p in open_) + d["benefit"],
                     "wider": sum((p.get("wider", 0) + p.get("agglom", 0)) * f[p["id"]] for p in open_) + d["wider"],
                     "flights_day": sum(p.get("flights_day", 0) * f[p["id"]] for p in open_),
                     "opex": sum(p["opex"] for p in open_) + d["opex"],
                     "fares": sum(p["fares"] * f[p["id"]] for p in open_) + d["fares"]})
    return rows


def pv(rows, key):
    """Present value in 2025 at 3% of a yearly series."""
    return sum(r[key] / 1.03 ** (r["year"] - YEARS[0]) for r in rows)


RISK_DRAWS, RISK_SEED = 4000, 2026
RISK_SIGMA = {"cost": 0.26, "riders": 0.40}
STRESS = {"cost": 1.45, "riders": 0.70}


def ratio_at(pr, cost=1.0, riders=1.0):
    """A project's ratio with its capital times `cost` and its riders (benefits and fares) times
    `riders`, valued as ratio() from the same year."""
    u = pr.get("uplift") or uplift(pr)
    margin = pr["fares"] * u * riders - pr["opex"]
    ben = (pr["benefit"] + pr.get("wider", 0.0) + pr.get("agglom", 0.0)) * u * riders
    cost_pv = pr["capital"] * cost + max(-margin, 0.0) * PV_FACTOR
    return (ben + max(margin, 0.0)) * PV_FACTOR / cost_pv if cost_pv > 0 else 0.0


def risk(projects):
    """P10 / P50 / P90 of each project's ratio over draws of its cost and riders (lognormal around the
    model's own estimate, spreads from the reference class, RISK_SIGMA: rail cost overruns' spread,
    Flyvbjerg 2003; ridership errors' spread, Flyvbjerg 2005), and the Auditor's stress gate: cost
    x1.45 and riders x0.70 at once (study/hsr_buildout.md, guardrail 3)."""
    import random
    rnd = random.Random(RISK_SEED)
    draws = [(math.exp(rnd.gauss(0, RISK_SIGMA["cost"])), math.exp(rnd.gauss(0, RISK_SIGMA["riders"])))
             for _ in range(RISK_DRAWS)]
    for pr in projects:
        rs = sorted(ratio_at(pr, c, r) for c, r in draws)
        pr["bcr_p10"], pr["bcr_p50"], pr["bcr_p90"] = (rs[int(q * (len(rs) - 1))] for q in (0.1, 0.5, 0.9))
        pr["bcr_stress"] = ratio_at(pr, STRESS["cost"], STRESS["riders"])


def asc_sensitivity(projects, log=print):
    """{hsr id: (ratio at the low end of the constant's range, at the high end)}, each corridor valued
    from the same year as in the plan (texas/intercity.json hsr.asc_range, study/calibrate_hsr.md)."""
    lo, hi = ic.load_params()["hsr"].get("asc_range", [None, None])
    by = {p["id"]: p for p in projects}
    out = {}
    for end in (lo, hi):
        if end is None:
            continue
        log(f"  high-speed rail at constant {end:+.2f} ...")
        for q in hsr_projects(log=None, asc=end):
            q["value_year"] = by[q["id"]].get("value_year")
            q["traj"] = by[q["id"]].get("traj")   # the central run's travel trajectory
            out.setdefault(q["id"], []).append(ratio(q))
    return out


def whole_map_projects(base_projects, log=print):
    """The project list for the whole-map scenario: urban and conventional as in the plan, high-speed
    rail re-estimated under WHOLE_MAP_HSR (costs, standards and their speeds), each high-speed line with
    its federal match and its partner state's share of out-of-state track (texas/finance.py)."""
    saved = dict(hsr.SETTINGS)
    try:
        hsr.SETTINGS.update(WHOLE_MAP_HSR)
        log("  high-speed rail, the whole map's costs and standards ...")
        hs = with_trajectories(hsr_projects, log=None)
    finally:
        hsr.SETTINGS.clear()
        hsr.SETTINGS.update(saved)
    for q in hs:
        cid = q["id"].split(":")[1]
        q["outside"] = finance.paid_by_others(q["capital"], finance.corridor_shares(cid), federal_in=finance.FEDERAL_SHARE)
        q["standard"] = WHOLE_MAP_HSR["standards"].get(cid, "S1")
        q["connectivity"] = q["id"] in finance.CONNECTIVITY
        if q["connectivity"]:
            q["gate_years"] = GATE_YEARS
    rest = [copy.deepcopy(p) for p in base_projects if p["layer"] != "hsr"]
    return rest + hs


def program_stream(projects, pop, rounds=4):
    """{year: $M} for the Connectivity Program: the Rail Fund, plus the operating surplus of high-speed
    lines outside the program once open, less the program's own lines' operating deficits (their first
    claim), given the open years already set."""
    out = {}
    for y in YEARS:
        v = finance.rail_fund(y, pop)
        surplus = deficit = 0.0
        for p in projects:
            if p.get("open") and p["open"] <= y and p["layer"] == "hsr":
                margin = p["fares"] * growth_at(p, y) - p["opex"]
                if p.get("connectivity"):
                    deficit += max(-margin, 0.0)
                elif finance.TRIANGLE_SURPLUS:
                    surplus += margin
        out[y] = max(0.0, v + max(surplus, 0.0) - deficit)
    return out


def trunk_first(projects):
    """Best ratio first, but never a project before one it depends on (among `projects`)."""
    ids = {p["id"] for p in projects}
    left = sorted(projects, key=lambda p: -p["bcr"])
    done, out = set(), []
    while left:
        nxt = next((p for p in left if all(d in done or d not in ids for d in p["after"])), left[0])
        out.append(nxt)
        done.add(nxt["id"])
        left.remove(nxt)
    return out


def whole_map(projects, budget, pop):
    """The whole-map scenario's schedule: everything outside the Connectivity Program best ratio first on
    the statewide budget (as the plan); the program's corridors, in order of ratio, on the program's own
    stream (program_stream), recomputed as its lines open (their deficits are its first claim)."""
    for p in projects:
        ratio(p)
    main = [p for p in projects if not p.get("connectivity")]
    prog = [p for p in projects if p.get("connectivity")]
    for p in prog:
        p["start"] = p["open"] = None
    busy = {}
    built, spend = schedule(projects, budget, order=trunk_first(main), busy=busy)
    pbuilt, pspend = [], {y: 0.0 for y in YEARS}
    for _ in range(4):
        stream = program_stream(projects, pop)
        pbuilt, pspend = schedule(projects, stream, order=trunk_first(prog), busy=dict(busy))
    total = {y: spend[y] + pspend[y] for y in YEARS}
    return built + pbuilt, total


def main():
    pop = texas_pop()
    print("projects ...")
    projects = urban_projects() + with_trajectories(hsr_projects) + with_trajectories(conventional_projects)
    dfw, plan, dfw_tax_year = dfw_layer()
    budget = other_budget(dfw)
    runs = {}
    wm = whole_map_projects(projects)
    for key, _ in SCENARIOS:
        ps = copy.deepcopy(wm if key == "whole_map" else projects)
        fn = {"ratio": lambda q: schedule(q, budget), "metros_first": lambda q: metros_first(q, budget, pop),
              "whole_map": lambda q: whole_map(q, budget, pop)}[key]
        built, spend = settle(ps, fn)
        rows = yearly(ps, spend, pop, dfw)
        for r in rows:
            r["net"] = r["benefit"] + r["wider"] + r["fares"] - r["opex"]
            r["net_users"] = r["benefit"] + r["fares"] - r["opex"]
        runs[key] = {"projects": ps, "built": built, "rows": rows}
    print("optimizing the order ...")
    runs["optimized"] = optimize_order(projects, budget, pop, dfw)
    print("what it takes ...")
    runs["takes"] = what_it_takes(runs, budget, pop)
    print("levers ...")
    runs["levers"] = lever_grid(runs, budget, pop, dfw)
    risk(runs["ratio"]["projects"])
    risk(runs["whole_map"]["projects"])
    runs["asc"] = asc_sensitivity(runs["ratio"]["projects"])
    write(runs, pop, dfw, plan, budget, dfw_tax_year)


P90_COST = math.exp(1.2816 * 0.26)   # a P90 cost overrun at RISK_SIGMA["cost"]
OPT_ITERS, OPT_SEED = 4000, 7


def pv_net(projects, spend, pop, dfw):
    """Present value in 2025 at 3% of the yearly net benefits (travellers' gain, wider benefits, fares less
    operating cost) of everything open, 2025-2100: what a schedule buys with the same budget."""
    rows = yearly(projects, spend, pop, dfw)
    return sum((r["benefit"] + r["wider"] + r["fares"] - r["opex"]) / 1.03 ** (r["year"] - YEARS[0]) for r in rows)


def optimize_order(projects, budget, pop, dfw, iters=OPT_ITERS, seed=OPT_SEED, log=print):
    """Local search over the build order (study/hsr_buildout.md, Phase 2, the mathematician's scheduling
    task): start from best ratio first and try swapping two projects or moving one earlier, keeping a
    change when the present value of net benefits rises. The budget, the dependencies (a project whose
    trunk hasn't opened is skipped) and each project's values are the plan's. Returns (order, the
    greedy value, the optimized value)."""
    import random
    rnd = random.Random(seed)
    ps = copy.deepcopy(projects)
    for p in ps:
        ratio(p)
    by = {p["id"]: p for p in ps}

    def prio(p):
        r = p["bcr"]
        for d in p["after"]:
            if d in by:
                r = min(r, prio(by[d]))
        return r
    order = [p["id"] for p in sorted(ps, key=lambda p: -prio(p))]

    def value(o):
        _, spend = schedule(ps, budget, order=[by[i] for i in o])
        return pv_net(ps, spend, pop, dfw)
    best = base = value(order)
    n = len(order)
    for it in range(iters):
        o = list(order)
        i = rnd.randrange(n)
        j = max(0, min(n - 1, i + rnd.randint(-25, 25)))
        if i == j:
            continue
        if rnd.random() < 0.5:
            o[i], o[j] = o[j], o[i]
        else:
            o.insert(min(i, j), o.pop(max(i, j)))
        v = value(o)
        if v > best + 1e-6:
            best, order = v, o
    if log:
        log(f"  optimized order: PV net benefits {base / 1000:,.1f}B -> {best / 1000:,.1f}B")
    return order, base, best


def program_cost_ratio(case, learning):
    """{project id: its capital under `case` / `learning` over its capital under WHOLE_MAP_HSR}, for the
    program's corridors, each costed with the corridors it hangs off already built."""
    out = {}
    saved = dict(hsr.SETTINGS)
    try:
        for cid in (c.split(":")[1] for c in finance.CONNECTIVITY):
            deps = hsr.REQUIRES.get(cid, [])
            hsr.SETTINGS.clear()
            hsr.SETTINGS.update(WHOLE_MAP_HSR)
            base = hsr.capital_musd([cid], built=deps)
            hsr.SETTINGS.update({"case": case, "learning": learning})
            out[f"hsr:{cid}"] = hsr.capital_musd([cid], built=deps) / base
    finally:
        hsr.SETTINGS.clear()
        hsr.SETTINGS.update(saved)
    return out


def min_rail_fund(projects, budget, pop, mult=None, hi=12000.0):
    """The smallest Rail Fund ($M a year from its start year) that opens every Connectivity Program
    corridor by 2100 in the whole-map schedule, the program's capital times `mult` ({id: factor});
    None if even `hi` doesn't (a trunk the program needs isn't built from the statewide budget)."""
    saved = dict(finance.RAIL_FUND)

    def all_open(level):
        ps = copy.deepcopy(projects)
        for p in ps:
            if p.get("connectivity") and mult:
                p["capital"] *= mult.get(p["id"], 1.0)
                p["outside"] = p.get("outside", 0.0) * mult.get(p["id"], 1.0)
        finance.RAIL_FUND["musd_per_year"] = level
        whole_map(ps, budget, pop)
        return all(p.get("open") for p in ps if p.get("connectivity"))
    try:
        if not all_open(hi):
            return None
        lo, top = 0.0, hi
        for _ in range(14):
            mid = (lo + top) / 2
            if all_open(mid):
                top = mid
            else:
                lo = mid
        return top
    finally:
        finance.RAIL_FUND.clear()
        finance.RAIL_FUND.update(saved)


def what_it_takes(runs, budget, pop):
    """{case: smallest Rail Fund, $M a year} to open every branch by 2100."""
    ps = runs["whole_map"]["projects"]
    cases = [("central costs, with learning (the whole map)", None),
             ("central, a P90 overrun", {p: P90_COST for p in finance.CONNECTIVITY}),
             ("high costs, no learning (business as usual)", program_cost_ratio("high", False)),
             ("high, no learning, a P90 overrun", {k: v * P90_COST for k, v in program_cost_ratio("high", False).items()})]
    out = [(lab, min_rail_fund(ps, budget, pop, m)) for lab, m in cases]
    finance.TRIANGLE_SURPLUS = False   # if the other lines' operating surplus isn't pledged (or doesn't appear)
    try:
        for lab, m in (cases[0], cases[3]):
            out.append((lab + ", no surplus pledged", min_rail_fund(ps, budget, pop, m)))
    finally:
        finance.TRIANGLE_SURPLUS = True
    return out


def optimizer_section(runs, budget, pop, dfw):
    """Best ratio first against an optimized order: how much the greedy rule leaves on the table."""
    if not runs.get("optimized"):
        return []
    order, base, best = runs["optimized"]
    ps = copy.deepcopy(runs["ratio"]["projects"])
    by = {p["id"]: p for p in ps}
    greedy = {p["id"]: p.get("open") for p in runs["ratio"]["projects"]}
    schedule(ps, budget, order=[by[i] for i in order])
    moved = [((greedy[p["id"]] or 2101) - (p.get("open") or 2101), p) for p in ps
             if (greedy[p["id"]] or 2101) != (p.get("open") or 2101)]
    L = ["## Is best ratio first good enough?", "",
         f"A local search over the build order ({OPT_ITERS:,} tries, swapping projects or moving one earlier, keeping a "
         "change only if the present value of net benefits 2025-2100 rises; same budget, same values, trunks before "
         f"branches) raises that value from {money(base)} to {money(best)}, **{(best / base - 1):+.1%}**. Best ratio "
         "first ranks each project by its own ratio; the search also weighs when the money is free and how long each "
         "project takes to build. Biggest moves:", "",
         "| Project | Opens: best ratio first | Optimized |", "|---|---|---|"]
    for d, p in sorted(moved, key=lambda x: -abs(x[0]))[:12]:
        L.append(f"| {label(p)} | {greedy[p['id']] or 'not by 2100'} | {p.get('open') or 'not by 2100'} |")
    L += ["", ("The gain is small: best ratio first stays the plan's rule, and the search is a check on it." if best / base - 1 < 0.03
               else "The gain is large enough that the plan should consider scheduling by the optimized order."), ""]
    return L


LEVERS = (("costs", ("high", "central")), ("rail_fund", (0, 1)), ("surplus", (0, 1)), ("federal", (0, 1)), ("partners", (0, 1)))


def hsr_cost_ratio(case, learning):
    """{high-speed project id: its capital under `case`/`learning` over its capital under WHOLE_MAP_HSR},
    each corridor costed with the ones it hangs off built (as program_cost_ratio, for every corridor)."""
    out = {}
    saved = dict(hsr.SETTINGS)
    try:
        for cid in hsr.CORRIDORS:
            deps = hsr.REQUIRES.get(cid, [])
            hsr.SETTINGS.clear()
            hsr.SETTINGS.update(WHOLE_MAP_HSR)
            base = hsr.capital_musd([cid], built=deps)
            hsr.SETTINGS.update({"case": case, "learning": learning})
            out[f"hsr:{cid}"] = hsr.capital_musd([cid], built=deps) / base
    finally:
        hsr.SETTINGS.clear()
        hsr.SETTINGS.update(saved)
    return out


def lever_grid(runs, budget, pop, dfw):
    """The site's "what it takes" panel (Phase 4): the whole-map schedule for every combination of
    LEVERS (high-speed costs: business as usual or central with learning; the Rail Fund; the surplus
    pledge; the federal match; the partner states' share), each project valued from the year it opens
    in the whole map. With neither the Rail Fund nor the surplus there is no program, and the branches
    compete in the statewide queue as in best ratio first. {key "costs|rf|surplus|fed|partners":
    {opens: {id: year or None}, hsr_texas: $M, branches: n, intercity_2100, metro_2100}}."""
    import itertools
    base = runs["whole_map"]["projects"]
    high = hsr_cost_ratio("high", False)
    saved = (dict(finance.RAIL_FUND), finance.TRIANGLE_SURPLUS, finance.FEDERAL_SHARE, finance.PARTNER_SHARE)
    out = {}
    try:
        for combo in itertools.product(*(v for _, v in LEVERS)):
            costs, rf, sur, fed, par = combo
            ps = copy.deepcopy(base)
            finance.RAIL_FUND["musd_per_year"] = saved[0]["musd_per_year"] if rf else 0.0
            finance.TRIANGLE_SURPLUS = bool(sur)
            for p in ps:
                if p["layer"] not in ("hsr", "conventional"):
                    continue
                cid = p["id"].split(":")[1]
                if p["layer"] == "conventional":   # the neighbours' and Mexico's shares, as levers
                    p["outside"] = finance.paid_by_others(p["capital"], finance.conventional_shares(cid),
                                                          federal_out=finance.OUT_FEDERAL_SHARE if fed else 0.0,
                                                          partner=saved[3] if par else 0.0)
                    continue
                if costs == "high":
                    p["capital"] *= high.get(p["id"], 1.0)
                p["outside"] = finance.paid_by_others(p["capital"], finance.corridor_shares(cid),
                                                      federal_in=saved[2] if fed else 0.0,
                                                      federal_out=finance.OUT_FEDERAL_SHARE if fed else 0.0,
                                                      partner=saved[3] if par else 0.0)
                if not rf and not sur:
                    p["connectivity"] = False
            settle(ps, lambda q: whole_map(q, budget, pop))   # as the scenario: valued from the year each opens
            ps_open = [p for p in ps if p.get("open")]
            rows = yearly(ps, {y: 0.0 for y in YEARS}, pop, dfw)   # flows only: spending isn't reported here
            out["|".join(map(str, combo))] = {
                "opens": {p["id"]: p.get("open") for p in ps if p["layer"] == "hsr"},
                "hsr_texas": round(sum(p["capital"] - p.get("outside", 0.0) for p in ps_open if p["layer"] == "hsr")),
                "branches": sum(1 for p in ps if p["id"] in finance.CONNECTIVITY and p.get("open")),
                "branches_texas": round(sum(p["capital"] - p.get("outside", 0.0) for p in ps_open if p["id"] in finance.CONNECTIVITY)),
                "intercity_2100": round(rows[-1]["intercity_trips_year"]),
                "metro_2100": round(rows[-1]["urban_trips_day"] + rows[-1]["dfw_trips_day"])}
    finally:
        finance.RAIL_FUND.clear()
        finance.RAIL_FUND.update(saved[0])
        finance.TRIANGLE_SURPLUS, finance.FEDERAL_SHARE, finance.PARTNER_SHARE = saved[1], saved[2], saved[3]
    return out


def whole_map_section(runs, pop):
    """The whole map against best ratio first: the high-speed network and the Connectivity Program."""
    a, w = runs["ratio"], runs["whole_map"]
    aw = {p["id"]: p for p in a["projects"]}
    hs = [p for p in w["projects"] if p["layer"] == "hsr"]
    L = ["## Scenario: the whole map", "",
         "The cabinet's plan (`study/hsr_buildout.md`): high-speed rail at central unit costs with the learning curve a "
         "permanent delivery office would earn, the thin legs to lighter standards (Oklahoma City 250 km/h double track; "
         "Laredo, the Valley, McAllen and the Big Country trunk 250 km/h single track with passing loops; Lubbock - "
         "Amarillo and El Paso 200 km/h single track first), a federal match of "
         f"{finance.FEDERAL_SHARE:.0%} on the track in Texas. As in every scenario, the track in other states is theirs: "
         f"{finance.OUT_FEDERAL_SHARE:.0%} federal money granted to the state it runs in and {finance.PARTNER_SHARE:.0%} that "
         "state's own (Mexico pays for its side of the Monterrey line). The branches (the Connectivity Program) are built from their own ring-fenced money, never the statewide "
         f"budget: the Rail Fund (1/8 cent of sales tax from {finance.RAIL_FUND['start']}, about "
         f"${finance.RAIL_FUND['musd_per_year'] / 1000:.2f}B a year and growing with Texas), plus the operating surplus "
         "of the high-speed lines outside it, less the branches' own operating deficits. Everything else is as in best "
         "ratio first.", "",
         "| Corridor | Standard | Capital | Texas pays | Ratio | Opens (whole map) | Opens (best ratio first) | Trips a year, 2100 |",
         "|---|---|---|---|---|---|---|---|"]
    for p in sorted(hs, key=lambda p: (p.get("open") or 9999)):
        t2100 = p["trips_year"] * p["traj"].get(2100, 1.0) if p.get("traj") else p["trips_year"]
        flag = " (upgrade: past 3M a year)" if p.get("standard", "S1") in ("S3", "S4") and t2100 >= UPGRADE_TRIPS else ""
        L.append(f"| {label(p)}{' *' if p.get('connectivity') else ''} | {p.get('standard', 'S1')} | {money(p['capital'])} | "
                 f"{money(p['capital'] - p.get('outside', 0.0))} | {p['bcr']:.2f} | {p.get('open') or 'not by 2100'} | "
                 f"{aw.get(p['id'], {}).get('open') or 'not by 2100'} | {t2100 / 1e6:.1f}M{flag} |")
    prog = [p for p in hs if p.get("connectivity")]
    stream = program_stream(w["projects"], pop)
    fund = sum(finance.rail_fund(y, pop) for y in YEARS)
    built = [p for p in prog if p.get("open")]
    L += ["", "\\* the Connectivity Program.", "",
          f"**The program:** the Rail Fund raises {money(fund)} by 2100; with the other high-speed lines' surplus and less "
          f"the branches' deficits, {money(sum(stream.values()))} is available to it. It builds {len(built)} of {len(prog)} "
          f"branch corridors ({money(sum(p['capital'] - p.get('outside', 0.0) for p in built))} of Texas's money)"
          + (", every one by 2100." if len(built) == len(prog) else
             f"; not by 2100: {', '.join(label(p) for p in prog if not p.get('open'))}.")
          + " Ratios are well below 1 for most of them: the program is a choice to connect the state, not an investment.",
          ""]
    if runs.get("takes"):
        L += ["**What it takes to open every branch by 2100** (the smallest Rail Fund that does, everything else as above):", "",
              "| Cost case | Rail Fund needed a year | In sales tax |", "|---|---|---|"]
        cent = finance.RAIL_FUND["musd_per_year"] / 0.125   # $M a year per cent of sales tax
        for lab, v in runs["takes"]:
            L.append(f"| {lab} | {money(v) if v is not None else 'not reachable'} | "
                     + (f"{v / cent:.2f} cents" if v is not None else "a trunk it needs isn't built") + " |")
        L += ["", f"The central package proposes 1/8 cent ({money(finance.RAIL_FUND['musd_per_year'])} a year). With the other "
              "high-speed lines' operating surplus pledged, the branches need little new tax: the surplus (fares over "
              "operating cost on the Triangle and the Gulf) pays for most of them, so the Rail Fund is insurance against "
              "overruns and fares that don't cover costs. Without the surplus, the rows marked so are what the tax "
              "alone has to raise.", ""]
    L += [f"Statewide by 2100: {w['rows'][-1]['urban_trips_day'] + w['rows'][-1]['dfw_trips_day']:,.0f} new daily metro "
          f"trips and {w['rows'][-1]['intercity_trips_year'] / 1e6:.0f}M intercity rail trips a year, against "
          f"{a['rows'][-1]['intercity_trips_year'] / 1e6:.0f}M in best ratio first.", ""]
    return L


def scenario_section(runs):
    """Best ratio first against metros first: when things open and what it adds up to."""
    a, b = runs["ratio"], runs["metros_first"]
    L = ["## Scenario: metros first", "",
         f"Each of the 25 metros gets its own stream, its 30-year budget from step 4 (DFW's rate per resident) spread "
         f"over {METRO_YEARS} years from 2025, and builds its lines in the generator's order as that stream allows. "
         "Intercity rail takes what's left of the statewide budget after DFW, including whatever the metros can't spend, best "
         "ratio first. Values, costs, land-tax bonds and the budget are the same as above.", "",
         "| | Best ratio first | Metros first |", "|---|---|---|"]

    def at(run, y, k):
        return next(r[k] for r in run["rows"] if r["year"] == y)

    def built_cap(run, layer):
        return sum(p["capital"] for p in run["projects"] if p.get("open") and p["layer"] == layer)
    for y in (2040, 2050, 2075, 2100):
        L.append(f"| New daily urban transit trips, {y} | {at(a, y, 'urban_trips_day'):,.0f} | {at(b, y, 'urban_trips_day'):,.0f} |")
    for y in (2050, 2100):
        L.append(f"| Intercity rail trips a year, {y} | {at(a, y, 'intercity_trips_year') / 1e6:.1f}M | "
                 f"{at(b, y, 'intercity_trips_year') / 1e6:.1f}M |")
        L.append(f"| Fewer flights a day, {y} | {at(a, y, 'flights_day'):.0f} | {at(b, y, 'flights_day'):.0f} |")
    for layer, lab in (("urban", "Urban capital built by 2100"), ("hsr", "High-speed capital built by 2100"),
                       ("conventional", "Conventional capital built by 2100")):
        L.append(f"| {lab} | {money(built_cap(a, layer))} | {money(built_cap(b, layer))} |")
    for k, lab in (("benefit", "Travellers' gain, 2025-2100, present value at 3%"),
                   ("wider", "Wider benefits, present value at 3%"),
                   ("net_users", "Travellers' gain + fares - operating cost, present value"),
                   ("net", "All benefits + fares - operating cost, present value")):
        L.append(f"| {lab} | {money(pv(a['rows'], k))} | {money(pv(b['rows'], k))} |")
    L += ["", "When the intercity lines open:", "", "| Line | Best ratio first | Metros first |", "|---|---|---|"]
    bw = {p["id"]: p for p in b["projects"]}
    for p in sorted((p for p in a["projects"] if p["layer"] != "urban"), key=lambda p: (p["open"] or 9999)):
        q = bw[p["id"]]
        L.append(f"| {p['name']} | {p['open'] or 'not built'} | {q['open'] or 'not built'} |")
    L += ["", "When each metro's plan is complete:", "", "| Metro | Lines | Best ratio first | Metros first |", "|---|---|---|---|"]
    for mid in dict.fromkeys(p["metro"] for p in a["projects"] if p["layer"] == "urban"):
        pa = [p for p in a["projects"] if p.get("metro") == mid]
        pb = [p for p in b["projects"] if p.get("metro") == mid]

        def done(ps):
            return "not all built" if any(not p.get("open") for p in ps) else max(p["open"] for p in ps)
        L.append(f"| {pa[0]['metro_name']} | {len(pa)} | {done(pa)} | {done(pb)} |")
    ua, ub_ = pv(a["rows"], "net_users"), pv(b["rows"], "net_users")
    ga, gb = pv(a["rows"], "net"), pv(b["rows"], "net")

    def diff(x, y):
        return f"{money(y - x)} more" if y >= x else f"{money(x - y)} less"
    L += ["", "Metros first finishes the metro networks decades sooner and pushes the high-speed lines back. Counting "
          f"travellers' gain only, it returns {diff(ua, ub_)} in present value net of operating cost; counting the wider "
          f"benefits too, {diff(ga, gb)}. The urban lines' operating deficits start sooner as well.", ""]
    return L


def money(m):
    sign = "-" if m < 0 else ""
    return f"{sign}${abs(m) / 1000:.1f}B" if abs(m) >= 1000 else f"{sign}${abs(m):,.0f}M"


def label(p):
    if p["layer"] == "urban":
        return f"{p['metro_name']}: {p['name']} ({'regional rail' if p['mode'] == 'commuter' else p['mode']})"
    return p["name"]


def write(runs, pop, dfw, plan, budget, dfw_tax_year):
    projects, built, rows = runs["ratio"]["projects"], runs["ratio"]["built"], runs["ratio"]["rows"]
    avail = sum(budget.values())
    layers = (("urban", "Urban rail and BRT (25 metros)"), ("hsr", "High-speed rail"), ("conventional", "Conventional trains"))
    dfw_spent = sum(dfw[y]["spend"] for y in YEARS)
    L = ["# Timing: one statewide plan under one budget", "",
         "Generated by `python study/timing.py`. Every project from steps 3-5 and Dallas-Fort Worth's own plan, valued "
         f"the same way and scheduled under the statewide budget: ${STATE_MUSD / 1000:.1f}B a year of capital (DFW Transit's "
         "rate per resident), 2025-2100, in 2025 dollars.", "",
         f"**Dallas-Fort Worth** runs DFW Transit's 2 million riders plan on its own timetable (`data/dfw/dfw_plan.json`). It "
         f"spends {money(dfw_spent)} of its {money(DFW_MUSD * len(YEARS))}, and every year the rest of the state gets what DFW "
         f"doesn't spend, plus the land-tax bonds DFW's new stations raise: {money(avail)} in all for everything else.", "",
         "**Value.** Travellers' gain, from the same logit models that predict the riders (the logsum gain of every intercity "
         f"traveller on a pair; for the urban commute model one money coefficient's worth per new trip, ${1 / URBAN_B_PER_DOLLAR:.0f}), "
         "plus wider benefits (`texas/benefits.json`): congestion, crashes and emissions avoided for each car-km off the road "
         f"(${ext_per_vkm('urban'):.2f} a km in the metros, ${ext_per_vkm('intercity'):.2f} between them) and air passenger-km "
         f"(${BEN['air_externality_per_pkm']:.2f}), and agglomeration ({BEN['agglomeration_share']['urban']:.0%} of travellers' "
         f"gain for urban lines, {BEN['agglomeration_share']['hsr']:.0%} for high-speed rail). An urban trip is worth about "
         f"${1 / URBAN_B_PER_DOLLAR * (1 + BEN['agglomeration_share']['urban']) + URBAN_WIDER_PER_TRIP:.0f} in all. The **ratio** "
         "is benefit over cost across the 50 years from a project's opening at 3%, with travel growing as forecast (Texas's "
         "population for intercity lines, each metro's own 2026, 2050 and 2100 model runs for urban ones): all benefits (plus "
         "any operating surplus) over capital plus the operating deficit. Projects open best ratio first as the budget allows (spending spread over the construction years, carryover "
         "allowed, no borrowing beyond the land-tax bonds); the budget is spent whether or not a ratio reaches 1.", "",
         "**Land tax.** Each new urban line's new stations form a Tax Increment Reinvestment Zone and a Public Improvement "
         f"District ({LT['radius_km'] * 1000:.0f} m around them): the city and county tax on the rise in value the line brings, "
         f"plus a {LT['pid_rate']:.1%} assessment, pledged for {LT['years']} years and borrowed against when the line opens. The "
         "bonds pay part of the line's capital, so the statewide budget pays less; they don't change its ratio (the rise in "
         "land value is travellers' gain showing up in prices).", "",
         "## Statewide, by layer (best ratio first)", "",
         "| Layer | Projects | Built by 2100 | Capital built | Land-tax bonds | Travellers' gain a year | Wider benefits a year | "
         "Fares - operating cost a year | Ratio, users only | Ratio, all benefits | Ratio 1 or more (all benefits) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, lab in layers:
        ps = [p for p in projects if p["layer"] == key]
        bs = [p for p in ps if p.get("open")]
        cap = sum(p["capital"] for p in bs)
        ben = sum(p["benefit"] * p.get("uplift", 1.0) for p in bs)   # valued from each one's opening year
        wid = sum((p.get("wider", 0) + p.get("agglom", 0)) * p.get("uplift", 1.0) for p in bs)
        mg = sum(p["fares"] * p.get("uplift", 1.0) - p["opex"] for p in bs)
        cost = cap + max(-mg, 0) * PV_FACTOR
        r_u = (ben + max(mg, 0)) * PV_FACTOR / cost if cap else 0
        r_a = (ben + wid + max(mg, 0)) * PV_FACTOR / cost if cap else 0
        ok = [p for p in ps if p["bcr"] >= 1]
        L.append(f"| {lab} | {len(ps)} | {len(bs)} | {money(cap)} | {money(sum(p.get('bond', 0) for p in bs))} | {money(ben)} | "
                 f"{money(wid)} | {money(mg)} | {r_u:.2f} | {r_a:.2f} | {len(ok)} ({money(sum(p['capital'] for p in ok))}) |")
    y100 = dfw[YEARS[-1]]
    L.append(f"| Dallas-Fort Worth (its own plan) | {sum(1 for l in plan['lines'] if l['status'] != 'existing')} lines | "
             f"its timetable | {money(dfw_spent)} | {money(sum(dfw[y]['bond'] for y in YEARS))} | {money(y100['benefit'])} | "
             f"{money(y100['wider'])} | {money(y100['fares'] - y100['opex'])} | | | |")
    last = rows[-1]
    cap_all = sum(p["capital"] for p in built)
    draw = sum(p["capital"] - p.get("bond", 0) for p in built)
    L += ["", "Gains and costs a year in this table are a snapshot of each project at 2050 travel (with each metro's own "
          "growth and station-area land use; DFW's at 2100), a reporting convention like a dollar year. The ratios value "
          "each project over its own 50 years from opening, with its own travel growth (intercity projects modelled at "
          "2030, 2050, 2075 and 2100 travel). ", "",
          f"**By 2100, statewide:** outside DFW {money(cap_all)} built ({money(cap_all - draw)} of it paid by land-tax bonds) of "
          f"{money(avail)} available, {money(avail - draw)} unspent; {last['urban_trips_day'] + last['dfw_trips_day']:,.0f} new "
          f"daily metro transit trips ({last['dfw_trips_day']:,.0f} in DFW), {last['intercity_trips_year'] / 1e6:.0f}M intercity "
          f"rail trips a year, about {last['flights_day']:.0f} fewer flights a day, {money(last['benefit'])} a year of "
          f"travellers' gain and {money(last['wider'])} of wider benefits, and {money(last['opex'] - last['fares'])} a year "
          "more to operate than fares bring in.", ""]
    # how sure
    asc = runs.get("asc") or {}
    lo, hi = ic.load_params()["hsr"].get("asc_range", [None, None])
    inter = [p for p in projects if p["layer"] != "urban"]
    L += ["## How sure", "",
          f"Each ratio is the model's central estimate. **P10-P90** is the range over {RISK_DRAWS:,} draws of the project's "
          f"cost (lognormal around the estimate, spread {RISK_SIGMA['cost']:.2f}: rail cost overruns, Flyvbjerg 2003) and its "
          f"riders (spread {RISK_SIGMA['riders']:.2f}: ridership errors, Flyvbjerg 2005), centred on the model's own figures. "
          f"The **stress** column is the Auditor's gate: cost x{STRESS['cost']:.2f} and riders x{STRESS['riders']:.2f} at once "
          "(`study/hsr_buildout.md`, guardrail 3: a ratio of at least 0.8 there, or a connectivity designation)."
          + (f" High-speed rail is also shown at both ends of its calibrated constant ({lo:+.2f} and {hi:+.2f}, "
             "`study/calibrate_hsr.md`; central " f"{ic.load_params()['hsr']['asc_vs_car']:+.2f}): Brightline's low, and "
             "the Northeast Corridor's high." if lo is not None else ""), "",
          "| Intercity project | Opens | Ratio | P10 | P90 | Stress | At the constant's low | high |",
          "|---|---|---|---|---|---|---|---|"]
    for p in sorted(inter, key=lambda p: -p["bcr"]):
        a = asc.get(p["id"], [])
        L.append(f"| {label(p)} | {p.get('open') or 'not by 2100'} | {p['bcr']:.2f} | {p['bcr_p10']:.2f} | {p['bcr_p90']:.2f} | "
                 f"{p['bcr_stress']:.2f} | {a[0]:.2f} | {a[1]:.2f} |" if len(a) == 2 else
                 f"| {label(p)} | {p.get('open') or 'not by 2100'} | {p['bcr']:.2f} | {p['bcr_p10']:.2f} | {p['bcr_p90']:.2f} | "
                 f"{p['bcr_stress']:.2f} | | |")
    ub = [p for p in projects if p["layer"] == "urban" and p.get("open")]
    if ub:
        pass_stress = sum(1 for p in ub if p["bcr_stress"] >= 0.8)
        L += ["", f"Urban lines built: median ratio {sorted(p['bcr'] for p in ub)[len(ub) // 2]:.2f} (P10-P90 of the median line "
              f"{sorted(p['bcr_p10'] for p in ub)[len(ub) // 2]:.2f}-{sorted(p['bcr_p90'] for p in ub)[len(ub) // 2]:.2f}); "
              f"{pass_stress} of {len(ub)} clear 0.8 under the stress.", ""]
    # what wider benefits change
    flips = sorted((p for p in projects if p["bcr"] >= 1 > p["bcr_users"]), key=lambda p: -p["bcr"])
    L += ["## What the wider benefits change", "",
          f"With travellers' gain alone, {sum(1 for p in projects if p['bcr_users'] >= 1)} projects reach a ratio of 1; with "
          f"the wider benefits, {sum(1 for p in projects if p['bcr'] >= 1)} do. A new urban trip is worth "
          f"${1 / URBAN_B_PER_DOLLAR:.0f} to its rider and about ${URBAN_WIDER_PER_TRIP + 1 / URBAN_B_PER_DOLLAR * BEN['agglomeration_share']['urban']:.0f} "
          "more to everyone else (less congestion, fewer crashes, less pollution, denser labour markets): wider benefits "
          "lift the urban lines most, because each urban rider takes a car off congested streets.", ""]
    if flips:
        L += ["| Now reaches 1 | Layer | Capital | Ratio, users only | Ratio, all benefits |", "|---|---|---|---|---|"]
        for p in flips[:25]:
            L.append(f"| {label(p)} | {p['layer']} | {money(p['capital'])} | {p['bcr_users']:.2f} | {p['bcr']:.2f} |")
        L.append("")
    # land tax
    ub = [p for p in projects if p["layer"] == "urban"]
    L += ["## Land tax near new urban stations", "",
          f"{sum(p['new_stations'] for p in ub)} new stations in the 25 metros reach {sum(p['district_pop'] for p in ub) / 1e6:.2f}M "
          f"residents and {sum(p['district_jobs'] for p in ub) / 1e6:.2f}M jobs within {LT['radius_km'] * 1000:.0f} m. Their "
          f"districts raise {money(sum(p['land_tax_year'] for p in ub))} a year, worth {money(sum(p['bond'] for p in ub))} "
          f"in bonds, {sum(p['bond'] for p in ub) / sum(p['capital'] for p in ub):.0%} of the lines' capital. DFW's new stations "
          f"raise {money(dfw_tax_year)} a year, {money(sum(dfw[y]['bond'] for y in YEARS))} in bonds, which go to the statewide "
          "pot because DFW's timetable is its own.", "",
          "| Metro | Lines | New stations | People + jobs near them | Land tax a year | Bonds | Share of capital |", "|---|---|---|---|---|---|---|"]
    for mid in dict.fromkeys(p["metro"] for p in ub):
        ps = [p for p in ub if p["metro"] == mid]
        cap = sum(p["capital"] for p in ps)
        L.append(f"| {ps[0]['metro_name']} | {len(ps)} | {sum(p['new_stations'] for p in ps)} | "
                 f"{sum(p['district_pop'] + p['district_jobs'] for p in ps):,.0f} | {money(sum(p['land_tax_year'] for p in ps))} | "
                 f"{money(sum(p['bond'] for p in ps))} | {sum(p['bond'] for p in ps) / cap:.0%} |")
    # connections
    first = {}
    for p in projects:
        for st in p.get("chain", []):
            if p.get("open"):
                first[(p["layer"], st)] = min(first.get((p["layer"], st), 9999), p["open"])
    key = {"Dallas (high-speed, beside Union Station)": ("hsr", "Dallas"), "Fort Worth (high-speed)": ("hsr", "Fort Worth"),
           "Denton (high-speed, to Oklahoma City)": ("hsr", "Denton"),
           "Dallas Union Station (conventional, I-20)": ("conventional", "Dallas"),
           "Fort Worth Central (conventional, Heartland Flyer)": ("conventional", "Fort Worth")}
    L += ["", "## Where the statewide lines meet DFW's", "",
          "| Statewide station | First statewide line opens | DFW's nearest station open by then | Distance | DFW station opens | DFW modes there |",
          "|---|---|---|---|---|---|"]
    opens = {n: first.get(k) for n, k in key.items()}
    global CONN
    CONN = connections(plan, opens)
    for c in connections(plan, opens):
        f = first.get(key[c["name"]])
        L.append(f"| {c['name']} | {f or 'not built'} | {c['dfw']} | {c['km'] * 1000:,.0f} m | {c['year']} | {c['modes']} |")
    far = [c["name"] for c in CONN if c["km"] > 0.4]
    L += ["", "Within about 400 m is a walk between platforms: " + (
        "all five are, with DFW's station open before the statewide line arrives (the Dallas high-speed station was moved "
        "from Texas Central's Cedars site, 830 m from both the Cedars and Union Station, to beside Union Station, and "
        "Denton's onto its transit center)." if not far else "farther: " + ", ".join(far) + " need a link of their own."), ""]
    L += ["## When things open (best ratio first)", "", "| Year | Opening | Layer | Capital | Land-tax bonds | Ratio |", "|---|---|---|---|---|---|"]
    for p in sorted(built, key=lambda p: (p["open"], -p["bcr"])):
        L.append(f"| {p['open']} | {label(p)} | {p['layer']} | {money(p['capital'])} | "
                 f"{money(p.get('bond', 0)) if p.get('bond') else ''} | {p['bcr']:.2f} |")
    L += ["", "## Every decade (best ratio first, statewide with DFW)", "",
          "| Year | Capital spent to date (outside DFW) | DFW spent to date | New metro trips a day (DFW) | Intercity rail trips a year | "
          "Fewer flights a day | Travellers' gain a year | Wider benefits a year | Operating cost - fares a year |",
          "|---|---|---|---|---|---|---|---|---|"]
    cum = cum_d = 0.0
    for r in rows:
        cum += r["spend"]
        cum_d += r["dfw_spend"]
        if r["year"] % 10 == 0 or r["year"] in (2025, 2100):
            L.append(f"| {r['year']} | {money(cum)} | {money(cum_d)} | {r['urban_trips_day'] + r['dfw_trips_day']:,.0f} "
                     f"({r['dfw_trips_day']:,.0f}) | {r['intercity_trips_year'] / 1e6:.1f}M | {r['flights_day']:.0f} | "
                     f"{money(r['benefit'])} | {money(r['wider'])} | {money(r['opex'] - r['fares'])} |")
    nb = sorted((p for p in projects if not p.get("open")), key=lambda p: -p["bcr"])
    L += ["", "## Not built (best ratio first)", "", "| Project | Layer | Capital | Ratio | Why |", "|---|---|---|---|---|"]
    for p in nb:
        why = "waits on a project not built" if any(
            not next(q for q in projects if q["id"] == d).get("open") for d in p["after"]) else "no budget left by 2100"
        L.append(f"| {label(p)} | {p['layer']} | {money(p['capital'])} | {p['bcr']:.2f} | {why} |")
    L += ["", "## Caveats", "",
          "- Wider benefits are per-km and per-trip allowances from the ranges in US and UK practice (`texas/benefits.json`), "
          "not modelled here: no traffic model says where the cars come off the road, and agglomeration is a share of "
          "travellers' gain. Halve them and most urban lines fall back under 1.",
          "- The urban figure for travellers' gain is an approximation (exact only as transit's share goes to zero) and counts "
          "non-commute trips at the commute value; the intercity figure leaves out induced trips' own gain. Both include each "
          "mode's constant, so the ratios are only as good as those constants (high-speed rail's moves its first four "
          "corridors between 30M and 74M trips a year).",
          "- Land-tax revenue assumes the uplift arrives with the line and the districts are formed: Texas cities form TIRZs "
          "and PIDs one at a time, and school taxes, the biggest share, can't be captured. Values are 2020 people and jobs "
          "at today's prices, with no growth near the stations (conservative).",
          "- Intercity values grow with Texas's population trend from 2050. Urban values follow each metro's model runs in "
          "2026, 2050 and 2100 (study/urban_metros.md), which open every line from 2026: a line opened late is credited "
          "with station areas that have had decades to develop, so late lines' riders are on the high side. DFW's "
          "numbers are its own model's, on its own growth path.",
          "- An urban line's riders are its share of its metro's total, by the full model's value of it (the mean of what "
          "the network loses without it and what it adds alone). Lines that work as a network share the credit, so fewer "
          "of them reach a ratio of 1 on their own than when the sketch's single-line trips split the total.",
          "- Operating cost is outside the capital budget, as in DFW Transit; the deficits are in the ratio, but no budget pays "
          "them yet.", ""]
    L += optimizer_section(runs, budget, pop, dfw)
    L += scenario_section(runs)
    L += whole_map_section(runs, pop)
    with open(os.path.join(ROOT, "study", "timing.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    os.makedirs(os.path.join(ROOT, "docs", "data"), exist_ok=True)
    keep = ("id", "layer", "metro", "metro_name", "name", "mode", "km", "capital", "opex", "fares", "benefit", "wider", "agglom",
            "bond", "land_tax_year", "trips_day", "trips_year", "air_day", "flights_day", "bcr", "bcr_users", "start", "open",
            "bcr_p10", "bcr_p90", "bcr_stress", "uplift",
            "chain", "after")

    def rnd(d, n):
        return {k: (round(v, n) if isinstance(v, float) else v) for k, v in d.items()}
    data = {"budget_musd": STATE_MUSD, "dfw_musd": DFW_MUSD, "other_musd": avail / len(YEARS), "other_total": avail,
            "years": [YEARS[0], YEARS[-1]], "metro_years": METRO_YEARS,
            "dfw": {"spent": dfw_spent, "bonds": sum(dfw[y]["bond"] for y in YEARS), "connections": CONN,
                    "lines": sum(1 for ln in plan["lines"] if ln["status"] != "existing"), "benefit": y100["benefit"],
                    "wider": y100["wider"], "margin": y100["fares"] - y100["opex"]},
            "projects": [rnd({k: v for k, v in p.items() if k in keep}, 3) for p in projects],
            # each metro's riders relative to their 2050 level (urban_trajectory), every 5 years: trips_day x this
            "urban_traj": {p["metro"]: {str(y): round(p["traj"][y], 3) for y in range(2030, 2101, 5)} | {"2026": round(p["traj"][2026], 3)}
                           for p in projects if p["layer"] == "urban" and p.get("traj")},
            "yearly": [rnd(r, 1) for r in rows],
            "levers": runs.get("levers"),
            "lever_names": [k for k, _ in LEVERS],
            "connectivity": finance.CONNECTIVITY,
            "whole_map_projects": [rnd({k: v for k, v in p.items() if k in keep + ("standard", "outside", "connectivity")}, 3)
                                   for p in runs["whole_map"]["projects"] if p["layer"] == "hsr"],
            "scenarios": {key: {"label": lab,
                                "when": {p["id"]: [p["start"], p["open"]] for p in runs[key]["projects"] if p.get("open")},
                                "yearly": [rnd(r, 1) for r in runs[key]["rows"]]}
                          for key, lab in SCENARIOS}}
    with open(os.path.join(ROOT, "docs", "data", "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print("\n".join(L[:60]))


if __name__ == "__main__":
    main()
