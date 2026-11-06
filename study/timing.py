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
   Fares and operating cost (urban fares URBAN_FARE a trip). Benefit-cost ratio over 50 years at
   3% (PV_FACTOR): travellers' gain (plus any operating surplus) over capital plus the operating
   deficit. Values grow with Texas's population (tools/build_growth.py): intercity from 2050,
   urban from 2026.
3. Schedule. Dallas-Fort Worth keeps DFW Transit's $2.3B a year (its own plan and timetable); the rest
   of the $9.0B a year goes to the other projects, best ratio first (a project opens no earlier than the
   ones its value depends on), each spending evenly over its construction years and opening at the end, with
   carryover and no borrowing: spending to date never exceeds budget to date. The budget is spent
   whether or not a project's ratio reaches 1 (the plan spends DFW's rate); the ratios say which
   projects pay for themselves in travellers' gains alone.
"""
import csv
import json
import math
import os
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
HSR_HEADWAY = 30


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


# ---------------------------------------------------------------- projects
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
        model = max(s.get("trips", 0) - s.get("trips_today", 0), 0)
        prev = None
        for r in rows:
            trips = model * float(r["new_trips"]) / sketch if sketch else 0.0
            benefit = trips / URBAN_B_PER_DOLLAR * URBAN_DAYS / 1e6
            fares = trips * URBAN_FARE * URBAN_DAYS / 1e6
            pid = f"{m['id']}:{r['cand_id']}"
            out.append({"id": pid, "layer": "urban", "metro": m["id"], "metro_name": m["name"].split(",")[0],
                        "name": r["name"], "mode": r["mode"], "km": float(r["km"]),
                        "capital": float(r["capital_musd"]), "opex": float(r["opex_musd_yr"]), "fares": fares,
                        "benefit": benefit, "trips_day": trips, "trips_year": trips * URBAN_DAYS,
                        "base_year": 2026, "after": [prev] if prev else [], "build": BUILD_YEARS[r["mode"]]})
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
    prev = {"rail": 0.0, "benefit": 0.0, "fares": 0.0, "air": 0.0, "flights": 0.0}
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
            return 0.0, 0.0, 0.0, 0.0
        rail, fares, air, res = ir.evaluate(ids, tpd, trips, zones, p, growth)
        return rail, fares, air, sum(r["benefit_usd"] for r in res.values())

    for cid, under, against in ir.PLAN:
        today = cv.CORRIDORS[cid][2]
        after = totals(under + [cid], 4)
        before = totals(under, 4) if against == "under" else (totals(under + [cid], today) if against == "today" else (0, 0, 0, 0))
        rail, fares, air, ben = (after[i] - before[i] for i in range(4))
        opex = cv.opex_musd(cid, 4) - (cv.opex_musd(cid, today) if against == "today" else 0.0)
        dep = {"KC": ["conv:FLYER"], "EAGLE": ["conv:I20"]}.get(cid, [])
        out.append({"id": f"conv:{cid}", "layer": "conventional", "name": cv.CORRIDORS[cid][0], "mode": "conventional",
                    "km": cv.route_km(cid), "capital": cv.capital_musd(cid, 4, p["conventional"]), "opex": opex,
                    "fares": fares * 365 / 1e6, "benefit": ben * 365 / 1e6, "trips_day": rail, "trips_year": rail * 365,
                    "air_day": air, "base_year": HSR_YEAR, "after": dep, "build": BUILD_YEARS["conventional"],
                    "chain": cv.CORRIDORS[cid][1]})
        if log:
            log(f"  conventional {cid}: +{rail * 365 / 1e6:.2f}M trips, ${ben * 365 / 1e6:,.0f}M benefit a year")
    return out


# ---------------------------------------------------------------- schedule
def ratio(pr):
    """Benefit-cost ratio over 50 years at 3%: travellers' gain (plus any operating surplus) over
    capital plus the operating deficit (operating cost minus fares)."""
    margin = pr["fares"] - pr["opex"]
    pr["net"] = pr["benefit"] + margin
    pv_benefit = (pr["benefit"] + max(margin, 0.0)) * PV_FACTOR
    pv_cost = pr["capital"] + max(-margin, 0.0) * PV_FACTOR
    pr["bcr"] = pv_benefit / pv_cost if pv_cost > 0 else 0.0
    return pr["bcr"]


def schedule(projects, budget_per_year):
    """Best ratio first; each starts in the first year its spending fits under cumulative budget, no
    earlier than what it depends on starts, and opens no earlier than that opens (a dependent's
    priority is capped at its parent's)."""
    by = {p["id"]: p for p in projects}
    for p in projects:
        ratio(p)

    def prio(p):
        r = p["bcr"]
        for d in p["after"]:
            r = min(r, prio(by[d]))
        return r
    for p in projects:
        p["priority"] = prio(p)
    spend = {y: 0.0 for y in YEARS}
    built = []
    for p in sorted(projects, key=lambda p: -p["priority"]):
        p["start"] = p["open"] = None
        if any(by[d]["open"] is None for d in p["after"]):
            continue
        # a project's value assumes the ones before it are there: it may be built alongside them, but
        # opens no earlier than they do
        first = max([YEARS[0]] + [max(by[d]["start"], by[d]["open"] - p["build"]) for d in p["after"]])
        per = p["capital"] / p["build"]
        for y in range(first, YEARS[-1] - p["build"] + 2):
            trial = dict(spend)
            for k in range(p["build"]):
                trial[y + k] += per
            cum_b = cum_s = 0.0
            ok = True
            for yy in YEARS:
                cum_b += budget_per_year
                cum_s += trial[yy]
                if cum_s > cum_b + 1e-6:
                    ok = False
                    break
            if ok:
                spend = trial
                p["start"], p["open"] = y, y + p["build"]
                built.append(p)
                break
    return built, spend


def yearly(projects, spend, pop):
    rows = []
    for y in YEARS:
        open_ = [p for p in projects if p.get("open") and p["open"] <= y]
        f = {p["id"]: pop[y] / pop[p["base_year"]] for p in open_}
        rows.append({"year": y, "spend": spend[y],
                     "urban_trips_day": sum(p["trips_day"] * f[p["id"]] for p in open_ if p["layer"] == "urban"),
                     "intercity_trips_year": sum(p["trips_year"] * f[p["id"]] for p in open_ if p["layer"] != "urban"),
                     "benefit": sum(p["benefit"] * f[p["id"]] for p in open_),
                     "flights_day": sum(p.get("flights_day", 0) * f[p["id"]] for p in open_),
                     "opex": sum(p["opex"] for p in open_), "fares": sum(p["fares"] * f[p["id"]] for p in open_)})
    return rows


def main():
    pop = texas_pop()
    print("projects ...")
    projects = urban_projects() + hsr_projects() + conventional_projects()
    built, spend = schedule(projects, OTHER_MUSD)
    rows = yearly(projects, spend, pop)
    write(projects, built, rows, pop)


def money(m):
    sign = "-" if m < 0 else ""
    return f"{sign}${abs(m) / 1000:.1f}B" if abs(m) >= 1000 else f"{sign}${abs(m):,.0f}M"


def write(projects, built, rows, pop):
    layers = (("urban", "Urban rail and BRT (25 metros)"), ("hsr", "High-speed rail"), ("conventional", "Conventional trains"))
    L = ["# Timing: every layer under the one budget", "",
         "Generated by `python study/timing.py`. Every project from steps 3-5, valued the same way and scheduled under "
         f"the statewide budget: ${STATE_MUSD / 1000:.1f}B a year of capital (DFW Transit's rate per resident), of which "
         f"Dallas-Fort Worth keeps ${DFW_MUSD / 1000:.1f}B for its own plan and ${OTHER_MUSD / 1000:.1f}B a year goes to "
         "everything here, 2025-2100, in 2025 dollars.", "",
         "**Value** is what travellers gain, from the same logit models that predict the riders: the logsum gain of "
         "every intercity traveller on a pair, and for the urban commute model (where transit's share is small) one "
         f"money coefficient's worth per new trip, ${1 / URBAN_B_PER_DOLLAR:.0f}. The **ratio** is benefit over cost across "
         "50 years at 3%: travellers' gain (plus any operating surplus) over capital plus the operating deficit "
         "(operating cost minus fares). Projects open best ratio first as the budget allows (spending spread over the "
         "construction years, carryover allowed, no borrowing). The budget is spent whether or not a ratio reaches 1, "
         "since the plan spends DFW's rate; a ratio of 1 or more means travellers' gains alone pay for it.", "",
         "## By layer", "",
         "| Layer | Projects | Built | Capital built | Trips a year (when valued) | Travellers' gain a year | Fares - operating cost a year | Ratio, built | Ratio 1 or more | Not built |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for key, lab in layers:
        ps = [p for p in projects if p["layer"] == key]
        bs = [p for p in ps if p.get("open")]
        cap = sum(p["capital"] for p in bs)
        t = sum(p["trips_year"] for p in bs)
        ben = sum(p["benefit"] for p in bs)
        margin = sum(p["fares"] - p["opex"] for p in bs)
        r = (ben + max(margin, 0)) * PV_FACTOR / (cap + max(-margin, 0) * PV_FACTOR) if cap else 0
        ok = [p for p in ps if p["bcr"] >= 1]
        L.append(f"| {lab} | {len(ps)} | {len(bs)} | {money(cap)} | {t / 1e6:.1f}M | {money(ben)} | "
                 f"{money(margin)} | {r:.2f} | {len(ok)} ({money(sum(p['capital'] for p in ok))}) | "
                 f"{money(sum(p['capital'] for p in ps if not p.get('open')))} |")
    last = rows[-1]
    cap_all = sum(p["capital"] for p in built)
    L += ["", f"**By 2100:** {money(cap_all)} built of {money(OTHER_MUSD * len(YEARS))} available "
          f"({money(OTHER_MUSD * len(YEARS) - cap_all)} unspent); {last['urban_trips_day']:,.0f} new daily urban transit "
          f"trips, {last['intercity_trips_year'] / 1e6:.0f}M intercity rail trips a year, about "
          f"{last['flights_day']:.0f} fewer flights a day, {money(last['benefit'])} a year of travellers' gain.", ""]
    L += ["## When things open", "", "| Year | Opening | Layer | Capital | Ratio |", "|---|---|---|---|---|"]
    for p in sorted(built, key=lambda p: (p["open"], -p["bcr"])):
        if p["layer"] == "urban":
            label = f"{p['metro_name']}: {p['name']} ({'regional rail' if p['mode'] == 'commuter' else p['mode']})"
        else:
            label = p["name"]
        L.append(f"| {p['open']} | {label} | {p['layer']} | {money(p['capital'])} | {p['bcr']:.2f} |")
    L += ["", "## Every decade", "", "| Year | Capital spent to date | New urban trips a day | Intercity rail trips a year | "
          "Fewer flights a day | Travellers' gain a year | Operating cost a year | Fares a year |", "|---|---|---|---|---|---|---|---|"]
    cum = 0.0
    for r in rows:
        cum += r["spend"]
        if r["year"] % 10 == 0 or r["year"] in (2025, 2100):
            L.append(f"| {r['year']} | {money(cum)} | {r['urban_trips_day']:,.0f} | {r['intercity_trips_year'] / 1e6:.1f}M | "
                     f"{r['flights_day']:.0f} | {money(r['benefit'])} | {money(r['opex'])} | {money(r['fares'])} |")
    nb = sorted((p for p in projects if not p.get("open")), key=lambda p: -p["bcr"])
    L += ["", "## Not built", "", "| Project | Layer | Capital | Ratio | Why |", "|---|---|---|---|---|"]
    for p in nb:
        why = "waits on a project not built" if any(
            not next(q for q in projects if q["id"] == d).get("open") for d in p["after"]) else "no budget left by 2100"
        label = f"{p['metro_name']}: {p['name']}" if p["layer"] == "urban" else p["name"]
        L.append(f"| {label} | {p['layer']} | {money(p['capital'])} | {p['bcr']:.2f} | {why} |")
    L += ["", "## Caveats", "",
          "- One dollar of travellers' gain is treated the same in every layer, but the urban figure is an approximation "
          "(exact only as transit's share goes to zero) and counts non-commute trips at the commute value; the "
          "intercity figure leaves out induced trips' own gain. Both include each mode's constant, so the ratios are "
          "only as good as those constants (high-speed rail's moves its first four corridors between 30M and 74M trips "
          "a year).",
          "- An urban trip is worth about $8 to its traveller in DFW Transit's commute model (its cost coefficient, a value "
          "of time near $12 an hour), an intercity trip $40-80. So the order favours the Triangle's high-speed lines and "
          "most metro lines open after 2050. Valuing urban trips higher, or counting congestion relief, would bring them "
          "forward.",
          "- Values grow with Texas's population trend from the year they were estimated; nothing else changes over "
          "time (no new land use around stations, no change in car travel or flying).",
          "- Travellers' gain is the only benefit counted: not less congestion for drivers, safety, emissions, or what "
          "stations do for land values and the economies of the places they join. Transit projects rarely pass a "
          "ratio of 1 on travellers' gains alone in US appraisals; the ratios rank projects more than they judge them.",
          "- Operating cost is outside the capital budget, as in DFW Transit; the deficits are in the ratio, but no "
          "budget pays them yet.",
          "- Dallas-Fort Worth's plan runs on its own timetable (DFW Transit) and isn't re-ranked here.", ""]
    with open(os.path.join(ROOT, "study", "timing.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    os.makedirs(os.path.join(ROOT, "docs", "data"), exist_ok=True)
    keep = ("id", "layer", "metro", "metro_name", "name", "mode", "km", "capital", "opex", "fares", "benefit", "trips_day",
            "trips_year", "air_day", "flights_day", "bcr", "start", "open", "chain", "after")
    data = {"budget_musd": STATE_MUSD, "dfw_musd": DFW_MUSD, "other_musd": OTHER_MUSD, "years": [YEARS[0], YEARS[-1]],
            "projects": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items() if k in keep} for p in projects],
            "yearly": [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]}
    with open(os.path.join(ROOT, "docs", "data", "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
