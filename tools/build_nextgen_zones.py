"""The NextGen OD zones (583 nationally: metro areas and the non-metro rest of each state) with
their 2020 population and centre of population, so the long-distance trip data can be placed.

    python tools/build_nextgen_zones.py

Each US county's 2020 centre of population (Census CenPop 2020) is assigned to the zone polygon
that contains it (NextGen zone shapefile, NAD83 latitude / longitude). Writes
data/zones/nextgen_zones.csv (zone_id, name, state, cbsa, pop_2020, lat, lon, counties) and
data/zones/county_zones.csv (each county's zone, population and centre: how a zone's people are
spread, for station access).
"""
import collections
import csv
import io
import os
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from texas import shapes  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
ZONES = "https://nhts.ornl.gov/od/assets/data/NextGen_OD_Zone_ESRI_11152022.zip"
COUNTIES = "https://www2.census.gov/geo/docs/reference/cenpop2020/county/CenPop2020_Mean_CO.txt"


def fetch(url, sub=""):
    d = os.path.join(RAW, sub)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, url.rsplit("/", 1)[1])
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
    return path


def main():
    with zipfile.ZipFile(fetch(ZONES, "nhts")) as z:
        base = next(n for n in z.namelist() if n.endswith(".shp"))[:-4]
        polys = shapes.read_polygons(z.read(base + ".shp"))
        table = list(csv.DictReader(io.StringIO(z.read(base + ".csv").decode("utf-8", "replace"))))
    assert len(polys) == len(table), "shapes and attribute rows should line up"
    boxes = [shapes.bbox(p) if p else None for p in polys]
    pop, lat, lon, n = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    unplaced, county_rows = [], []
    with open(fetch(COUNTIES), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            y, x, p = float(r["LATITUDE"]), float(r["LONGITUDE"]), int(r["POPULATION"])
            hit = next((i for i, b in enumerate(boxes) if b and b[0] <= x <= b[2] and b[1] <= y <= b[3]
                        and shapes.contains(polys[i], x, y)), None)
            if hit is None:
                unplaced.append(f"{r['COUNAME']}, {r['STNAME']}")
                continue
            z = table[hit]["zone_id"]
            county_rows.append([r["STATEFP"] + r["COUNTYFP"], z, p, round(y, 5), round(x, 5)])
            pop[z] += p
            lat[z] += p * y
            lon[z] += p * x
            n[z] += 1
    out = os.path.join(ROOT, "data", "zones", "nextgen_zones.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["zone_id", "name", "state", "cbsa", "pop_2020", "lat", "lon", "counties"])
        for r in table:
            z = r["zone_id"]
            p = pop[z]
            w.writerow([z, r["zone_name"], r["state_abb"], r["CBSAFP2"], p,
                        round(lat[z] / p, 4) if p else "", round(lon[z] / p, 4) if p else "", n[z]])
    with open(os.path.join(ROOT, "data", "zones", "county_zones.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["county_fips", "zone_id", "pop_2020", "lat", "lon"])
        w.writerows(sorted(county_rows))
    print(f"{out}: {len(table)} zones, {sum(pop.values()):,} people in {sum(n.values())} counties; "
          f"{len(unplaced)} counties outside every zone: {unplaced[:8]}")


if __name__ == "__main__":
    main()
