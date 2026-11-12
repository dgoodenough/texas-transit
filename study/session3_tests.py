"""The third session's tests (study/third_session.md, the governor's answers marked "test").

    python study/session3_tests.py [--no-s416]

Each reruns the plan's schedules (study/timing.py) with one change and compares it with the plan as it stands:

  3   order        best ratio first against the optimized build order (timing.optimize_order), each valued as
                   planned and under the Auditor's stress (every project's cost x1.45 and riders x0.70): does
                   the optimized order's gain hold when the numbers come in worse?
  5   endowment    a share of each year's statewide budget banked from 2050 at 3% real, paying the operating gap
                   (operating cost less fares) as it grows: what it costs in value, what it covers
  6   land tax     every metro line's land-tax bonds halved (Finance: cities form the districts one at a time)
  7   pipeline     the whole map capped at 800 km of high-speed track under construction at once, with the
                   learning curve, against the whole map uncapped without it (central unit costs, no learning):
                   the learning counted only where the steady office that earns it exists
  11  growth       every metro's riders growing with Texas, not with its own counties' trend (riders follow
                   people): which lines depend on growth above the state's
  13  S416         San Antonio's Flores-Harry Wurzbach line (S416, over capacity as BRT) as metro on the same
                   alignment, valued on the full model in 2050 by the line planner's measure

PV: the present value in 2025 at 3% of the yearly net benefits 2025-2100 (timing.pv_net). Writes
study/session3_tests.md and study/session3_tests.json.
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "study"))
sys.path.insert(0, ROOT)
import session2_tests as s2  # noqa: E402
import timing  # noqa: E402

STRESS = timing.STRESS
B = lambda v: f"${v / 1e3:,.1f}B"  # noqa: E731


def stressed(projects):
    ps = copy.deepcopy(projects)
    for p in ps:
        p["capital"] *= STRESS["cost"]
        for k in ("benefit", "wider", "agglom", "fares", "trips_day", "trips_year", "flights_day"):
            if p.get(k):
                p[k] *= STRESS["riders"]
    return ps


def order_test(projects, budget, pop, dfw):
    """PV of best ratio first's order and the optimized one, as planned and under the stress."""
    order, base, best = timing.optimize_order(projects, budget, pop, dfw, log=None)
    out = {"planned": (base, best)}

    def value(ps, o):
        ps = copy.deepcopy(ps)
        for p in ps:
            timing.ratio(p)
            p["start"] = p["open"] = None   # a dependency later in the order counts as not open
        by = {p["id"]: p for p in ps}
        _, spend = timing.schedule(ps, budget, order=[by[i] for i in o if i in by])
        return timing.pv_net(ps, spend, pop, dfw)
    ps = stressed(projects)
    for p in ps:
        timing.ratio(p)
    greedy = [p["id"] for p in sorted(ps, key=lambda p: -p["bcr"])]
    out["stressed"] = (value(ps, greedy), value(ps, order))
    return out


def endowment_test(projects, budget, pop, dfw, share, key):
    """Bank `share` of the statewide budget each year from 2050; the rest builds. Returns the run, the share of
    the 2050-2100 operating gap the fund pays and its balance in 2100."""
    b2 = {y: v - (share * timing.STATE_MUSD if y >= 2050 else 0.0) for y, v in budget.items()}
    ps = copy.deepcopy(projects)
    fn = (lambda q: timing.schedule(q, b2)) if key == "ratio" else (lambda q: timing.whole_map(q, b2, pop))
    m = s2.run(ps, fn, pop, dfw)
    e = covered = gap_all = 0.0
    for r in m["rows"]:
        if r["year"] < 2050:
            continue
        e = e * 1.03 + share * timing.STATE_MUSD
        gap = max(r["opex"] - r["fares"], 0.0)
        d = min(e, gap)
        e -= d
        covered += d
        gap_all += gap
    return m, covered / gap_all if gap_all else 0.0, e


def growth_test(projects):
    """Every metro's riders at Texas's growth: trips scaled by the state's growth over the metro's, by year."""
    pop = timing.texas_pop()
    ps = copy.deepcopy(projects)
    changed = []
    for p in ps:
        if p["layer"] != "urban" or not p.get("traj"):
            continue
        m0, m50 = timing.metro_pop(p["metro"], 2020), timing.metro_pop(p["metro"], 2050)
        if not (m0 and m50):
            continue
        k50 = (pop[2050] / pop[2020]) / (m50 / m0)
        before = p["trips_day"]
        for k in ("trips_day", "trips_year", "benefit", "wider", "agglom", "fares"):
            if p.get(k):
                p[k] *= k50
        for y in list(p["traj"]):
            my = timing.metro_pop(p["metro"], y)
            if my:
                p["traj"][y] *= (pop[y] / pop[2050]) / (my / m50)
        changed.append((p, before, p["trips_day"]))
    return ps, changed


def s416_test():
    """S416 (San Antonio's G01) as metro on the same alignment: 2050 trips, capital, opex and the planner's J
    (trips - 2.5 x ($M capital + 20 x opex)) against it as BRT."""
    import urban_metros
    vendor = os.path.join(ROOT, "vendor", "dfw-transit")
    sys.path.insert(0, vendor)
    os.environ.setdefault("METRO_HOME", os.path.join(ROOT, "urban"))
    from metro import model, output, pages
    from dfwt import evaluate
    reg = {m["id"]: m for m in json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))["metros"]}
    folder = os.path.join(ROOT, "urban", "generated", "san-antonio")
    summ = json.load(open(os.path.join(folder, "summary.json"), encoding="utf-8"))
    m, cfg, ctx = pages.model_setup("san-antonio", summ["asc"], urban_metros.policies(reg["san-antonio"]), years=[2050])
    lid = next(r["line_id"] for r in output.inputs.read_csv(os.path.join(folder, "lines.csv")) if "(S416)" in r.get("notes", ""))
    out = {}
    with model.projection(m):
        for mode in ("brt", "metro"):
            t = pages.staged(folder, {})
            for k in ("line_stops.csv", "line_segments.csv"):
                for r in t[k]:
                    r["year_opens"] = "2026"
            for r in t["lines.csv"]:
                if r["line_id"] == lid:
                    r["mode"] = mode
                    r["headway_min"] = "6" if mode == "brt" else "8"
            net = output.load_net(t, cfg, mode)
            res = model.run_future(ctx, net, 2050, want_loads=True)
            ln = net.lines[lid]
            out[mode] = {"trips": res["daily_trips"], "capital": net.line_cost_musd(ln),
                         "opex": net.opex_musd(2050).get(lid, 0.0), "name": ln.name}
    b, mtr = out["brt"], out["metro"]
    d_trips, d_cap, d_opex = mtr["trips"] - b["trips"], mtr["capital"] - b["capital"], mtr["opex"] - b["opex"]
    floor = urban_metros.PLAN_FLOOR
    return {"line": lid, "name": b["name"], "brt": b, "metro": mtr,
            "dJ": d_trips - floor * (d_cap + 20 * d_opex), "per_musd": d_trips / max(d_cap + 20 * d_opex, 1e-9)}


def main():
    pop, projects, dfw, budget = s2.setup()
    wm = timing.whole_map_projects(projects, log=lambda *a: None)
    base = {"ratio": s2.run(copy.deepcopy(projects), lambda q: timing.schedule(q, budget), pop, dfw),
            "whole_map": s2.run(copy.deepcopy(wm), lambda q: timing.whole_map(q, budget, pop), pop, dfw)}
    res = {"base": {k: v["pv"] for k, v in base.items()}}
    L = ["# The third session's tests", "",
         "Generated by `python study/session3_tests.py`. The tests the governor set in `study/third_session.md`, each "
         "on the plan as it stands (its networks, its budget, the doubled station-area bonds and the Gulf spine in the "
         "program, both adopted in that session). PV: the present value in 2025 at 3% of the yearly net benefits "
         "2025-2100.", "",
         f"The plan: best ratio first {B(base['ratio']['pv'])}, the whole map {B(base['whole_map']['pv'])}.", ""]

    print("order ...")
    o = order_test(projects, budget, pop, dfw)
    res["order"] = o
    (pb, po), (sb, so) = o["planned"], o["stressed"]
    L += ["## Item 3: the optimized build order", "",
          "| | Best ratio first's order | Optimized order | Gain |", "|---|---|---|---|",
          f"| As planned | {B(pb)} | {B(po)} | {B(po - pb)} ({(po - pb) / pb:+.1%}) |",
          f"| Under the stress (cost x1.45, riders x0.70) | {B(sb)} | {B(so)} | {B(so - sb)} ({(so - sb) / abs(sb):+.1%}) |", "",
          ("**The gain holds under the stress**: the optimized order is better when the numbers come in worse too, "
           "so the governor's condition is met." if so > sb else
           "**The gain doesn't hold under the stress**: the optimized order is worse when the numbers come in worse, so "
           "the governor's condition isn't met and best ratio first stays."), ""]

    print("endowment ...")
    L += ["## Item 5: an operating endowment from 2050", "",
          "| Schedule | Banked from 2050 | PV | Change | Share of the 2050-2100 operating gap it pays | Fund in 2100 |",
          "|---|---|---|---|---|---|"]
    res["endowment"] = []
    for key in ("ratio", "whole_map"):
        for share in (0.05, 0.10):
            m, cov, e = endowment_test(wm if key == "whole_map" else projects, budget, pop, dfw, share, key)
            res["endowment"].append({"schedule": key, "share": share, "pv": m["pv"], "covered": cov, "fund_2100": e})
            L.append(f"| {dict(timing.SCENARIOS)[key]} | {share:.0%} of the budget (${share * timing.STATE_MUSD / 1e3:.2f}B a year) | "
                     f"{B(m['pv'])} | {B(m['pv'] - base[key]['pv'])} | {cov:.0%} | {B(e)} |")
    L.append("")

    print("land tax ...")
    ps = copy.deepcopy(projects)
    for p in ps:
        if p["layer"] == "urban":
            p["bond"] = 0.5 * p.get("bond", 0.0)
    m = s2.run(ps, lambda q: timing.schedule(q, budget), pop, dfw)
    res["land_tax_half"] = m["pv"]
    L += ["## Item 6: half the land-tax revenue", "",
          f"Every metro line's land-tax bonds halved: best ratio first {B(m['pv'])}, {B(m['pv'] - base['ratio']['pv'])} "
          f"against the plan; {B(m['spent'])} spent (the plan: {B(base['ratio']['spent'])}). "
          "The bonds change what the statewide budget has to pay, not any line's value, so the loss is the lines that "
          "open later or not at all.", ""]

    print("pipeline and learning ...")
    no_learn = timing.hsr_cost_ratio("central", False)
    wm_nl = copy.deepcopy(wm)
    for p in wm_nl:
        if p["id"] in no_learn:
            p["capital"] *= no_learn[p["id"]]
    a = s2.run(copy.deepcopy(wm_nl), lambda q: timing.whole_map(q, budget, pop), pop, dfw)
    timing.PIPELINE_KM = 800
    try:
        b = s2.run(copy.deepcopy(wm), lambda q: timing.whole_map(q, budget, pop), pop, dfw)
    finally:
        timing.PIPELINE_KM = None
    res["pipeline"] = {"uncapped_no_learning": a["pv"], "capped_learning": b["pv"]}
    L += ["## Item 7: the steady pipeline, with the learning only under it", "",
          "| The whole map | PV | Branches open (the last) | Most km building at once |", "|---|---|---|---|",
          f"| The plan: uncapped, with learning | {B(base['whole_map']['pv'])} | {base['whole_map']['branches']} "
          f"({base['whole_map']['last_branch'] or 'not all'}) | {base['whole_map']['peak_km_building']:,.0f} |",
          f"| Uncapped, no learning (no steady office) | {B(a['pv'])} | {a['branches']} ({a['last_branch'] or 'not all'}) | "
          f"{a['peak_km_building']:,.0f} |",
          f"| Capped at 800 km, with learning (the steady office) | {B(b['pv'])} | {b['branches']} ({b['last_branch'] or 'not all'}) | "
          f"{b['peak_km_building']:,.0f} |", "",
          (f"**The cap pays for itself** once the learning is credited only to the steady office: {B(b['pv'] - a['pv'])} "
           "more than the uncapped whole map without it." if b["pv"] > a["pv"] else
           f"**The cap doesn't pay for itself** even with the learning credited only to it: {B(b['pv'] - a['pv'])} against "
           "the uncapped whole map without learning."), ""]

    print("growth ...")
    ps, changed = growth_test(projects)
    m = s2.run(ps, lambda q: timing.schedule(q, budget), pop, dfw)
    res["growth"] = m["pv"]
    by_metro = {}
    for p, b0, b1 in changed:
        d = by_metro.setdefault(p["metro_name"], [0.0, 0.0, 0])
        d[0] += b0
        d[1] += b1
        d[2] += 1
    L += ["## Item 11: every metro at Texas's growth", "",
          f"Riders follow people, so each line's riders are scaled by Texas's growth over its metro's own trend: best "
          f"ratio first {B(m['pv'])}, {B(m['pv'] - base['ratio']['pv'])} against the plan; new daily metro trips in 2100 "
          f"{m['metro_2100'] / 1e6:.2f}M (the plan: {base['ratio']['metro_2100'] / 1e6:.2f}M).", "",
          "| Metro | Lines | 2050 riders, own trend | at Texas's growth | Change |", "|---|---|---|---|---|"]
    for name, (b0, b1, n) in sorted(by_metro.items(), key=lambda kv: (kv[1][1] - kv[1][0]) / max(kv[1][0], 1)):
        if abs(b1 - b0) > 1:
            L.append(f"| {name} | {n} | {b0:,.0f} | {b1:,.0f} | {(b1 - b0) / b0:+.0%} |")
    L.append("")

    if "--no-s416" not in sys.argv:
        print("S416 ...")
        s = s416_test()
        res["s416"] = s
        L += ["## Item 13: San Antonio's S416 as rail", "",
              f"{s['name']} (S416) as metro on its alignment, against BRT, on the full model in 2050 (every line open):", "",
              "| | Daily trips, the metro | Its capital | Its operating cost a year |", "|---|---|---|---|",
              f"| BRT (the plan) | {s['brt']['trips']:,.0f} | {B(s['brt']['capital'])} | ${s['brt']['opex']:,.0f}M |",
              f"| Metro | {s['metro']['trips']:,.0f} | {B(s['metro']['capital'])} | ${s['metro']['opex']:,.0f}M |", "",
              f"Metro adds {s['metro']['trips'] - s['brt']['trips']:,.0f} daily trips, {s['per_musd']:.2f} per $M of extra "
              f"capital and 20 years' operating: the line planner's J {s['dJ']:+,.0f}. "
              + ("**Upgrade it**: rail clears the plan's floor of 2.5." if s["dJ"] > 0 else
                 "**Keep it as BRT**: rail doesn't clear the plan's floor of 2.5; run it more often (two buses a "
                 "platform, or articulated vehicles) instead."), ""]
    with open(os.path.join(ROOT, "study", "session3_tests.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    json.dump(res, open(os.path.join(ROOT, "study", "session3_tests.json"), "w", encoding="utf-8"), indent=1, default=str)
    print("\n".join(L))


if __name__ == "__main__":
    main()
