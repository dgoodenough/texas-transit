"""Conventional rail to Texas's neighbours and Monterrey, at a high level: riders, cost and the
comparison with high-speed rail on the corridors both could serve.

    python study/interstate_rail.py

1. Calibration. The conventional service's constant against car is fitted so the Heartland Flyer
   as it runs today (one train a day each way, Fort Worth - Oklahoma City) carries Amtrak's FY2024
   riders on today's travel; how much the timetable wait counts (wait_share) is set so four trains
   a day carry FREQ_RATIO times one train's riders (a frequency elasticity of FREQ_ELASTICITY).
2. Monterrey. The NextGen data stops at the border, so trips between Texas metros and Monterrey are
   a gravity model fitted on today's trips between US metros with a Texas end, times a border
   factor (assumption, tested), with an hour at the border for car and train alike. Air comes from
   the international segment data (US airport - Monterrey passengers, the latest 12 months).
3. Each corridor at two and four trains a day in 2050 (trend growth, induced trips): rail trips,
   capital, operating cost, fares, and new trips a year per $B. Corridors that only reach Texas
   through another one (Kansas City through Oklahoma City, Memphis through Longview) are counted
   on top of it. Only trips with a Texas end are counted (the data has no others), so the
   out-of-state corridors are undercounted: Oklahoma City - Kansas City riders are missing.

Writes study/interstate_rail.md.
"""
import copy
import csv
import json
import math
import os
import sys
import urllib.parse
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from texas import conventional as cv, hsr, intercity as ic  # noqa: E402

YEAR = 2050
FLYER_RIDERS_FY2024 = 80_000      # Amtrak FY2024 (Railfan, Progressive Railroading); FY2025 80,876
FREQ_ELASTICITY = 0.7             # intercity rail ridership vs trains a day (assumption, 0.5-0.8 in studies)
FREQ_RATIO = 4 ** FREQ_ELASTICITY
MONTERREY = {"name": "Monterrey, NL", "state": "NL", "pop": 5_341_171,   # INEGI 2020, metro area
             "at": (25.686, -100.316), "parts": [], "fips": [], "border_min": 60}
BORDER_FACTOR, BORDER_RANGE = 0.3, (0.15, 0.6)
# share of an airport's Monterrey passengers who start or end in its metro (hubs carry connections; assumption)
LOCAL_SHARE = {"SAT": 1.0, "AUS": 1.0, "ELP": 1.0, "HOU": 1.0, "DAL": 1.0, "IAH": 0.5, "DFW": 0.5}
AIRPORT_ZONE = {"SAT": "41700_TX", "AUS": "12420_TX", "ELP": "21340_TX", "HOU": "26420_TX", "IAH": "26420_TX",
                "DAL": "19100_TX", "DFW": "19100_TX"}
INTL = "https://data.transportation.gov/resource/xgub-n9bw.json"
TRAINS = (2, 4)
PLAN = [   # (corridor, the network it runs with, what its new trips are counted against)
    ("FLYER", ["DFW"], "today"),        # Dallas reaches the Flyer at Fort Worth (TRE connector)
    ("KC", ["DFW", "FLYER"], "under"),  # Kansas City reaches Texas through the Flyer
    ("I20", [], None),
    ("EAGLE", ["I20"], "under"),        # Memphis and Little Rock reach Dallas through Longview
    ("SUNSET", [], "today"),
    ("ABQ", [], None),
    ("MTY", [], None),
]
HSR_TWIN = {"FLYER": "OKC", "I20": "SHV", "SUNSET": "GULF"}   # the high-speed corridor on the same route


# ---------------------------------------------------------------- inputs
def monterrey_air(path=os.path.join(ROOT, "data", "flows", "air_monterrey.csv")):
    """{zone: air passengers a day to and from Monterrey} (fetched once, cached in data/flows)."""
    if not os.path.exists(path):
        last = json.load(urllib.request.urlopen(INTL + "?$select=max(data_dte)", timeout=60))[0]["max_data_dte"][:10]
        y, m = int(last[:4]), int(last[5:7])
        start = f"{y - 1}-{m + 1:02d}-01" if m < 12 else f"{y}-01-01"
        q = {"$select": "usg_apt,sum(total) as pax", "$group": "usg_apt", "$limit": "500",
             "$where": f"fg_apt='MTY' AND data_dte >= '{start}' AND data_dte <= '{last}'"}
        rows = json.load(urllib.request.urlopen(INTL + "?" + urllib.parse.urlencode(q), timeout=120))
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["airport", "passengers_12_months", "from", "to"])
            for r in sorted(rows, key=lambda r: -float(r["pax"])):
                if r["usg_apt"] in AIRPORT_ZONE:
                    w.writerow([r["usg_apt"], int(float(r["pax"])), start, last])
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            z = AIRPORT_ZONE[r["airport"]]
            out[z] = out.get(z, 0.0) + int(r["passengers_12_months"]) / 365 * LOCAL_SHARE[r["airport"]]
    return out


def gravity(base, zones):
    """ln(trips a day) = c + a ln(pop_a x pop_b) - g ln(km), fitted on today's trips between metro
    zones 150-1,500 km apart with a Texas end."""
    X, y = [], []
    for (a, b), d in base.items():
        za, zb = zones[a], zones[b]
        if "NonMSA" in za["name"] or "NonMSA" in zb["name"] or not 150 <= d["km"] <= 1500:
            continue
        t = d["car"] + d["air"]
        if t > 0:
            X.append([1.0, math.log(za["pop"] * zb["pop"]), -math.log(d["km"])])
            y.append(math.log(t))
    coef, *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)
    pred = np.array(X) @ coef
    r2 = 1 - ((np.array(y) - pred) ** 2).sum() / ((np.array(y) - np.mean(y)) ** 2).sum()
    return coef, r2, len(y)


def add_monterrey(base, zones, p, factor):
    """Monterrey as zone MTY, with trips to every Texas metro zone 150-1,500 km away."""
    coef, r2, n = gravity(base, zones)
    zones["MTY"] = dict(MONTERREY)
    air = monterrey_air()
    out = dict(base)
    for z, v in zones.items():
        if v["state"] != "TX" or "NonMSA" in v["name"]:
            continue
        dist = ic.km(v["at"], MONTERREY["at"])
        if not 150 <= dist <= 1500:
            continue
        total = factor * math.exp(coef[0] + coef[1] * math.log(v["pop"] * MONTERREY["pop"]) - coef[2] * math.log(dist))
        a = min(air.get(z, 0.0), 0.9 * total)
        out[tuple(sorted((z, "MTY")))] = {"km": dist, "car": total - a, "air": a, "work_share": 0.15, "air_fare": None}
    return out, (coef, r2, n), air


# ---------------------------------------------------------------- the model
def network(ids, svc):
    return ic.RailNetwork({s: cv.point(s) for s in cv.stations_of(ids)}, cv.network_links(ids), svc)


def evaluate(ids, tpd, trips_base, zones, p, growth=None):
    """(rail trips a day incl. induced, fares $ a day, air trips a day taken, results)."""
    svc = cv.service(p["conventional"], tpd)
    net = network(ids, svc)
    res = ic.run(trips_base, zones, p, net, growth)
    rail = sum(r["new"]["rail"] + r["new"]["induced"] for r in res.values())
    fares = 0.0
    for k, r in res.items():
        if r["new"]["rail"] > 0:
            los = net.los(zones[k[0]], zones[k[1]], "nonwork", p)
            if los:
                fares += (r["new"]["rail"] + r["new"]["induced"]) * los[2]
    air = sum(r["base"]["air"] - r["new"]["air"] for r in res.values())
    return rail, fares, air, res


def calibrate(trips_base, zones, p, log=print):
    """Fit wait_share (frequency elasticity) and asc_vs_car (the Flyer's riders) together."""
    target = FLYER_RIDERS_FY2024 / 365
    ids = ["DFW", "FLYER"]

    def fit_asc(q):
        lo, hi = -8.0, 6.0
        for _ in range(28):
            q["conventional"]["asc_vs_car"] = (lo + hi) / 2
            t = evaluate(ids, 1, trips_base, zones, q)[0] / (1 + q["conventional"]["induced_share"])
            lo, hi = ((lo + hi) / 2, hi) if t < target else (lo, (lo + hi) / 2)
        return q["conventional"]["asc_vs_car"]

    lo, hi = 0.01, 0.3
    q = copy.deepcopy(p)
    for _ in range(14):
        q["conventional"]["wait_share"] = (lo + hi) / 2
        fit_asc(q)
        t1 = evaluate(ids, 1, trips_base, zones, q)[0]
        t4 = evaluate(ids, 4, trips_base, zones, q)[0]
        lo, hi = ((lo + hi) / 2, hi) if t4 / t1 < FREQ_RATIO else (lo, (lo + hi) / 2)
    q["conventional"]["wait_share"] = round((lo + hi) / 2, 4)
    asc = round(fit_asc(q), 4)
    q["conventional"]["asc_vs_car"] = asc
    t1 = evaluate(ids, 1, trips_base, zones, q)[0]
    if log:
        log(f"calibrated: wait_share {q['conventional']['wait_share']}, asc_vs_car {asc:+.4f}: Flyer "
            f"{t1 / (1 + q['conventional']['induced_share']) * 365:,.0f} riders a year")
    return q


def save_params(q):
    path = os.path.join(ROOT, "texas", "intercity.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    for k in ("asc_vs_car", "wait_share"):
        d["conventional"][k] = q["conventional"][k]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------- study
def hsr_alone():
    """{corridor id: (trips a year built alone, capital $B)} from study/hsr_options.md."""
    out = {}
    names = {v[0]: k for k, v in hsr.CORRIDORS.items()}
    with open(os.path.join(ROOT, "study", "hsr_options.md"), encoding="utf-8") as f:
        for line in f:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 9 and cells[0].isdigit() and cells[1] in names:
                out[names[cells[1]]] = (float(cells[6].split("M")[0]), float(cells[3].strip("$B")))
    return out


def main():
    p = ic.load_params()
    zones = ic.load_zones()
    base = ic.base_trips(zones, p)
    tx = {k: v for k, v in base.items() if "TX" in (zones[k[0]]["state"], zones[k[1]]["state"])}
    q = calibrate(tx, zones, p)
    save_params(q)
    trips, (coef, r2, n), air = add_monterrey(tx, zones, q, BORDER_FACTOR)
    growth = ic.zone_growth({k: v for k, v in zones.items() if k != "MTY"}, YEAR)
    growth["MTY"] = growth["41700_TX"]   # Monterrey grows like San Antonio (assumption)
    svc = q["conventional"]
    rows = []
    for cid, under, against in PLAN:
        today = cv.CORRIDORS[cid][2]
        ids = under + [cid]
        for tpd in TRAINS:
            after = evaluate(ids, tpd, trips, zones, q, growth)
            if against == "under":      # the network it reaches Texas through, at the same timetable
                before = evaluate(under, tpd, trips, zones, q, growth)
            elif against == "today":    # today's trains on the same route
                before = evaluate(ids, today, trips, zones, q, growth)
            else:
                before = (0.0, 0.0, 0.0)
            rail, fares, air_off = (after[i] - before[i] for i in range(3))
            opex = cv.opex_musd(cid, tpd) - (cv.opex_musd(cid, today) if against == "today" else 0.0)
            rows.append({"id": cid, "tpd": tpd, "km": cv.route_km(cid), "rail": rail, "fares_musd": fares * 365 / 1e6,
                         "air": air_off, "capital": cv.capital_musd(cid, tpd, svc), "opex": opex,
                         "sets": cv.trainsets(cid, tpd, svc), "hours": cv.run_minutes(cid, svc) / 60})
            print(f"  {cid} {tpd}/day: +{rail * 365 / 1e6:.2f}M trips a year, ${rows[-1]['capital'] / 1000:.1f}B")
    # sensitivity: Monterrey border factor
    mty = {}
    for f in BORDER_RANGE:
        tr, _, _ = add_monterrey(tx, zones, q, f)
        mty[f] = evaluate(["MTY"], 4, tr, zones, q, growth)[0]
    write(rows, q, (coef, r2, n), air, trips, zones, mty, hsr_alone())


def write(rows, q, grav, air, trips, zones, mty, hsr_ref):
    svc = q["conventional"]
    coef, r2, n = grav
    L = ["# Interstate rail: conventional trains to Texas's neighbours and Monterrey", "",
         f"Generated by `python study/interstate_rail.py`. Travel in {YEAR} (today's long-distance trips grown with each "
         "county's population trend, as `study/hsr_options.md`), plus induced trips "
         f"({svc['induced_share']:.0%} of the trips rail takes). Corridors and costs: `texas/conventional.py`; service "
         "and model: `texas/intercity.json` (`conventional`), `texas/intercity.py`.", "",
         "Trains run at up to 79 mph on upgraded freight track: "
         f"{svc['speed_kmh']} km/h between stops, {svc['stop_min']} minutes a stop, fares "
         f"${svc['fare_fixed']} + ${svc['fare_per_km']:.2f} a km, trains spread over {svc['service_hours']} hours. Trips under "
         f"{svc['min_km']} km are left to the car: with two or four trains a day, the wait outweighs the ride.", "",
         "## Calibration", "",
         f"- **Riders:** the constant against car ({svc['asc_vs_car']:+.2f}) is set so the Heartland Flyer as it runs today, "
         f"one train a day each way, carries Amtrak's FY2024 {FLYER_RIDERS_FY2024:,} riders on today's travel.",
         f"- **Frequency:** waiting counts {svc['wait_share']:.3f} of the headway (people plan around a timetable), set so "
         f"four trains a day carry {FREQ_RATIO:.1f} times one train's riders, a frequency elasticity of {FREQ_ELASTICITY} "
         "(an assumption in the range intercity rail studies find).",
         f"- **Monterrey:** a gravity model of trips between US metro zones with a Texas end, 150-1,500 km apart "
         f"({n} pairs, R² {r2:.2f}): trips rise with (population x population)^{coef[1]:.2f} and fall with "
         f"distance^{coef[2]:.2f}, times a border factor of {BORDER_FACTOR} (assumption; tested at "
         f"{BORDER_RANGE[0]} and {BORDER_RANGE[1]}), with an hour at the border for car and train alike. Monterrey: "
         f"{MONTERREY['pop'] / 1e6:.1f}M people (INEGI 2020).", ""]
    sa = trips.get(tuple(sorted(("41700_TX", "MTY"))))
    if sa:
        L += [f"  Check: San Antonio - Monterrey comes out at {sa['car'] + sa['air']:,.0f} trips a day today; San Antonio's "
              f"airport alone carries {air.get('41700_TX', 0):,.0f} passengers a day to and from Monterrey "
              f"(international segment data, latest 12 months), {sa['air'] / (sa['car'] + sa['air']):.0%} of that. Houston's "
              f"and Dallas's airports carry more (about 1,200 and 1,100 a day), but as hubs much of that is connecting; "
              "half is counted as local (assumption).", ""]
    L += ["## Each corridor", "",
          "New trips are on top of today's trains where there are some (Heartland Flyer and Texas Eagle one a day, "
          "Sunset three a week) and, for Kansas City and Memphis, on top of the corridor they reach Texas through, run "
          "with the same timetable (the Texas Eagle's one train a day east of Longview is not subtracted). *Per $B* is new trips a year per $B of capital. *Operating gap* is operating cost minus "
          "fares, a year.", "",
          "| Corridor | Route km | Trains a day each way | Time end to end | New trips a year | Capital | Per $B | "
          "Operating cost | Fares | Operating gap | Air trips a day taken |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        gap = r["opex"] - r["fares_musd"]
        L.append(f"| {cv.CORRIDORS[r['id']][0]} | {r['km']:,.0f} | {r['tpd']} | {r['hours']:.1f} h | "
                 f"{r['rail'] * 365 / 1e6:.2f}M | ${r['capital'] / 1000:.1f}B | {r['rail'] * 365 / 1e6 / (r['capital'] / 1000):.2f}M | "
                 f"${r['opex']:.0f}M | ${r['fares_musd']:.0f}M | ${gap:.0f}M | {r['air']:,.0f} |")
    four = {r["id"]: r for r in rows if r["tpd"] == 4}
    cap4 = sum(r["capital"] for r in four.values())
    trips4 = sum(r["rail"] for r in four.values())
    gap4 = sum(r["opex"] - r["fares_musd"] for r in four.values())
    L += ["", f"**All seven at four trains a day:** {trips4 * 365 / 1e6:.1f}M new trips a year for ${cap4 / 1000:.1f}B of "
          f"capital ({trips4 * 365 / 1e6 / (cap4 / 1000):.2f}M per $B) and an operating gap of ${gap4:.0f}M a year.", "",
          "## Against high-speed rail on the same routes", "",
          "| Route | Conventional, 4 trains a day: trips a year, capital, per $B | High-speed, built alone: trips a year, capital, per $B |",
          "|---|---|---|"]
    for cid, hid in HSR_TWIN.items():
        r = four[cid]
        t, c = hsr_ref[hid]
        L.append(f"| {cv.CORRIDORS[cid][0]} | {r['rail'] * 365 / 1e6:.2f}M, ${r['capital'] / 1000:.1f}B, "
                 f"{r['rail'] * 365 / 1e6 / (r['capital'] / 1000):.2f}M | {t:.1f}M, ${c:.1f}B, {t / c:.2f}M |")
    L += ["", "High-speed rail carries several times the riders on each route, but conventional trains carry more per "
          "dollar of capital, at least for the few trains a day modelled here. The high-speed figures include trips "
          "within Texas that the conventional rows also have (Dallas - Longview, Houston - Beaumont).", "",
          "### Monterrey's border factor (trips a year at four trains a day)", "", "| Border factor | Trips a year |",
          "|---|---|"]
    for f, t in sorted(mty.items()):
        L.append(f"| {f} | {t * 365 / 1e6:.2f}M |")
    L.append(f"| {BORDER_FACTOR} (as above) | {four['MTY']['rail'] * 365 / 1e6:.2f}M |")
    L += ["", "## Caveats", "",
          "- Only trips with a Texas end are counted (NextGen's Texas extract), so Oklahoma City - Kansas City, "
          "Shreveport - Jackson or Little Rock - Memphis riders are missing: the out-of-state corridors are undercounted.",
          "- One calibration point (the Heartland Flyer) and an assumed frequency elasticity. Station-to-station "
          "ridership for the Texas Eagle and the Sunset Limited would test it; Amtrak's state fact sheets list station "
          "totals.",
          "- Capital is a per-km allowance on top of freight railroads' track, not an engineering estimate: what a host "
          "railroad asks for (sidings, double track, dispatching agreements) varies several times over. Kansas City and "
          "Memphis need agreements with BNSF and Union Pacific; Monterrey with CPKC and Mexican customs.",
          "- Monterrey's demand is a gravity model with an assumed border factor, not data; the air check is loose.",
          "- These trains would also feed high-speed rail and the urban networks (Fort Worth, Dallas, Houston, San "
          "Antonio); the study counts each corridor on its own.", ""]
    with open(os.path.join(ROOT, "study", "interstate_rail.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
