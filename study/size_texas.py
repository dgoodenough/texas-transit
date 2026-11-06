"""Size Texas for the statewide plan: population by metro area (2020 Census block groups, 2023
OMB delineation), straight-line distances between the largest metros, and the budget at DFW
Transit's spending rate per resident.

    python study/size_texas.py

Downloads two Census files into data/raw/ (about 15 MB) the first time.
"""
import collections
import csv
import math
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor", "dfw-transit"))
from metro import census  # noqa: E402  (dfw-transit's Census parsers)

RAW = os.path.join(ROOT, "data", "raw")
CENPOP = "https://www2.census.gov/geo/docs/reference/cenpop2020/blkgrp/CenPop2020_Mean_BG48.txt"
# DFW Transit's budget: $2.3B a year (config.json budget.musd_per_year) for the 7.47M people of
# its nine-county model area (data/metroplex_density.csv, 2020)
DFW_MUSD_PER_YEAR, DFW_POP = 2300, 7_468_799
YEARS = 75   # 2025-2100


def fetch(url):
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, url.rsplit("/", 1)[1])
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
    return path


def km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    h = math.sin(math.radians(la2 - la1) / 2) ** 2 + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def main():
    rows = census.read_xlsx_rows(fetch(census.CBSA_URL))
    hi = next(i for i, r in enumerate(rows) if r and "CBSA Code" in r)
    ix = {h: i for i, h in enumerate(rows[hi])}
    cbsa_of, title, metro = {}, {}, {}
    for r in rows[hi + 1:]:
        try:
            fips = f"{int(r[ix['FIPS State Code']]):02d}{int(r[ix['FIPS County Code']]):03d}"
        except (ValueError, IndexError, TypeError):
            continue   # notes at the foot of the sheet
        code = r[ix["CBSA Code"]]
        cbsa_of[fips], title[code] = code, r[ix["CBSA Title"]]
        metro[code] = r[ix["Metropolitan/Micropolitan Statistical Area"]].startswith("Metropolitan")
    pop, lat, lon = collections.Counter(), collections.Counter(), collections.Counter()
    for bg in census.parse_cenpop(fetch(CENPOP)).values():
        c = cbsa_of.get(bg["county_fips"])
        c = c if c and metro[c] else "outside metro areas"
        pop[c] += bg["pop"]
        lat[c] += bg["pop"] * bg["lat"]
        lon[c] += bg["pop"] * bg["lon"]
    total = sum(pop.values())
    per_res = DFW_MUSD_PER_YEAR * 1e6 / DFW_POP
    print(f"Texas 2020: {total / 1e6:.2f}M residents")
    print(f"Budget at DFW Transit's rate (${per_res:.0f} per resident a year): "
          f"${per_res * total / 1e9:.1f}B a year, ${per_res * total * YEARS / 1e9:.0f}B over {YEARS} years (2025 $)")
    metros = sorted((c for c in pop if c != "outside metro areas"), key=lambda c: -pop[c])
    print(f"{len(metros)} metro areas; the largest four hold {sum(pop[c] for c in metros[:4]) / total:.0%}; "
          f"{pop['outside metro areas'] / 1e6:.1f}M live outside metro areas")
    with open(os.path.join(ROOT, "study", "texas_metros.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["cbsa", "name", "pop_2020", "lat", "lon"])
        for c in metros:
            w.writerow([c, title[c], pop[c], round(lat[c] / pop[c], 4), round(lon[c] / pop[c], 4)])
    for c in metros[:12]:
        print(f"  {title[c]:45s} {pop[c] / 1e6:5.2f}M")
    cen = {c: (lat[c] / pop[c], lon[c] / pop[c]) for c in metros}
    short = lambda c: title[c].split(",")[0].split("-")[0]
    print("Straight-line km between centres of population:")
    for a in metros[:6]:
        print(f"  {short(a):12s}", ", ".join(f"{short(b)} {km(cen[a], cen[b]):.0f}" for b in metros[:6] if b != a))


if __name__ == "__main__":
    main()
