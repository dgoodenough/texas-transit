"""How much Texans ride transit today, by metro: the targets the urban layer is calibrated to.

    python tools/fetch_transit_use.py

Writes:
  data/urban/ntd_2024_weekday_tx.csv   NTD 2024 average typical weekday boardings (unlinked trips)
                                       for every Texas agency and mode
  data/urban/acs_transit_share_cbsa.csv  ACS 2020-2024 5-year B08301: workers and public
                                       transportation commuters for every metro with a Texas county

Sources:
  NTD 2024 annual data, "Service (by Mode and Time Period)", data.transportation.gov dataset
  wwdp-t4re, time period "Average Typical Weekday". Rapid buses that NTD files as plain bus (MB:
  CapMetro's MetroRapid, VIA's Primo, Sun Metro's Brio) are in their agency's bus total; only
  Houston's Silver Line is filed as bus rapid transit (RB).
  ACS table B08301 (means of transportation to work), 5-year 2020-2024, Census table-based
  summary file (www2.census.gov, about 90 MB, cached in data/raw/). Public transportation
  excludes taxicab; the share is over all workers, including those who work from home (as
  DFW Transit's reports/FINDINGS.md).
"""
import csv
import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "urban")
NTD = "https://data.transportation.gov/resource/wwdp-t4re.json"
NTD_YEAR = "2024"
ACS = ("https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/"
       "acsdt5y2024-b08301.dat")


def ntd():
    q = {"$limit": "5000", "state": "TX", "report_year": NTD_YEAR, "time_period": "Average Typical Weekday",
         "$select": "_5_digit_ntd_id,agency,mode,mode_name,type_of_service,primary_uza_name,unlinked_passenger_trips_upt"}
    with urllib.request.urlopen(NTD + "?" + urllib.parse.urlencode(q), timeout=120) as r:
        rows = json.load(r)
    out = [{"ntd_id": r["_5_digit_ntd_id"], "agency": r["agency"], "mode": r["mode"], "mode_name": r["mode_name"],
            "type_of_service": r["type_of_service"], "uza": r["primary_uza_name"],
            "weekday_boardings": int(float(r["unlinked_passenger_trips_upt"]))}
           for r in rows if r.get("unlinked_passenger_trips_upt")]
    out.sort(key=lambda r: (r["uza"], r["agency"], r["mode"], r["type_of_service"]))
    write("ntd_2024_weekday_tx.csv", out)
    return out


def acs():
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, ACS.rsplit("/", 1)[1])
    if not os.path.exists(path):
        urllib.request.urlretrieve(ACS, path + ".part")
        os.replace(path + ".part", path)
    import sys
    sys.path.insert(0, os.path.join(ROOT, "vendor", "dfw-transit"))
    from metro import census
    rows = census.read_xlsx_rows(os.path.join(RAW, "list1_2023.xlsx"))
    hi = next(i for i, r in enumerate(rows) if r and "CBSA Code" in r)
    ix = {h: i for i, h in enumerate(rows[hi])}
    texas = {}
    for r in rows[hi + 1:]:
        try:
            st = f"{int(r[ix['FIPS State Code']]):02d}"
        except (ValueError, IndexError, TypeError):
            continue
        if st == "48" and r[ix["Metropolitan/Micropolitan Statistical Area"]].startswith("Metropolitan"):
            texas[r[ix["CBSA Code"]]] = r[ix["CBSA Title"]]
    out = []
    with open(path, encoding="utf-8") as f:
        head = f.readline().rstrip("\n").split("|")
        col = {h: i for i, h in enumerate(head)}
        for line in f:
            if not line.startswith("310M"):     # metro and micro areas: GEO_ID 310M...US<cbsa>
                continue
            v = line.rstrip("\n").split("|")
            cbsa = v[col["GEO_ID"]][-5:]
            if cbsa in texas:
                workers, transit = int(v[col["B08301_E001"]]), int(v[col["B08301_E010"]])
                out.append({"cbsa": cbsa, "name": texas[cbsa], "workers": workers, "transit": transit,
                            "transit_moe": v[col["B08301_M010"]], "transit_share": round(transit / workers, 5)})
    out.sort(key=lambda r: -r["workers"])
    write("acs_transit_share_cbsa.csv", out)
    return out


def write(name, rows):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote data/urban/{name}: {len(rows)} rows")


if __name__ == "__main__":
    ntd()
    for r in acs():
        print(f"  {r['name'][:40]:40s} {r['transit_share']:.2%} of {r['workers']:,} workers")
