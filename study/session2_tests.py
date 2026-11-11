"""The second session's tests (study/second_session.md, the governor's answers marked "test").

    python study/session2_tests.py

Each test reruns the plan's schedules (study/timing.py) with one change and compares it with the plan as it
stands, on the same networks and the same budget:

  13/16 hybrid      each metro is guaranteed half its stream (metro_stream); everything else, the metros'
                    remaining lines and the intercity projects, in one queue best ratio first
  6     pipeline    the whole map with a cap on high-speed km under construction at once (timing.PIPELINE_KM):
                    does a steady pipeline cost the branches time, and how many idle years does it remove
  5     endowment   the whole map's never-spent money banked from the year building stops, earning 3% real,
                    paying the operating gap (operating cost less fares); what it covers
  20    gulf spine  Houston - Victoria - Corpus Christi in the Connectivity Program as higher-speed rail first
                    (standard S4), so the Valley's trunk doesn't wait in the statewide queue
  26    land tax    station-district bonds doubled in the metros growing faster than Texas
  23    stations    a frequent link (BRT-lite, $40M, $4M a year to run) from every high-speed station in Texas
                    no metro station reaches within 1.5 km, charged to the branch it opens with

PV: the present value in 2025 at 3% of the yearly net benefits 2025-2100 (timing.pv_net). Writes
study/session2_tests.md and study/session2_tests.json.
"""
import copy
import csv
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "study"))
sys.path.insert(0, ROOT)
import timing  # noqa: E402
from texas import finance, hsr  # noqa: E402

LINK_CAPITAL, LINK_OPEX, LINK_KM = 40.0, 4.0, 1.5


def setup():
    pop = timing.texas_pop()
    projects = (timing.urban_projects() + timing.with_trajectories(timing.hsr_projects)
                + timing.with_trajectories(timing.conventional_projects))
    dfw, _, _ = timing.dfw_layer()
    budget = timing.other_budget(dfw)
    return pop, projects, dfw, budget


def run(ps, fn, pop, dfw):
    built, spend = timing.settle(ps, fn)
    rows = timing.yearly(ps, spend, pop, dfw)
    return metrics(ps, rows, spend, pop, dfw)


BRANCHES = list(finance.CONNECTIVITY)   # the plan's seven, whatever a test adds to the program


def metrics(ps, rows, spend, pop, dfw):
    r50 = next(r for r in rows if r["year"] == 2050)
    opened = {p["id"]: p for p in ps if p.get("open")}
    conn = [i for i in BRANCHES if i in opened]
    hs = [p for p in opened.values() if p["layer"] == "hsr"]
    busy = {y: sum(p["km"] for p in hs if p["start"] <= y < p["open"]) for y in timing.YEARS}
    first = min((p["start"] for p in hs), default=None)
    last = max((p["open"] for p in hs), default=None)
    return {"pv": timing.pv_net(ps, spend, pop, dfw),
            "metro_2050": r50["urban_trips_day"] + r50["dfw_trips_day"],
            "metro_2100": rows[-1]["urban_trips_day"] + rows[-1]["dfw_trips_day"],
            "intercity_2100": rows[-1]["intercity_trips_year"],
            "branches": len(conn), "last_branch": max((opened[i]["open"] for i in conn), default=None)
            if len(conn) == len(BRANCHES) else None,
            "branch_years": {i: opened[i]["open"] for i in conn},
            "spent": sum(r["spend"] + r["dfw_spend"] for r in rows),
            "idle_years": sum(1 for y in range(first, last) if busy[y] == 0) if first else None,
            "peak_km_building": max(busy.values()) if busy else 0.0,
            "rows": rows, "projects": ps, "spend": spend}


def hybrid(projects, budget, pop, share=0.5):
    """Each metro guaranteed `share` of its stream, its lines in the generator's order; then everything
    not built, in one queue best ratio first, against the same statewide budget."""
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))
    spend = {y: 0.0 for y in timing.YEARS}
    built = []
    for p in projects:
        p["start"] = p["open"] = None
    for m in reg["metros"]:
        ps = [p for p in projects if p.get("metro") == m["id"]]
        if not ps:
            continue
        n = len(timing.YEARS) if m.get("buildout") or m.get("policies") else timing.METRO_YEARS
        stream = {y: v * share for y, v in timing.metro_stream(m, n, pop).items()}
        b, s_m = timing.schedule(ps, stream, order=ps)
        built += b
        for y in timing.YEARS:
            spend[y] += s_m[y]
    rest = [p for p in projects if p["layer"] != "urban" or not p.get("open")]   # settle() reruns this: intercity again
    b, spend = timing.schedule(rest, budget, spend=spend)
    for p in projects:
        timing.ratio(p)
    return built + b, spend


def endowment(m, rate=0.03):
    """From the year the schedule stops building: the money it never spends banked at `rate`, paying
    the operating gap each year it can. Returns (from year, share of the gap 2025-2100 it covers, share
    of the gap in its years it covers, endowment in 2100, the share of 2100's gap 3.5% of it pays forever)."""
    rows = m["rows"]
    last = max((r["year"] for r in rows if r["spend"] + r["dfw_spend"] > 1.0), default=timing.YEARS[-1])
    e = sum(timing.STATE_MUSD - r["spend"] - r["dfw_spend"] for r in rows if r["year"] <= last)
    covered = gap_after = 0.0
    for r in rows:
        if r["year"] <= last:
            continue
        e = e * (1 + rate) + timing.STATE_MUSD - r["spend"] - r["dfw_spend"]
        gap = max(r["opex"] - r["fares"], 0.0)
        draw = min(e, gap)
        e -= draw
        covered += draw
        gap_after += gap
    gap_all = sum(max(r["opex"] - r["fares"], 0.0) for r in rows)
    g2100 = max(rows[-1]["opex"] - rows[-1]["fares"], 1e-9)
    return last + 1, covered / gap_all if gap_all else 0.0, covered / gap_after if gap_after else 0.0, e, \
        e * 0.035 / g2100


def station_links(projects):
    """{high-speed corridor id: [stations in Texas no metro station reaches within LINK_KM]}, each station
    charged once, to the first corridor (in the whole map's order of opening) that serves it."""
    pts = []
    for d in os.listdir(timing.URBAN_GENERATED):
        f = os.path.join(timing.URBAN_GENERATED, d, "stations.csv")
        if os.path.exists(f):
            pts += [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open(f, encoding="utf-8"))]
    for f in (os.path.join(ROOT, "vendor", "dfw-transit", "network", "stations.csv"),   # DFW's plan, its own network
              os.path.join(ROOT, "vendor", "dfw-transit", "scenarios", "two_million", "extra", "stations.csv")):
        if os.path.exists(f):
            pts += [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open(f, encoding="utf-8"))]

    def reached(la, lo):
        return any(abs(la - a) < 0.03 and abs(lo - b) < 0.03 and
                   math.hypot((la - a) * 110.57, (lo - b) * 111.32 * math.cos(math.radians(la))) <= LINK_KM for a, b in pts)
    seen, out = set(), {}
    for p in sorted((p for p in projects if p["layer"] == "hsr" and p.get("open")), key=lambda p: p["open"]):
        cid = p["id"].split(":")[1]
        for st in hsr.CORRIDORS[cid][1]:
            la, lo = hsr.point(st)
            if st in seen or not finance.in_texas(la, lo):
                continue
            seen.add(st)
            if not reached(la, lo):
                out.setdefault(p["id"], []).append(st)
    return out


def main():
    pop, projects, dfw, budget = setup()
    wm = timing.whole_map_projects(projects, log=lambda *a: None)
    base = {
        "ratio": run(copy.deepcopy(projects), lambda q: timing.schedule(q, budget), pop, dfw),
        "metros_first": run(copy.deepcopy(projects), lambda q: timing.metros_first(q, budget, pop), pop, dfw),
        "whole_map": run(copy.deepcopy(wm), lambda q: timing.whole_map(q, budget, pop), pop, dfw)}
    tests = []

    print("hybrid ...")
    m = run(copy.deepcopy(projects), lambda q: hybrid(q, budget, pop), pop, dfw)
    tests.append(("13/16", "Each metro guaranteed half its stream, the rest one queue", "ratio", m, ""))

    for cap in (800, 500):
        print(f"pipeline {cap} ...")
        timing.PIPELINE_KM = cap
        try:
            m = run(copy.deepcopy(wm), lambda q: timing.whole_map(q, budget, pop), pop, dfw)
        finally:
            timing.PIPELINE_KM = None
        tests.append(("6", f"At most {cap} km of high-speed track under construction at once", "whole_map", m,
                      f"{m['idle_years']} idle years between the first start and the last opening "
                      f"(the plan: {base['whole_map']['idle_years']}); at most {m['peak_km_building']:,.0f} km at once "
                      f"(the plan: {base['whole_map']['peak_km_building']:,.0f})"))

    print("endowment ...")
    frm, share_all, share_after, e2100, forever = endowment(base["whole_map"])
    tests.append(("5", "The whole map's never-spent money as an operating endowment", "whole_map", base["whole_map"],
                  f"from {frm}, when building stops: it pays {share_after:.0%} of the operating gap from then to 2100 "
                  f"({share_all:.0%} of the gap 2025-2100) and leaves ${e2100 / 1e3:,.0f}B in 2100, whose 3.5% a year "
                  f"pays {forever:.0%} of 2100's gap for good"))

    print("gulf spine ...")
    saved_c, saved_s = list(finance.CONNECTIVITY), dict(timing.WHOLE_MAP_HSR["standards"])
    try:
        finance.CONNECTIVITY.append("hsr:CC")
        timing.WHOLE_MAP_HSR["standards"]["CC"] = "S4"
        wm2 = timing.whole_map_projects(projects, log=lambda *a: None)
        m = run(wm2, lambda q: timing.whole_map(q, budget, pop), pop, dfw)
        cc = next(p for p in m["projects"] if p["id"] == "hsr:CC")
        m["note_cc"] = cc.get("open")
    finally:
        finance.CONNECTIVITY[:] = saved_c
        timing.WHOLE_MAP_HSR["standards"].clear()
        timing.WHOLE_MAP_HSR["standards"].update(saved_s)
    b_cc = next((p.get("open") for p in base["whole_map"]["projects"] if p["id"] == "hsr:CC"), None)
    tests.append(("20", "Houston - Corpus Christi in the program as higher-speed rail first", "whole_map", m,
                  f"Corpus Christi opens {m['note_cc']} (the plan: {b_cc}); the Valley {m['branch_years'].get('hsr:VALLEY')} "
                  f"(the plan: {base['whole_map']['branch_years'].get('hsr:VALLEY')}), McAllen "
                  f"{m['branch_years'].get('hsr:MFE')} (the plan: {base['whole_map']['branch_years'].get('hsr:MFE')})"))

    print("land tax ...")
    ps = copy.deepcopy(projects)
    fast = set()
    for p in ps:
        if p["layer"] == "urban":
            g = (timing.metro_pop(p["metro"], 2100) or 0) / max(timing.metro_pop(p["metro"], 2020) or 1, 1)
            if g > pop[2100] / pop[2020]:
                p["bond"] = min(2 * p.get("bond", 0.0), p["capital"])
                fast.add(p["metro_name"])
    m = run(ps, lambda q: timing.schedule(q, budget), pop, dfw)
    tests.append(("26", "Station-district bonds doubled where the metro outgrows Texas", "ratio", m,
                  "in " + ", ".join(sorted(fast))))

    print("station links ...")
    links = station_links(base["whole_map"]["projects"])
    wm3 = copy.deepcopy(wm)
    for p in wm3:
        n = len(links.get(p["id"], []))
        if n:
            p["capital"] += n * LINK_CAPITAL
            p["opex"] += n * LINK_OPEX
    m = run(wm3, lambda q: timing.whole_map(q, budget, pop), pop, dfw)
    names = sorted(s for v in links.values() for s in v)
    tests.append(("23", "A frequent link from every high-speed station no metro station reaches", "whole_map", m,
                  f"{len(names)} stations ({', '.join(names)}): ${len(names) * LINK_CAPITAL / 1e3:,.2f}B and "
                  f"${len(names) * LINK_OPEX:,.0f}M a year; riders not counted (the intercity model already assumes "
                  "a way to the station)"))
    write(base, tests)


def write(base, tests):
    B = lambda v: f"${v / 1e3:,.1f}B"  # noqa: E731
    label = {"ratio": "best ratio first", "metros_first": "metros first", "whole_map": "the whole map"}
    L = ["# The second session's tests", "",
         "Generated by `python study/session2_tests.py`. Each test reruns one of the plan's schedules (`study/timing.py`) "
         "with one change from the governor's answers in `study/second_session.md` and compares it with the plan as it "
         "stands, on the same networks and budget. PV: the present value in 2025 at 3% of the yearly net benefits, "
         "2025-2100.", "",
         "| Item | Test | Against | PV | Change in PV | New daily metro trips 2050 / 2100 | Branches open (the last) | Spent | What else |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k in ("ratio", "metros_first", "whole_map"):
        b = base[k]
        L.append(f"| | The plan: {label[k]} | | {B(b['pv'])} | | {b['metro_2050'] / 1e6:.2f}M / {b['metro_2100'] / 1e6:.2f}M | "
                 f"{b['branches']} of 7 ({b['last_branch'] or 'not all'}) | {B(b['spent'])} | |")
    for item, name, k, m, note in tests:
        b = base[k]
        L.append(f"| {item} | {name} | {label[k]} | {B(m['pv'])} | {B(m['pv'] - b['pv'])} | "
                 f"{m['metro_2050'] / 1e6:.2f}M / {m['metro_2100'] / 1e6:.2f}M | {m['branches']} of 7 "
                 f"({m['last_branch'] or 'not all'}) | {B(m['spent'])} | {note} |")
    L.append("")
    with open(os.path.join(ROOT, "study", "session2_tests.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    json.dump({"base": {k: {kk: v for kk, v in b.items() if kk not in ("rows", "projects", "spend")} for k, b in base.items()},
               "tests": [{"item": i, "test": n, "against": k, "result": {kk: v for kk, v in m.items()
                                                                       if kk not in ("rows", "projects", "spend")}, "note": nt}
                         for i, n, k, m, nt in tests]},
              open(os.path.join(ROOT, "study", "session2_tests.json"), "w", encoding="utf-8"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main()
