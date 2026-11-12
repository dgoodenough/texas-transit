"""The metro registry the urban layer runs on: urban/metros.json, in DFW Transit's format
(vendor/dfw-transit/metro/metros.json), for every Texas metro area except Dallas-Fort Worth,
which has its own plan (DFW Transit).

    python tools/build_metro_registry.py

From the 2023 OMB delineation (data/raw/list1_2023.xlsx; every county of each metropolitan
area with a Texas county, so Texarkana includes Miller County, Arkansas) and the 2020 Census
Gazetteer of places (reference points). Extra keys this repo adds, which DFW Transit ignores:
  texas_pop     2020 population of the metro's Texas counties (the budget is Texas's money)
  buildout      true for the metros the generator runs in build-out mode (BUILDOUT below)
  policies      true for the metros with the 2 million plan's policy package (POLICY_METROS below)
  anchors       places lines should reach (downtown, airports, campuses, medical districts; ANCHORS below)
  border        ports of entry: people crossing from Mexico a day, on foot or by bus, added to the zone at
                their bridge (data/urban/border_crossings.json, tools/fetch_border.py; `--border` applies
                just this to the current registry)
  budget_musd   capital budget: DFW Transit's rate per resident ($2.3B a year for 7.47M people)
                x texas_pop x 30 years, the generator's default horizon (as DFW Transit's
                generated Houston and Eugene); 75 years, DFW Transit's horizon, for the build-out
                and policy metros
  growth        the metro's own regional multipliers for the generator (vendor/dfw-transit metro/model.py
                metro_cfg), replacing DFW's forecast: regional_pop relative to 2020 from its counties'
                trend (data/zones/county_growth.csv, tools/build_growth.py), regional_jobs the same growth
                relative to its LODES year (no county jobs forecast: jobs keep pace with people)
Calibration keys (`calibration`, `ridership_asc`) are added by study/urban_metros.py.

`downtowns` are the principal city's Gazetteer internal point, labelled as such: the generator
uses them only when a metro has no jobs data, and every Texas metro has LODES jobs.
"""
import collections
import csv
import io
import json
import os
import re
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor", "dfw-transit"))
from metro import census  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
GAZ = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_Gaz_place_national.zip"
OUT = os.path.join(ROOT, "urban", "metros.json")
DFW_MUSD_PER_YEAR, DFW_POP, YEARS = 2300, 7_468_799, 30   # as study/size_texas.py; 30: metro/generate.json
# Metros the generator runs in build-out mode (vendor/dfw-transit metro/generate.json buildout), with
# DFW Transit's whole 75-year horizon at its rate per resident: their layout can carry a DFW-sized
# network and the default generator stops well short of it (study/metro_potential.md). Not Houston
# (its default network already carries more, 3.75% of commutes against 3.6%), El Paso (build-out
# splits its few strong corridors) or the small metros (no corridor dense enough).
BUILDOUT, BUILDOUT_YEARS = {"austin", "san-antonio"}, 75
# Metros that get the 2 million plan's policy package (study/urban_metros.py POLICIES: frequent feeders, bikes and
# drop-off to stations, longer walks, parking prices at the densest job centers) and, like the build-out metros,
# DFW Transit's whole 75-year horizon as their budget: the four whose layout matches DFW's under the same
# treatment (study/metro_potential.md). Too few people live near the smaller metros' corridors for either.
POLICY_METROS = {"houston", "austin", "san-antonio", "el-paso"}
STATES = {"48": "tx", "05": "ar", "22": "la", "35": "nm", "40": "ok"}
# Routes NTD files as bus rapid transit (mode RB): only Houston's Silver Line. MetroRapid
# (Austin), Primo (San Antonio) and Brio (El Paso) are filed as plain bus and run mostly in
# mixed traffic, so here they are today's frequent buses and the generator may propose real BRT
# on their streets.
BRT = {"houston": r"Silver Line|\bBRT\b"}
# Anchors (vendor/dfw-transit metro/anchors.py): places a line should reach even when they aren't the
# densest spots: the downtown (city hall), airports, big campuses, medical districts. weight: riders a day
# it draws beyond the people and jobs around it (assumption: about a third of an airport's daily
# passengers, a half of a campus's students).
def border(mid):
    """The metro's ports of entry: [{port, bridge, lat, lon, pedestrians_day, bus_day}] (tools/fetch_border.py)."""
    p = os.path.join(ROOT, "data", "urban", "border_crossings.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    out = [{"port": q["port"], "bridge": q["bridge"], "lat": q["lat"], "lon": q["lon"],
            "pedestrians_day": q.get("pedestrians_day", 0), "bus_day": q.get("bus_passengers_day", 0),
            "source": d["source"]} for q in d["ports"] if q["metro"] == mid]
    return out or None


VALLEY = ("rio-grande-valley", "Rio Grande Valley (McAllen-Edinburg-Mission and Brownsville-Harlingen), TX",
          ["mcallen", "brownsville"])


def merge_valley(metros):
    """One network for the Valley (study/second_session.md, item 21): McAllen-Edinburg-Mission and
    Brownsville-Harlingen are one 1.3M-person region the census splits in two; one entry with both
    counties, both downtowns and every port of entry, the budgets and people summed."""
    vid, name, parts = VALLEY
    ps = [e for e in metros if e["id"] in parts]
    if len(ps) < 2:
        return metros
    e = {"id": vid, "name": name, "cbsa": "+".join(p["cbsa"] for p in ps),
         "state_fips": ["48"], "state_abbr": {"48": "tx"},
         "county_fips": [f for p in ps for f in p["county_fips"]],
         "county_names": {k: v for p in ps for k, v in p["county_names"].items()},
         "downtowns": [d for p in ps for d in p.get("downtowns", [])],
         "texas_pop": sum(p["texas_pop"] for p in ps), "budget_musd": sum(p["budget_musd"] for p in ps),
         "merged_from": parts, "cbsa_pop": {p["cbsa"]: p["texas_pop"] for p in ps}}
    if all(p.get("growth") for p in ps):   # people-weighted
        w = [p["texas_pop"] for p in ps]
        e["growth"] = {"_doc": ps[0]["growth"].get("_doc", "") + "; the two metros' trends, people-weighted"}
        for k in ("regional_pop", "regional_jobs"):
            yrs = set.intersection(*(set(p["growth"][k]) for p in ps))
            e["growth"][k] = {y: round(sum(p["growth"][k][y] * wi for p, wi in zip(ps, w)) / sum(w), 4) for y in sorted(yrs)}
    b = [q for p in ps for q in (p.get("border") or [])]
    if b:
        e["border"] = b
    keep = [m for m in metros if m["id"] not in parts]
    keep.append(e)
    keep.sort(key=lambda m: -m["texas_pop"])
    return keep


def valley_only():
    """Apply merge_valley() to the registry as it is (no downloads)."""
    with open(OUT, encoding="utf-8") as f:
        reg = json.load(f)
    reg["metros"] = merge_valley(reg["metros"])
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1)
        f.write("\n")
    print([m["id"] for m in reg["metros"]][:8])


def border_only():
    """Apply border() to the registry as it is (no downloads)."""
    with open(OUT, encoding="utf-8") as f:
        reg = json.load(f)
    for e in reg["metros"]:
        b = border(e["id"]) or [q for mid in e.get("merged_from", []) for q in (border(mid) or [])] or None
        if b:
            e["border"] = b
        else:
            e.pop("border", None)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1)
        f.write("\n")
    print("border:", ", ".join(f"{e['id']} {sum(p['pedestrians_day'] + p['bus_day'] for p in e['border']):,}"
                               for e in reg["metros"] if e.get("border")))


ANCHORS = {
    "houston": [("Downtown Houston", 29.7604, -95.3698, "downtown", 0), ("Bush Intercontinental Airport", 29.9902, -95.3368, "airport", 30000),
                ("Hobby Airport", 29.6454, -95.2789, "airport", 8000), ("Texas Medical Center", 29.7071, -95.3978, "medical", 30000),
                ("University of Houston", 29.7199, -95.3422, "university", 20000), ("Rice University", 29.7174, -95.4018, "university", 4000)],
    "austin": [("Downtown Austin", 30.2672, -97.7431, "downtown", 0), ("Austin-Bergstrom Airport", 30.1975, -97.6664, "airport", 20000),
               ("University of Texas", 30.2849, -97.7341, "university", 25000), ("Texas State University", 29.8884, -97.9384, "university", 18000)],
    "san-antonio": [("Downtown San Antonio", 29.4241, -98.4936, "downtown", 0), ("San Antonio Airport", 29.5337, -98.4698, "airport", 10000),
                    ("UTSA", 29.5830, -98.6197, "university", 17000), ("South Texas Medical Center", 29.5100, -98.5780, "medical", 20000)],
    "el-paso": [("Downtown El Paso", 31.7587, -106.4869, "downtown", 0), ("El Paso Airport", 31.8072, -106.3778, "airport", 4000),
                ("UTEP", 31.7709, -106.5047, "university", 12000)],
    "college-station": [("Texas A&M University", 30.6187, -96.3365, "university", 35000)],
    "lubbock": [("Texas Tech University", 33.5843, -101.8783, "university", 20000)],
    "waco": [("Baylor University", 31.5489, -97.1131, "university", 10000)],
}


def fetch(url):
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, url.rsplit("/", 1)[1])
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path + ".part")
        os.replace(path + ".part", path)
    return path


def slug(title):
    first = title.split(",")[0].split("-")[0]
    return re.sub(r"[^a-z]+", "-", first.lower()).strip("-")


def places():
    out = {}
    with zipfile.ZipFile(fetch(GAZ)) as z:
        name = next(n for n in z.namelist() if n.endswith(".txt"))
        text = io.TextIOWrapper(z.open(name), encoding="latin-1")
        rows = csv.reader(text, delimiter="\t")
        head = [h.strip() for h in next(rows)]
        ix = {h: i for i, h in enumerate(head)}
        for r in rows:
            out[(r[ix["USPS"]], r[ix["NAME"]])] = (float(r[ix["INTPTLAT"]]), float(r[ix["INTPTLONG"]].strip()))
    return out


def county_trend():
    """{county_fips: {year: population}} from data/zones/county_growth.csv."""
    out = {}
    with open(os.path.join(ROOT, "data", "zones", "county_growth.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["county_fips"]] = {int(k[4:]): float(v) for k, v in r.items() if k.startswith("pop_")}
    return out


def interp(table, year):
    ks = sorted(table)
    lo = max(k for k in ks if k <= year)
    hi = min(k for k in ks if k >= year)
    return table[lo] if lo == hi else table[lo] + (table[hi] - table[lo]) * (year - lo) / (hi - lo)


def growth(fips, trend, mid):
    """The metro's regional multipliers (registry `growth`) from its counties' trend."""
    tot = collections.Counter()
    for f in fips:
        for y, v in trend[f].items():
            tot[y] += v
    years = [y for y in sorted(tot) if y >= 2020]
    meta = os.path.join(ROOT, "urban", "data", "metros", mid, "meta.json")
    jy = 2023
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as f:
            jy = (json.load(f).get("sources", {}).get("lodes_wac") or {}).get("year") or jy
    p20, pj = tot[2020], interp(tot, jy)
    return {"_doc": f"County trend (tools/build_growth.py); jobs relative to LODES {jy}, growing with people",
            "regional_pop": {str(y): round(tot[y] / p20, 4) for y in years},
            "regional_jobs": {str(jy): 1.0, **{str(y): round(tot[y] / pj, 4) for y in years if y > jy}}}


def main():
    trend = county_trend()
    rows = census.read_xlsx_rows(os.path.join(RAW, "list1_2023.xlsx"))
    hi = next(i for i, r in enumerate(rows) if r and "CBSA Code" in r)
    ix = {h: i for i, h in enumerate(rows[hi])}
    counties, title, names = collections.defaultdict(list), {}, {}
    for r in rows[hi + 1:]:
        try:
            fips = f"{int(r[ix['FIPS State Code']]):02d}{int(r[ix['FIPS County Code']]):03d}"
        except (ValueError, IndexError, TypeError):
            continue
        if not r[ix["Metropolitan/Micropolitan Statistical Area"]].startswith("Metropolitan"):
            continue
        code = r[ix["CBSA Code"]]
        counties[code].append(fips)
        title[code] = r[ix["CBSA Title"]]
        names[fips] = r[ix["County/County Equivalent"]].replace(" County", "").replace(" Parish", "")
    texas = [c for c, fs in counties.items() if any(f.startswith("48") for f in fs) and c != "19100"]
    pop = collections.Counter()
    for bg in census.parse_cenpop(os.path.join(RAW, "CenPop2020_Mean_BG48.txt")).values():
        pop[bg["county_fips"]] += bg["pop"]
    gaz = places()
    metros = []
    for code in texas:
        fs = sorted(counties[code])
        mid = slug(title[code])
        city = title[code].split(",")[0].split("-")[0]
        pt = gaz.get(("TX", city + " city"))
        if pt is None:
            raise SystemExit(f"no Gazetteer place for {city}")
        tx_pop = sum(pop[f] for f in fs if f.startswith("48"))
        states = sorted({f[:2] for f in fs})
        e = {"id": mid, "name": title[code], "cbsa": code, "state_fips": states,
             "state_abbr": {s: STATES[s] for s in states}, "county_fips": fs,
             "county_names": {f: names[f] for f in fs},
             "downtowns": [{"name": f"{city} (city's Census internal point)", "lat": pt[0], "lon": pt[1]}],
             "texas_pop": tx_pop,
             "budget_musd": round(DFW_MUSD_PER_YEAR * tx_pop / DFW_POP * (BUILDOUT_YEARS if mid in BUILDOUT | POLICY_METROS else YEARS))}
        e["growth"] = growth(fs, trend, mid)
        if mid in BUILDOUT:
            e["buildout"] = True
        if mid in POLICY_METROS:
            e["policies"] = True
        if mid in BRT:
            e["brt_name_pattern"] = BRT[mid]
        if mid in ANCHORS:
            e["anchors"] = [{"name": n, "lat": la, "lon": lo, "kind": k, "weight": w} for n, la, lo, k, w in ANCHORS[mid]]
        if border(mid):
            e["border"] = border(mid)
        metros.append(e)
    metros.sort(key=lambda e: -e["texas_pop"])
    metros = merge_valley(metros)
    old, keep_top = {}, {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            prev = json.load(f)
        old = {m["id"]: m for m in prev["metros"]}
        keep_top = {k: v for k, v in prev.items() if k not in ("_doc", "metros")}   # e.g. _calibration
    for e in metros:   # keep the calibration keys study/urban_metros.py wrote
        for k in ("calibration", "ridership_asc"):
            if k in old.get(e["id"], {}):
                e[k] = old[e["id"]][k]
    doc = ("Texas metro areas other than Dallas-Fort Worth, in DFW Transit's registry format "
           "(vendor/dfw-transit/metro/metros.json). Written by tools/build_metro_registry.py; calibration keys "
           "by study/urban_metros.py.")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"_doc": doc, "metros": metros, **keep_top}, f, indent=1)
        f.write("\n")
    for e in metros:
        print(f"{e['id']:16s} {e['cbsa']} {len(e['county_fips']):2d} counties  {e['texas_pop']:>10,}  "
              f"${e['budget_musd'] / 1000:5.1f}B  {e['name']}")
    print(f"{len(metros)} metros, {sum(e['texas_pop'] for e in metros):,} people, "
          f"${sum(e['budget_musd'] for e in metros) / 1000:.0f}B")


if __name__ == "__main__":
    if "--border" in sys.argv:
        border_only()
    elif "--valley" in sys.argv:
        valley_only()
    else:
        main()
