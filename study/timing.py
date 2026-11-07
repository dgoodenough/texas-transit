"""Timing: every project, urban and intercity, under the one statewide budget, 2025-2100.

    python study/timing.py

Writes study/timing.md and docs/data/timeline.json (the site's data).

1. Projects.
   - Urban: each line the generator chose in the 25 metros (urban/generated/<id>/candidates.csv),
     its daily trips the model's metro total (study/urban_metros.md) shared out by the line's own
     sketch trips. Within a metro, lines open in the generator's order.
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
   deficit. Ratios are on 2050 travel. Intercity values grow with Texas's population from 2050
   (tools/build_growth.py); urban ones follow each metro's own model runs in 2026, 2050 and 2100
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
from texas import conventional as cv, hsr, intercity as ic  # noqa: E402
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
SCENARIOS = (("ratio", "Best ratio first"), ("metros_first", "Metros first"))


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
    d = os.path.join(ROOT, "urban", "generated", metro_id)
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
        d = os.path.join(ROOT, "urban", "generated", m["id"])
        s = json.load(open(os.path.join(d, "summary.json"), encoding="utf-8"))
        cpath = os.path.join(d, "candidates.csv")
        if not os.path.exists(cpath):   # no corridor dense enough for a candidate (study/urban_metros.md)
            continue
        rows = [r for r in csv.DictReader(open(cpath, encoding="utf-8")) if r["status"] == "chosen"]
        rows.sort(key=lambda r: int(r["order"]))
        sketch = sum(float(r["new_trips"]) for r in rows)
        model, traj, base_year = urban_trajectory(s)
        # the feeder buses the network adds (study/urban_metros.py), in the base year, shared out like the riders
        feeder = ((s.get("future") or {}).get(str(base_year)) or s).get("feeder_opex_musd", 0.0)
        dist = districts(m["id"], [r["cand_id"] for r in rows])
        prev = None
        for r in rows:
            trips = model * float(r["new_trips"]) / sketch if sketch else 0.0
            dp, dj, dn = dist.get(r["cand_id"], (0.0, 0.0, 0))
            tax_year, bond = land_tax(dp, dj, r["mode"])
            benefit = trips / URBAN_B_PER_DOLLAR * URBAN_DAYS / 1e6
            fares = trips * URBAN_FARE * URBAN_DAYS / 1e6
            pid = f"{m['id']}:{r['cand_id']}"
            out.append({"id": pid, "layer": "urban", "metro": m["id"], "metro_name": m["name"].split(",")[0],
                        "name": r["name"], "mode": r["mode"], "km": float(r["km"]),
                        "capital": float(r["capital_musd"]),
                        "opex": float(r["opex_musd_yr"]) + max(feeder, 0.0) * (float(r["new_trips"]) / sketch if sketch else 0.0),
                        "fares": fares,
                        "benefit": benefit, "trips_day": trips, "trips_year": trips * URBAN_DAYS,
                        "wider": trips * URBAN_WIDER_PER_TRIP * URBAN_DAYS / 1e6,
                        "agglom": benefit * BEN["agglomeration_share"]["urban"],
                        "district_pop": dp, "district_jobs": dj, "new_stations": dn,
                        "land_tax_year": tax_year, "bond": min(bond, float(r["capital_musd"])),
                        "base_year": base_year, "traj": traj, "after": [prev] if prev else [], "build": BUILD_YEARS[r["mode"]]})
            prev = pid
    return out


def hsr_projects(log=print):
    order = []
    names = {v[0]: k for k, v in hsr.CORRIDORS.items()}
    with open(os.path.join(ROOT, "study", "hsr_options.md"), encoding="utf-8") as f:
        for line in f:
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(c) == 9 and c[0].isdigit() and c[1] in names:
                order.append(names[c[1]])
    p = ic.load_params()
    zones = ic.load_zones()
    base = ic.base_trips(zones, p)
    tx = {k: v for k, v in base.items() if "TX" in (zones[k[0]]["state"], zones[k[1]]["state"])}
    growth = ic.zone_growth(zones, HSR_YEAR)
    prev = {"rail": 0.0, "benefit": 0.0, "fares": 0.0, "air": 0.0, "flights": 0.0, "vkm": 0.0, "pkm": 0.0}
    out = []
    for i, cid in enumerate(order):
        built = order[:i + 1]
        net = ic.RailNetwork({s: hsr.point(s) for s in hsr.stations_of(built)}, hsr.network_links(built), p["hsr"])
        res = ic.run(tx, zones, p, net, growth)
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
        out.append({"id": f"hsr:{cid}", "layer": "hsr", "name": hsr.CORRIDORS[cid][0], "mode": "hsr",
                    "km": hsr.track_km([cid]), "capital": hsr.capital_musd([cid], built=order[:i]),
                    "opex": hsr.opex_musd([cid], HSR_HEADWAY, built=order[:i]),
                    "fares": d["fares"] * 365 / 1e6, "benefit": d["benefit"] * 365 / 1e6,
                    "trips_day": d["rail"], "trips_year": d["rail"] * 365, "air_day": d["air"], "flights_day": d["flights"],
                    "wider": intercity_wider(d["vkm"], d["pkm"]),
                    "agglom": d["benefit"] * 365 / 1e6 * BEN["agglomeration_share"]["hsr"],
                    "base_year": HSR_YEAR, "after": [f"hsr:{order[i - 1]}"] if i else [], "build": BUILD_YEARS["hsr"],
                    "chain": hsr.CORRIDORS[cid][1]})
        if log:
            log(f"  hsr {cid}: +{d['rail'] * 365 / 1e6:.2f}M trips, ${d['benefit'] * 365 / 1e6:,.0f}M benefit a year")
    return out


def conventional_projects(log=print):
    p = ic.load_params()
    zones = ic.load_zones()
    base = ic.base_trips(zones, p)
    tx = {k: v for k, v in base.items() if "TX" in (zones[k[0]]["state"], zones[k[1]]["state"])}
    trips, _, _ = ir.add_monterrey(tx, zones, p, ir.BORDER_FACTOR)
    growth = ic.zone_growth({k: v for k, v in zones.items() if k != "MTY"}, HSR_YEAR)
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
        out.append({"id": f"conv:{cid}", "layer": "conventional", "name": cv.CORRIDORS[cid][0], "mode": "conventional",
                    "km": cv.route_km(cid), "capital": cv.capital_musd(cid, 4, p["conventional"]), "opex": opex,
                    "fares": fares * 365 / 1e6, "benefit": ben * 365 / 1e6, "trips_day": rail, "trips_year": rail * 365,
                    "air_day": air, "wider": intercity_wider(vkm, pkm),
                    "agglom": ben * 365 / 1e6 * BEN["agglomeration_share"]["conventional"],
                    "base_year": HSR_YEAR, "after": dep, "build": BUILD_YEARS["conventional"],
                    "chain": cv.CORRIDORS[cid][1]})
        if log:
            log(f"  conventional {cid}: +{rail * 365 / 1e6:.2f}M trips, ${ben * 365 / 1e6:,.0f}M benefit a year")
    return out


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
def ratio(pr):
    """Benefit-cost ratio over 50 years at 3%: all benefits (travellers' gain, wider benefits,
    agglomeration, plus any operating surplus) over capital plus the operating deficit (operating cost
    minus fares). Land-tax bonds change who pays, not the ratio."""
    margin = pr["fares"] - pr["opex"]
    pr["all_benefit"] = pr["benefit"] + pr.get("wider", 0.0) + pr.get("agglom", 0.0)
    pr["net"] = pr["all_benefit"] + margin
    pv_benefit = (pr["all_benefit"] + max(margin, 0.0)) * PV_FACTOR
    pv_cost = pr["capital"] + max(-margin, 0.0) * PV_FACTOR
    pr["bcr"] = pv_benefit / pv_cost if pv_cost > 0 else 0.0
    pr["bcr_users"] = (pr["benefit"] + max(margin, 0.0)) * PV_FACTOR / pv_cost if pv_cost > 0 else 0.0
    return pr["bcr"]


def schedule(projects, budget, spend=None, order=None):
    """Schedule `projects` (sets each one's start and open years; None if it doesn't fit by 2100).
    `budget`: $M a year, a number or {year: $M}; `spend`: {year: $M} already committed (counted
    against the same budget). Each project starts in the first year its spending fits: cumulative
    spending never exceeds cumulative budget (carryover, no borrowing), no earlier than what it depends
    on starts, and it opens no earlier than that opens. Order: best ratio first (a dependent's priority
    capped at its parent's), or the given list `order`."""
    by = {p["id"]: p for p in projects}
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
        per = (p["capital"] - p.get("bond", 0.0)) / p["build"]   # land-tax bonds pay part of an urban line
        for y in range(first, YEARS[-1] - p["build"] + 1):   # opens by the last year
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
                built.append(p)
                break
    return built, spend


def metros_first(projects, budget):
    """Scenario: each metro gets its own stream, its 30-year generator budget (urban/metros.json
    budget_musd) spread evenly over METRO_YEARS from 2025, and builds its lines in the generator's
    order as that stream allows. Intercity projects take what's left of the $6.7B a year (including
    whatever the metros don't spend), best ratio first."""
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))
    spend = {y: 0.0 for y in YEARS}
    built = []
    for m in reg["metros"]:
        ps = [p for p in projects if p.get("metro") == m["id"]]
        if not ps:
            continue
        n = len(YEARS) if m.get("buildout") or m.get("policies") else METRO_YEARS   # 75-year budgets cover DFW's whole horizon
        stream = {y: (m["budget_musd"] / n if y < YEARS[0] + n else 0.0) for y in YEARS}
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


def main():
    pop = texas_pop()
    print("projects ...")
    projects = urban_projects() + hsr_projects() + conventional_projects()
    dfw, plan, dfw_tax_year = dfw_layer()
    budget = other_budget(dfw)
    runs = {}
    for key, _ in SCENARIOS:
        ps = copy.deepcopy(projects)
        built, spend = schedule(ps, budget) if key == "ratio" else metros_first(ps, budget)
        rows = yearly(ps, spend, pop, dfw)
        for r in rows:
            r["net"] = r["benefit"] + r["wider"] + r["fares"] - r["opex"]
            r["net_users"] = r["benefit"] + r["fares"] - r["opex"]
        runs[key] = {"projects": ps, "built": built, "rows": rows}
    write(runs, pop, dfw, plan, budget, dfw_tax_year)


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
         "is benefit over cost across 50 years at 3%: all benefits (plus any operating surplus) over capital plus the operating "
         "deficit. Projects open best ratio first as the budget allows (spending spread over the construction years, carryover "
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
        ben = sum(p["benefit"] for p in bs)
        wid = sum(p.get("wider", 0) + p.get("agglom", 0) for p in bs)
        mg = sum(p["fares"] - p["opex"] for p in bs)
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
    L += ["", "Gains and costs a year are at full build (2050 travel, with each metro's own growth and station-area land use "
          "for the metros; DFW's at 2100). ", "",
          f"**By 2100, statewide:** outside DFW {money(cap_all)} built ({money(cap_all - draw)} of it paid by land-tax bonds) of "
          f"{money(avail)} available, {money(avail - draw)} unspent; {last['urban_trips_day'] + last['dfw_trips_day']:,.0f} new "
          f"daily metro transit trips ({last['dfw_trips_day']:,.0f} in DFW), {last['intercity_trips_year'] / 1e6:.0f}M intercity "
          f"rail trips a year, about {last['flights_day']:.0f} fewer flights a day, {money(last['benefit'])} a year of "
          f"travellers' gain and {money(last['wider'])} of wider benefits, and {money(last['opex'] - last['fares'])} a year "
          "more to operate than fares bring in.", ""]
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
          "- Operating cost is outside the capital budget, as in DFW Transit; the deficits are in the ratio, but no budget pays "
          "them yet.", ""]
    L += scenario_section(runs)
    with open(os.path.join(ROOT, "study", "timing.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    os.makedirs(os.path.join(ROOT, "docs", "data"), exist_ok=True)
    keep = ("id", "layer", "metro", "metro_name", "name", "mode", "km", "capital", "opex", "fares", "benefit", "wider", "agglom",
            "bond", "land_tax_year", "trips_day", "trips_year", "air_day", "flights_day", "bcr", "bcr_users", "start", "open",
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
            "scenarios": {key: {"label": lab,
                                "when": {p["id"]: [p["start"], p["open"]] for p in runs[key]["projects"] if p.get("open")},
                                "yearly": [rnd(r, 1) for r in runs[key]["rows"]]}
                          for key, lab in SCENARIOS}}
    with open(os.path.join(ROOT, "docs", "data", "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print("\n".join(L[:60]))


if __name__ == "__main__":
    main()
