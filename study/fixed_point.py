"""Is the metro floor circular? (study/second_session.md, item 1: the Auditor's dissent)

    python study/urban_metros.py generate --sweep 1,1.75,4 --sweep-dir DIR     (hours: Houston)
    python study/fixed_point.py DIR

The line planner keeps a change to a metro's network only if it carries PLAN_FLOOR new daily trips per $M
(study/urban_metros.py). That floor was set from the ratio at which the statewide queue ran out of money, and the
queue runs out where it does because of what the metros spend. So the floor is a choice, and this tests it: for
each floor swept (DIR/<floor>/<metro>/, plus urban/generated/ at the plan's own floor) it runs the three schedules
of study/timing.py on those networks and reports what the whole plan buys:

  pv        present value in 2025 at 3% of the yearly net benefits, 2025-2100 (timing.pv_net): travellers' gain,
            wider benefits, fares less operating cost, of everything open, for the same budget
  the queue's margin under best ratio first: the ratio of the best project it can't reach by 2100, the lowest
            ratio it funds, and the floor each implies through k, the ratio a trip a day per $M is worth here

A floor is consistent (a fixed point) when the floor it implies is the floor it was run at; the floor the plan
should use is the one that buys the most. Writes study/fixed_point.md and study/fixed_point.json.
"""
import copy
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "study"))
import timing  # noqa: E402
import urban_metros  # noqa: E402

SCEN = ("ratio", "metros_first", "whole_map")


def networks(sweep_dir, floor):
    """A folder of every metro's network at `floor`: DIR/<floor>/<id> where the sweep wrote one, else the
    plan's own (a metro with no lines has none in the sweep, and is the same at any floor)."""
    tmp = tempfile.mkdtemp(prefix=f"floor_{floor:g}_")
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))
    for m in reg["metros"]:
        src = os.path.join(sweep_dir, f"{floor:g}", m["id"]) if sweep_dir else None
        if not src or not os.path.exists(os.path.join(src, "summary.json")):
            src = os.path.join(ROOT, "urban", "generated", m["id"])
        os.symlink(src, os.path.join(tmp, m["id"]))
    return tmp


def run(floor, folder):
    timing.URBAN_GENERATED = folder
    pop = timing.texas_pop()
    projects = (timing.urban_projects() + timing.with_trajectories(timing.hsr_projects)
                + timing.with_trajectories(timing.conventional_projects))
    dfw, _, _ = timing.dfw_layer()
    budget = timing.other_budget(dfw)
    wm = timing.whole_map_projects(projects, log=lambda *a: None)
    total = timing.STATE_MUSD * len(timing.YEARS)
    out = {"floor": floor}
    urban = [p for p in projects if p["layer"] == "urban"]
    out["metro_lines"] = len(urban)
    out["metro_capital"] = sum(p["capital"] for p in urban)
    for key in SCEN:
        ps = copy.deepcopy(wm if key == "whole_map" else projects)
        fn = {"ratio": lambda q: timing.schedule(q, budget), "metros_first": lambda q: timing.metros_first(q, budget),
              "whole_map": lambda q: timing.whole_map(q, budget, pop)}[key]
        built, spend = timing.settle(ps, fn)
        rows = timing.yearly(ps, spend, pop, dfw)
        r50 = next(r for r in rows if r["year"] == 2050)
        opened = {p["id"]: p for p in ps if p.get("open")}
        spent = sum(r["spend"] + r["dfw_spend"] for r in rows)
        s = {"pv": timing.pv_net(ps, spend, pop, dfw),
             "metro_2050": r50["urban_trips_day"] + r50["dfw_trips_day"],
             "metro_2100": rows[-1]["urban_trips_day"] + rows[-1]["dfw_trips_day"],
             "intercity_2100": rows[-1]["intercity_trips_year"],
             "net_2100": rows[-1]["benefit"] + rows[-1]["wider"] + rows[-1]["fares"] - rows[-1]["opex"],
             "gap_2100": rows[-1]["opex"] - rows[-1]["fares"],
             "spent": spent, "unspent": total - spent,
             "metro_built": sum(1 for p in opened.values() if p["layer"] == "urban"),
             "hsr_built": sum(1 for p in opened.values() if p["layer"] == "hsr"),
             "branches": sum(1 for i in opened if i in timing.finance.CONNECTIVITY)}
        if key == "ratio":
            ks = sorted(p["bcr"] / (p["trips_day"] / (p["capital"] + 20 * p["opex"]))
                        for p in ps if p["layer"] == "urban" and p["trips_day"] > 0)
            out["k"] = ks[len(ks) // 2] if ks else None
            unb = [p for p in ps if not p.get("open") and all(d in opened for d in p["after"])]
            best = max(unb, key=lambda p: p["bcr"], default=None)
            low = min((p for p in opened.values()), key=lambda p: p["bcr"])
            s["margin_best_unbuilt"] = (best["id"], best["bcr"]) if best else None
            s["margin_lowest_funded"] = (low["id"], low["bcr"])
        out[key] = s
    return out


def main():
    sweep_dir = sys.argv[1] if len(sys.argv) > 1 else None
    floors = sorted({float(f) for f in os.listdir(sweep_dir)} if sweep_dir else set())
    plan_floor = urban_metros.PLAN_FLOOR
    res = []
    for f in sorted(set(floors) | {plan_floor}):
        folder = networks(sweep_dir if f != plan_floor else None, f)
        try:
            print(f"floor {f:g} ...")
            res.append(run(f, folder))
        finally:
            shutil.rmtree(folder)
    json.dump(res, open(os.path.join(ROOT, "study", "fixed_point.json"), "w", encoding="utf-8"), indent=1)
    write(res, plan_floor)


def write(res, plan_floor):
    B = lambda v: f"${v / 1e3:,.1f}B"  # noqa: E731
    L = ["# Is the metro floor circular?", "",
         "Generated by `python study/fixed_point.py` (the networks: `python study/urban_metros.py generate --sweep ...`). "
         "The Auditor's dissent in `study/second_session.md` (item 1): the line planner's floor, the new daily trips per $M "
         "a change to a metro's network must carry, was set from the ratio where the statewide queue ran out of money, "
         "and the queue runs out where it does because of what the metros spend. Here each metro's network is planned at "
         "several floors from the same pruned network, and the plan is scheduled on each. PV: the present value in 2025 "
         "at 3% of the plan's yearly net benefits, 2025-2100 (travellers' gain, wider benefits and fares less operating "
         f"cost, `study/timing.py` pv_net), for the same budget. The plan's floor today: {plan_floor:g}.", ""]
    L += ["| Floor (trips a day per $M) | Metro lines | Metro capital | " + " | ".join(
              f"PV, {n}" for n in ("best ratio first", "metros first", "the whole map")) +
          " | Metro trips 2050 / 2100 (best ratio first) | Unspent (best ratio first / whole map) | High-speed, branches (best ratio first) | Operating gap 2100 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in res:
        a, w = r["ratio"], r["whole_map"]
        L.append(f"| {r['floor']:g}{' (the plan)' if r['floor'] == plan_floor else ''} | {r['metro_lines']} | {B(r['metro_capital'])} | "
                 + " | ".join(B(r[k]['pv']) for k in SCEN)
                 + f" | {a['metro_2050'] / 1e6:.2f}M / {a['metro_2100'] / 1e6:.2f}M | {B(a['unspent'])} / {B(w['unspent'])} | "
                 f"{a['hsr_built']} of 16, {a['branches']} of 7 | {B(a['gap_2100'])} |")
    best = {k: max(res, key=lambda r: r[k]["pv"]) for k in SCEN}
    L += ["", "**The queue's margin** under best ratio first, and the floor it implies (the ratio over k, the ratio a "
          "trip a day per $M is worth in this plan's valuation, the median over the metro lines):", "",
          "| Floor | k | Best project not reached by 2100 | Floor it implies | Lowest ratio funded | Floor it implies |",
          "|---|---|---|---|---|---|"]
    for r in res:
        a, k = r["ratio"], r["k"]
        bu, lf = a.get("margin_best_unbuilt"), a.get("margin_lowest_funded")
        L.append(f"| {r['floor']:g} | {k:.3f} | " + (f"{bu[0]} ({bu[1]:.2f}) | {bu[1] / k:.1f}" if bu else "everything reachable | ")
                 + f" | {lf[0]} ({lf[1]:.2f}) | {lf[1] / k:.1f} |")
    L += ["", "**What it says.** "
          + "; ".join(f"{n}: the floor that buys the most is {best[k]['floor']:g} ({B(best[k][k]['pv'])})"
                      for k, n in zip(SCEN, ("best ratio first", "metros first", "the whole map"))) + ".", ""]
    with open(os.path.join(ROOT, "study", "fixed_point.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
