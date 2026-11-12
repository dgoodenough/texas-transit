"""Editable tables for every generated metro (study/site_parity.md, phase 5).

    python tools/metro_tables.py [ids]     -> urban/generated/<id>/stages.csv, service.csv, validation.md

DFW Transit's `python -m metro tables` on each metro with lines, the opening years taken from the plan's main
schedule (best ratio first, docs/data/timeline.json). The tables are first drafts for a metro's planners to
edit, as DFW's network/ was edited; rows edited by hand survive a rerun. validation.md is dfwt's validator on
the result (spacing, curves, hairpins, gaps, islands, stages).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("METRO_HOME", os.path.join(ROOT, "urban"))
import build_metro_pages as bmp  # noqa: E402


def main(ids):
    sys.path.insert(0, bmp.VENDOR)
    from metro import tables
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))["metros"]
    for m in reg:
        if ids and m["id"] not in ids:
            continue
        if not os.path.exists(os.path.join(ROOT, "urban", "generated", m["id"], "lines.csv")):
            continue
        years = bmp.schedules(m["id"])["ratio"]
        tables.write(m["id"], years)


if __name__ == "__main__":
    main(sys.argv[1:])
