"""Today's air travel to, from and within Texas: origin-destination passengers by city-pair
market, from the BTS / DOT Consumer Airfare Report, Table 6 (every contiguous-state city-pair
market averaging at least 10 passengers a day each way; the DB1B 10% ticket sample).

    python tools/fetch_air.py

Writes data/flows/air_city_pairs.csv: city1, city2, distance (miles), passengers a day (one
way, the report's measure), average fare, for every market with a Texas end, averaged over the
latest four quarters. Multi-airport cities are one market (Dallas/Fort Worth = DFW + Love Field;
Houston = IAH + Hobby).
"""
import collections
import csv
import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://data.transportation.gov/resource/yj5y-b2ir.json"


def get(params):
    with urllib.request.urlopen(URL + "?" + urllib.parse.urlencode(params), timeout=120) as r:
        return json.load(r)


def main():
    latest = get({"$select": "year, quarter", "$order": "year DESC, quarter DESC", "$limit": 1})[0]
    y, q = int(latest["year"]), int(latest["quarter"])
    quarters = []
    for _ in range(4):
        quarters.append((y, q))
        y, q = (y, q - 1) if q > 1 else (y - 1, 4)
    when = " OR ".join(f"(year={a} AND quarter={b})" for a, b in quarters)
    rows = get({"$where": f"(city1 like '%TX%' OR city2 like '%TX%') AND ({when})", "$limit": 50000})
    acc = collections.defaultdict(lambda: [0.0, 0.0, 0])
    miles = {}
    for r in rows:
        k = (r["city1"], r["city2"])
        p = float(r["passengers"])
        acc[k][0] += p
        acc[k][1] += p * float(r["fare"])
        acc[k][2] += 1
        miles[k] = int(r["nsmiles"])
    out = os.path.join(ROOT, "data", "flows", "air_city_pairs.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["city1", "city2", "miles", "passengers_per_day", "avg_fare", "quarters"])
        # a market missing from a quarter had under 10 passengers a day then: counted as 0
        for k, (p, pf, n) in sorted(acc.items(), key=lambda kv: -kv[1][0]):
            w.writerow([k[0], k[1], miles[k], round(p / 4, 1), round(pf / p, 2) if p else "", n])
    span = f"{quarters[-1][0]} Q{quarters[-1][1]} - {quarters[0][0]} Q{quarters[0][1]}"
    print(f"{out}: {len(acc)} markets with a Texas end, {span}")


if __name__ == "__main__":
    main()
