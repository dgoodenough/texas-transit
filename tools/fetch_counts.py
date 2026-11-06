"""Today's intercity road traffic: TxDOT annual average daily traffic (AADT, both directions,
all vehicles) at a rural point midway along each intercity corridor, away from city traffic.

    python tools/fetch_counts.py

Writes data/flows/road_screenlines.csv. AADT counts every vehicle, trucks and local trips
included; it bounds the intercity car trips a corridor carries rather than measuring them.
Source: the TxDOT AADT layer (TxDOT open data, ArcGIS FeatureServer).
"""
import csv
import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYER = "https://services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services/TxDOT_AADT/FeatureServer/0/query"
# corridor, route as TxDOT names it, the place on the corridor, (lat, lon) near it
SCREENLINES = [
    ("Dallas-Houston", "IH0045", "Centerville", (31.258, -95.978)),
    ("Dallas-Austin", "IH0035", "West", (31.802, -97.093)),
    ("Austin-San Antonio", "IH0035", "between Kyle and San Marcos", (29.935, -97.905)),
    ("Houston-San Antonio", "IH0010", "Weimar", (29.700, -96.780)),
    ("Houston-Austin", "US0290", "Carmine", (30.142, -96.687)),
    ("Houston-Victoria / Corpus Christi / Rio Grande Valley", "US0059", "Wharton", (29.330, -96.120)),
    ("Dallas-Fort Worth to West Texas", "IH0020", "Cisco", (32.395, -98.975)),
    ("San Antonio-El Paso", "IH0010", "Ozona", (30.713, -101.200)),
    ("Dallas-Fort Worth to Oklahoma", "IH0035", "Gainesville", (33.700, -97.150)),
    ("Dallas-Fort Worth to Arkansas", "IH0030", "Mount Pleasant", (33.160, -94.975)),
    ("Dallas-Fort Worth to Shreveport", "IH0020", "Marshall", (32.530, -94.360)),
    ("Houston to Louisiana", "IH0010", "Orange", (30.095, -93.770)),
]


def query(route, lat, lon, metres):
    params = {"where": f"RTE_NM LIKE '{route}-%'", "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
              "inSR": 4326, "distance": metres, "units": "esriSRUnit_Meter",
              "spatialRel": "esriSpatialRelIntersects", "outFields": "RTE_NM,RDBD_TYPE,AADT_CUR,EXT_DATE",
              "returnGeometry": "false", "f": "json"}
    with urllib.request.urlopen(LAYER + "?" + urllib.parse.urlencode(params), timeout=120) as r:
        return [f["attributes"] for f in json.load(r).get("features", [])]


def main():
    out = os.path.join(ROOT, "data", "flows", "road_screenlines.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["corridor", "route", "place", "lat", "lon", "aadt", "segments", "counted"])
        for corridor, route, place, (lat, lon) in SCREENLINES:
            for metres in (1500, 4000, 10000):   # widen the search until the route turns up
                segs = [s for s in query(route, lat, lon, metres) if s["AADT_CUR"]]
                if segs:
                    break
            # the main roadbed (KG) carries the two-way total; a divided highway's left and right
            # roadbeds (LG, RG) repeat it, and frontage roads and ramps (AG, XG, ...) are left out.
            # Of the segments near the point, the busiest stands for the corridor.
            main = [s["AADT_CUR"] for s in segs if s["RDBD_TYPE"] == "KG"] or \
                   [s["AADT_CUR"] for s in segs if s["RDBD_TYPE"] in ("LG", "RG")]
            aadt = max(main, default="")
            when = sorted({s["EXT_DATE"] for s in segs if s["EXT_DATE"]})
            w.writerow([corridor, route, place, lat, lon, aadt, len(segs), when[-1] if when else ""])
            print(f"  {corridor:52s} {route} at {place:28s} {aadt if aadt != '' else 'not found':>8}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
