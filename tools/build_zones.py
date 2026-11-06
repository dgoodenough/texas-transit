"""County zones for the intercity model, and today's county-to-county commutes.

    python tools/build_zones.py

Writes:
- data/zones/counties.csv: one row per Texas county (254): name, 2020 population and its
  centre (Census CenPop 2020 block groups, population-weighted), land area (Census 2020
  Gazetteer), jobs at workplaces in the county (LODES 8 WAC, all jobs, 2022), and its metro or
  micro area (2023 OMB delineation).
- data/flows/lodes_county_commutes_2022.csv: home county, work county, commuters (LODES 8 OD,
  all jobs, 2022, both ends in Texas), for every pair with at least one commuter.

Downloads into data/raw/ (about 90 MB) the first time. 2022 matches the jobs year DFW
Transit's model uses.
"""
import collections
import csv
import gzip
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor", "dfw-transit"))
from metro import census  # noqa: E402  (dfw-transit's Census parsers)

RAW = os.path.join(ROOT, "data", "raw")
CENPOP = "https://www2.census.gov/geo/docs/reference/cenpop2020/blkgrp/CenPop2020_Mean_BG48.txt"
GAZ = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_Gaz_counties_national.zip"
LODES = "https://lehd.ces.census.gov/data/lodes/LODES8/tx/{kind}/tx_{kind}_{part}JT00_2022.csv.gz"
STATE = "48"


def fetch(url):
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, url.rsplit("/", 1)[1])
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
    return path


def gazetteer():
    """{county fips: (name, land km2)} for Texas, from the 2020 Census Gazetteer."""
    import zipfile
    with zipfile.ZipFile(fetch(GAZ)) as z:
        name = next(n for n in z.namelist() if n.endswith(".txt"))
        lines = z.read(name).decode("utf-8").splitlines()
    rows = csv.DictReader(lines, delimiter="\t")
    out = {}
    for r in rows:
        r = {k.strip(): v.strip() for k, v in r.items()}
        if r["GEOID"].startswith(STATE):
            out[r["GEOID"]] = (r["NAME"], int(r["ALAND"]) / 1e6)
    return out


def delineation():
    """{county fips: (cbsa code, cbsa title, 'metro' | 'micro')}, 2023 OMB delineation."""
    rows = census.read_xlsx_rows(fetch(census.CBSA_URL))
    hi = next(i for i, r in enumerate(rows) if r and "CBSA Code" in r)
    ix = {h: i for i, h in enumerate(rows[hi])}
    out = {}
    for r in rows[hi + 1:]:
        try:
            fips = f"{int(r[ix['FIPS State Code']]):02d}{int(r[ix['FIPS County Code']]):03d}"
        except (ValueError, IndexError, TypeError):
            continue   # notes at the foot of the sheet
        kind = "metro" if r[ix["Metropolitan/Micropolitan Statistical Area"]].startswith("Metropolitan") else "micro"
        out[fips] = (r[ix["CBSA Code"]], r[ix["CBSA Title"]], kind)
    return out


def main():
    gaz, cbsa = gazetteer(), delineation()
    pop, lat, lon = collections.Counter(), collections.Counter(), collections.Counter()
    for bg in census.parse_cenpop(fetch(CENPOP)).values():
        c, p = bg["county_fips"], bg["pop"]
        pop[c] += p
        lat[c] += p * bg["lat"]
        lon[c] += p * bg["lon"]
    jobs = collections.Counter()
    with gzip.open(fetch(LODES.format(kind="wac", part="S000_")), "rt") as f:
        for r in csv.DictReader(f):
            jobs[r["w_geocode"][:5]] += int(r["C000"])
    flows = collections.Counter()
    with gzip.open(fetch(LODES.format(kind="od", part="main_")), "rt") as f:
        rows = csv.reader(f)
        next(rows)
        for w, h, n, *_ in rows:   # w_geocode, h_geocode, S000 (all jobs), ...
            flows[(h[:5], w[:5])] += int(n)

    os.makedirs(os.path.join(ROOT, "data", "zones"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "data", "flows"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "zones", "counties.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["fips", "name", "pop_2020", "jobs_2022", "land_km2", "lat", "lon", "cbsa", "cbsa_name", "cbsa_kind"])
        for c in sorted(gaz):
            name, area = gaz[c]
            p = pop[c]
            # a county's centre of population; its land centre would need the polygons
            la, lo = (round(lat[c] / p, 5), round(lon[c] / p, 5)) if p else ("", "")
            code, title, kind = cbsa.get(c, ("", "", "rural"))
            w.writerow([c, name, p, jobs[c], round(area, 1), la, lo, code, title, kind])
    with open(os.path.join(ROOT, "data", "flows", "lodes_county_commutes_2022.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["home_fips", "work_fips", "commuters"])
        for (h, wk), n in sorted(flows.items()):
            w.writerow([h, wk, n])
    print(f"{len(gaz)} counties, {sum(pop.values()):,} residents, {sum(jobs.values()):,} jobs; "
          f"{len(flows):,} county pairs, {sum(flows.values()):,} commuters "
          f"({sum(n for (h, wk), n in flows.items() if h != wk):,} crossing a county line)")


if __name__ == "__main__":
    main()
