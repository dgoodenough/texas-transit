"""The metro registry the urban layer runs on: urban/metros.json, in DFW Transit's format
(vendor/dfw-transit/metro/metros.json), for every Texas metro area except Dallas-Fort Worth,
which has its own plan (DFW Transit).

    python tools/build_metro_registry.py

From the 2023 OMB delineation (data/raw/list1_2023.xlsx; every county of each metropolitan
area with a Texas county, so Texarkana includes Miller County, Arkansas) and the 2020 Census
Gazetteer of places (reference points). Extra keys this repo adds, which DFW Transit ignores:
  texas_pop     2020 population of the metro's Texas counties (the budget is Texas's money)
  budget_musd   capital budget: DFW Transit's rate per resident ($2.3B a year for 7.47M people)
                x texas_pop x 30 years, the generator's default horizon (as DFW Transit's
                generated Houston and Eugene)
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
STATES = {"48": "tx", "05": "ar", "22": "la", "35": "nm", "40": "ok"}
# Routes NTD files as bus rapid transit (mode RB): only Houston's Silver Line. MetroRapid
# (Austin), Primo (San Antonio) and Brio (El Paso) are filed as plain bus and run mostly in
# mixed traffic, so here they are today's frequent buses and the generator may propose real BRT
# on their streets.
BRT = {"houston": r"Silver Line|\bBRT\b"}


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


def main():
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
             "budget_musd": round(DFW_MUSD_PER_YEAR * tx_pop / DFW_POP * YEARS)}
        if mid in BRT:
            e["brt_name_pattern"] = BRT[mid]
        metros.append(e)
    metros.sort(key=lambda e: -e["texas_pop"])
    old = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            old = {m["id"]: m for m in json.load(f)["metros"]}
    for e in metros:   # keep the calibration keys study/urban_metros.py wrote
        for k in ("calibration", "ridership_asc"):
            if k in old.get(e["id"], {}):
                e[k] = old[e["id"]][k]
    doc = ("Texas metro areas other than Dallas-Fort Worth, in DFW Transit's registry format "
           "(vendor/dfw-transit/metro/metros.json). Written by tools/build_metro_registry.py; calibration keys "
           "by study/urban_metros.py.")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"_doc": doc, "metros": metros}, f, indent=1)
        f.write("\n")
    for e in metros:
        print(f"{e['id']:16s} {e['cbsa']} {len(e['county_fips']):2d} counties  {e['texas_pop']:>10,}  "
              f"${e['budget_musd'] / 1000:5.1f}B  {e['name']}")
    print(f"{len(metros)} metros, {sum(e['texas_pop'] for e in metros):,} people, "
          f"${sum(e['budget_musd'] for e in metros) / 1000:.0f}B")


if __name__ == "__main__":
    main()
