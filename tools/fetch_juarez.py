"""Ciudad Juárez on a grid, for the cross-border line (study/cross_border.py; study/second_session.md, item 19).

    python tools/fetch_juarez.py      -> data/urban/juarez_cells.csv

Neither the US census nor LODES covers Juárez, and INEGI's servers aren't reachable from here, so the
city is read from Overture Maps (the same public bucket as the metros' roads): building footprints
(their bounding-box area, a proxy for floor space where people live) and places (shops, offices,
services: where people go), in 500 m cells. A cell is on the Mexican side when most of its places carry
a Mexican address (Overture's addresses.country), which follows the Rio Grande more closely than the
state outline does. Population is the footprint area scaled to Juárez's 2020 census count (INEGI,
Censo de Población y Vivienda 2020: 1,512,450 in the municipio); study/cross_border.py does the scaling.
"""
import csv
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor", "dfw-transit"))
OUT = os.path.join(ROOT, "data", "urban", "juarez_cells.csv")
BBOX = (-106.60, 31.50, -106.25, 31.80)   # lon/lat: Juárez's urban area and El Paso across the river
CELL_KM = 0.5
LAT0 = 31.65
KX, KY = 111.32 * math.cos(math.radians(LAT0)), 110.57


def cell(lon, lat):
    return int((lon - BBOX[0]) * KX // CELL_KM), int((lat - BBOX[1]) * KY // CELL_KM)


def centre(i, j):
    return BBOX[1] + (j + 0.5) * CELL_KM / KY, BBOX[0] + (i + 0.5) * CELL_KM / KX


def main():
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    import pyarrow.fs as fs
    from metro import overture
    rel = overture.resolve_release()
    s3 = fs.S3FileSystem(anonymous=True, region=overture.REGION)
    xmin, ymin, xmax, ymax = BBOX
    f = ((pc.field("bbox", "xmin") < xmax) & (pc.field("bbox", "xmax") > xmin) &
         (pc.field("bbox", "ymin") < ymax) & (pc.field("bbox", "ymax") > ymin))
    cells = {}

    t0 = time.time()
    d = ds.dataset(f"{overture.BUCKET}/release/{rel}/theme=places/type=place/", filesystem=s3, format="parquet")
    tbl = d.to_table(columns=["bbox", "addresses"], filter=f)
    bb, ad = tbl.column("bbox").to_pylist(), tbl.column("addresses").to_pylist()
    for b, a in zip(bb, ad):
        c = cells.setdefault(cell(b["xmin"], b["ymin"]), {"m2": 0.0, "places": 0, "mx": 0, "us": 0})
        c["places"] += 1
        country = next((x.get("country") for x in (a or []) if x.get("country")), None)
        if country == "MX":
            c["mx"] += 1
        elif country == "US":
            c["us"] += 1
    print(f"  places: {len(bb):,} in {time.time() - t0:.0f}s")

    t0 = time.time()
    d = ds.dataset(f"{overture.BUCKET}/release/{rel}/theme=buildings/type=building/", filesystem=s3, format="parquet")
    n = 0
    for batch in d.to_batches(columns=["bbox"], filter=f, batch_size=200_000):
        for b in batch.column("bbox").to_pylist():
            w = (b["xmax"] - b["xmin"]) * KX * 1000
            h = (b["ymax"] - b["ymin"]) * KY * 1000
            c = cells.setdefault(cell((b["xmin"] + b["xmax"]) / 2, (b["ymin"] + b["ymax"]) / 2),
                                 {"m2": 0.0, "places": 0, "mx": 0, "us": 0})
            c["m2"] += w * h
            n += 1
    print(f"  buildings: {n:,} in {time.time() - t0:.0f}s")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["lat", "lon", "building_m2", "places", "places_mx", "places_us"])
        for (i, j), c in sorted(cells.items()):
            lat, lon = centre(i, j)
            wr.writerow([f"{lat:.5f}", f"{lon:.5f}", round(c["m2"]), c["places"], c["mx"], c["us"]])
    print(f"wrote {OUT}: {len(cells):,} cells, Overture release {rel}")


if __name__ == "__main__":
    main()
