"""County population by year, extended from the 2010-2020 Census trend.

    python tools/build_growth.py

Each US county keeps its own 2010-2020 annual growth rate, fading by half every HALF_LIFE years
(so fast-growing counties don't compound without end), from its 2020 population. Writes
data/zones/county_growth.csv: county_fips, pop_2010, pop_2020, then a column per year in YEARS.

This is a trend extrapolation, not an official projection. The Texas Demographic Center's county
projections (to 2060) would replace it; their download is behind a usage survey for its users
to answer, so it isn't fetched here.
"""
import csv
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
URL = "https://www2.census.gov/geo/docs/reference/cenpop{y}/county/CenPop{y}_Mean_CO.txt"
YEARS = [2030, 2040, 2050, 2060, 2075, 2100]
HALF_LIFE = 40   # years for a county's growth rate to fall by half (assumption)


def counties(year):
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, f"CenPop{year}_Mean_CO.txt")
    if not os.path.exists(path):
        urllib.request.urlretrieve(URL.format(y=year), path)
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return {r["STATEFP"].zfill(2) + r["COUNTYFP"].zfill(3): int(r["POPULATION"]) for r in csv.DictReader(f)}


def project(p2010, p2020, year):
    """Population in `year`: the 2010-2020 rate, decaying exponentially with HALF_LIFE."""
    if p2010 <= 0 or p2020 <= 0:
        return p2020
    rate = (p2020 / p2010) ** 0.1 - 1          # annual, 2010-2020
    pop = p2020
    for t in range(year - 2020):
        pop *= 1 + rate * 0.5 ** (t / HALF_LIFE)
    return pop


def main():
    c10, c20 = counties(2010), counties(2020)
    out = os.path.join(ROOT, "data", "zones", "county_growth.csv")
    tx = {y: 0.0 for y in [2020] + YEARS}
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["county_fips", "pop_2010", "pop_2020"] + [f"pop_{y}" for y in YEARS])
        for fips in sorted(c20):
            p10 = c10.get(fips, 0)   # a county created after 2010 keeps its 2020 population
            row = [round(project(p10, c20[fips], y)) for y in YEARS]
            w.writerow([fips, p10, c20[fips]] + row)
            if fips.startswith("48"):
                tx[2020] += c20[fips]
                for y, v in zip(YEARS, row):
                    tx[y] += v
    print(f"{out}: {len(c20)} counties. Texas: " + ", ".join(f"{y} {v / 1e6:.1f}M" for y, v in tx.items()))


if __name__ == "__main__":
    main()
