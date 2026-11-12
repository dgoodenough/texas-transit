"""Northbound border crossings at Texas's ports of entry, for the metros' trip tables
(study/second_session.md, item 18).

    python tools/fetch_border.py [YEAR]      -> data/urban/border_crossings.json

US Bureau of Transportation Statistics, Border Crossing Entry Data (CBP counts of inbound crossings,
data.bts.gov dataset keg4-3bc2): pedestrians, bus passengers and personal-vehicle passengers a day at
each Texas port, averaged over the year. The census and LODES count only people who live in the US,
so none of these people are in a metro's commutes; pedestrians and bus passengers, who have no car on
this side, are added to the zone at their bridge (vendor/dfw-transit metro/model.py, demand.border).
Each port is placed at the bridge most of its pedestrians use (approximate coordinates).
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "urban", "border_crossings.json")
URL = "https://data.bts.gov/resource/keg4-3bc2.json"
PORTS = {   # port code: (metro id, the bridge most pedestrians use, lat, lon)
    "2402": ("el-paso", "Paso del Norte bridge, downtown El Paso (El Paso port: also Stanton and the Bridge of the Americas)",
             31.7486, -106.4869),
    "2401": ("el-paso", "Zaragoza bridge, Ysleta", 31.6726, -106.3352),
    "2304": ("laredo", "Gateway to the Americas bridge, downtown Laredo", 27.5003, -99.5072),
    "2305": ("mcallen", "Hidalgo - Reynosa bridge", 26.0950, -98.2710),
    "2309": ("mcallen", "Progreso bridge", 26.0627, -97.9560),
    "2301": ("brownsville", "Gateway international bridge, downtown Brownsville", 25.8975, -97.4985),
    "2303": ("eagle-pass", "Eagle Pass bridge I, downtown", 28.7086, -100.5049),
}
MEASURES = ("Pedestrians", "Bus Passengers", "Personal Vehicle Passengers")


def fetch(year):
    q = {"$select": "port_code,port_name,measure,sum(value)",
         "$where": f"state='Texas' AND date between '{year}-01-01T00:00:00' and '{year}-12-31T23:59:59' AND measure in ("
                   + ",".join(f"'{m}'" for m in MEASURES) + ")",
         "$group": "port_code,port_name,measure", "$limit": "1000"}
    with urllib.request.urlopen(URL + "?" + urllib.parse.urlencode(q), timeout=120) as r:
        return json.load(r)


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2024
    rows = fetch(year)
    ports = {}
    for r in rows:
        code = r["port_code"]
        if code not in PORTS:
            continue
        metro, bridge, lat, lon = PORTS[code]
        p = ports.setdefault(code, {"port_code": code, "port": r["port_name"], "metro": metro, "bridge": bridge,
                                    "lat": lat, "lon": lon})
        p[r["measure"].lower().replace(" ", "_") + "_day"] = round(float(r["sum_value"]) / (366 if year % 4 == 0 else 365))
    out = {"source": f"US Bureau of Transportation Statistics, Border Crossing Entry Data (data.bts.gov keg4-3bc2), {year}, "
                     "inbound crossings a day at each port, averaged over the year",
           "year": year, "ports": sorted(ports.values(), key=lambda p: p["port_code"])}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    for p in out["ports"]:
        print(f"{p['port']:12} {p['metro']:12} pedestrians {p.get('pedestrians_day', 0):6,} bus {p.get('bus_passengers_day', 0):5,} "
              f"vehicle passengers {p.get('personal_vehicle_passengers_day', 0):6,}")


if __name__ == "__main__":
    main()
