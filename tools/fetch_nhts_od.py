"""Today's long-distance travel by every mode: the FHWA / ORNL NextGen NHTS national
origin-destination passenger data for 2022 (annual person trips between NextGen zones, which are
metro areas and the rest of each state, by mode and purpose; built from location data and
calibrated to the NHTS).

    python tools/fetch_nhts_od.py

Writes data/flows/nhts_od_2022_texas.csv: every zone pair with a Texas end (origin or
destination), with annual trips in total and by mode (air, rail, vehicle, and atf: active
transportation and ferries) and purpose (work, non-work). Downloads the national file
(24 MB zipped) into data/raw/nhts/ the first time.
"""
import csv
import io
import os
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://nhts.ornl.gov/od/assets/data/2022_Passenger_OD_Annual.zip"
KEEP = ["origin_zone_id", "destination_zone_id", "origin_zone_name", "destination_zone_name",
        "origin_state", "destination_state", "annual_total_trips", "mode_air", "mode_rail",
        "mode_vehicle", "mode_atf", "purpose_work", "purpose_nonwork"]


def main():
    raw = os.path.join(ROOT, "data", "raw", "nhts")
    os.makedirs(raw, exist_ok=True)
    path = os.path.join(raw, URL.rsplit("/", 1)[1])
    if not os.path.exists(path):
        urllib.request.urlretrieve(URL, path)
    out = os.path.join(ROOT, "data", "flows", "nhts_od_2022_texas.csv")
    n = trips = 0
    with zipfile.ZipFile(path) as z, open(out, "w", newline="", encoding="utf-8") as f:
        name = next(x for x in z.namelist() if x.lower().endswith(".csv"))
        w = csv.writer(f, lineterminator="\n")
        w.writerow(KEEP)
        with z.open(name) as src:
            for r in csv.DictReader(io.TextIOWrapper(src, encoding="utf-8")):
                if "TX" not in (r["origin_state"], r["destination_state"]) or r["annual_total_trips"] in ("", "0"):
                    continue
                w.writerow([r[k] for k in KEEP])
                n += 1
                trips += int(float(r["annual_total_trips"]))
    print(f"{out}: {n:,} zone pairs with a Texas end, {trips / 1e9:.2f}B trips a year")


if __name__ == "__main__":
    main()
