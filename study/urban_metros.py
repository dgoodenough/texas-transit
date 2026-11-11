"""The urban layer: a generated rail and BRT network for each Texas metro other than DFW, each
calibrated to its own transit use, at DFW Transit's spending rate per resident.

    python tools/build_metro_registry.py          # urban/metros.json
    (METRO_HOME=urban python -m metro fetch <id>, from vendor/dfw-transit, for every metro)
    python study/urban_metros.py calibrate        # the ridership constant for every metro
    python study/urban_metros.py generate [ids]   # urban/generated/<id>/ (DFW Transit's generator)
    python study/urban_metros.py summary          # study/urban_metros.md, study/urban_metros.csv

The ridership constant. DFW Transit's demand model has one constant for how much people like
transit beyond its times and costs, fitted to DFW's rail boardings. Here:

1. Houston, the one other Texas metro with a rail system NTD counts separately, is fitted so
   today's lines carry their riders (NTD 2024 average weekday, light rail + BRT; local buses
   are the model's feeder grid, as in DFW).
2. Houston's fit against its ACS transit share of commuters gives the slope k of constant on
   log transit share through DFW: asc = asc_DFW + k x ln(share / share_DFW).
3. Every other metro gets that line at its own ACS share. Austin's Red Line is a check, not a
   fit (CHECK below); El Paso's streetcar is missing from its GTFS feed. Shares below 0.1% (Eagle Pass: no
   sampled transit commuters) count as 0.1%.
"""
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, "vendor", "dfw-transit")
HOME = os.path.join(ROOT, "urban")
REGISTRY = os.path.join(HOME, "metros.json")
os.environ["METRO_HOME"] = HOME
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
sys.path.insert(0, VENDOR)
import csv  # noqa: E402

from dfwt import config  # noqa: E402

FUTURE = (2050, 2100)   # model years with every line open, the metro's own growth and the land-use package
# The line planner's exchange rate (vendor/dfw-transit/metro/lineplan.py): a change to a metro's network must
# carry this many new daily trips per $M of capital + 20 years' operating cost. In this plan's valuation
# (study/timing.py) a line's ratio is about 0.15 x its trips per $M, so 2.5 is a ratio of about 0.37: the ratio
# of the last projects the statewide queue reaches. At the generator's own floor (1, a ratio of about 0.15) the
# planner bought riders, mostly with frequency, that the statewide queue then wouldn't fund.
PLAN_FLOOR = 2.5
# The 2 million plan's station-area land use (DFW Transit scenarios/two_million/config.json growth): stronger
# development near new stations, today's stations upzoned from 2030, and a fifth of growth steered to station
# areas. It changes nothing on today's land use (the ramps start after 2025).
with open(os.path.join(VENDOR, "scenarios", "two_million", "config.json"), encoding="utf-8") as _f:
    LAND_USE = {"growth": json.load(_f)["growth"]}


def policies(m):
    """The package a metro's run gets: the land use everywhere, and for the registry's policy metros (`policies`:
    Houston, Austin, San Antonio, El Paso) the 2 million plan's access and parking policies at their mature
    settings, in force from the model's first year (study/metro_potential.py LEVERS): feeder buses every 15
    minutes, bikes and scooters and drop-off to stations, walks up to 1.6 km on straighter paths, no park & ride
    under 1.6 km, and $5 a day parking where jobs reach 15,000 per km2. The generator applies it on top of the
    constant fitted to today's riders (vendor/dfw-transit metro/generate.py), and chooses lines with it on."""
    import copy
    pk = copy.deepcopy(LAND_USE)
    if m.get("policies"):
        sys.path.insert(0, os.path.join(ROOT, "study"))
        import metro_potential
        config.merge(pk, copy.deepcopy(metro_potential.LEVERS))
    return pk

FLOOR_SHARE = 0.001
# NTD 2024 rows (ntd id, mode) that are today's lines in the model, by metro. Checked against
# each metro's existing/lines.csv (study/urban_metros.md lists the lines).
CALIBRATE = {   # fitted: the constant is set so today's lines carry these riders
    "houston": [("60008", "LR"), ("60008", "RB")],   # METRORail Red, Green, Purple; Silver Line BRT
}
CHECK = {       # not fitted, compared: the model on today's lines at the slope's constant
    # One train every 30-60 minutes: fitting the constant to it (-2.05 as commuter rail) would say
    # Austinites like transit far less than Dallasites, against ACS (1.06% vs 0.67%). It says the
    # model overrates infrequent rail, which DFW's calibration (mostly frequent light rail) can't see.
    "austin": [("60048", "YR")],                     # CapMetro Rail Red Line
    # El Paso's streetcar (NTD SR, 676 a weekday) is not in the Mobility Database's Sun Metro feed,
    # so the model has no line to compare it with.
}


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def save_registry(reg):
    with open(REGISTRY, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1)
        f.write("\n")


def shares():
    return {r["cbsa"]: float(r["transit_share"]) for r in read_csv(os.path.join(ROOT, "data", "urban",
                                                                                "acs_transit_share_cbsa.csv"))}


# Corrections to step 1's GTFS reading: (metro, line_id, mode, why). Re-applied on every run, since a
# new fetch rewrites existing/.
MODE_FIXES = [
    ("austin", "m150_550", "commuter", "CapMetro files its Red Line, a diesel commuter train with park & ride, as GTFS "
                                      "route_type 0 (tram), which step 1 reads as metro"),
]


def fix_inputs():
    for mid, lid, mode, why in MODE_FIXES:
        p = os.path.join(HOME, "data", "metros", mid, "existing", "lines.csv")
        rows = read_csv(p)
        hit = [r for r in rows if r["line_id"] == lid]
        if not hit:
            raise SystemExit(f"{mid}: line {lid} is not in existing/lines.csv ({why})")
        for r in hit:
            r["mode"] = mode
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)


def calibrate():
    from metro import generate
    fix_inputs()
    ntd = {(r["ntd_id"], r["mode"]): int(r["weekday_boardings"])
           for r in read_csv(os.path.join(ROOT, "data", "urban", "ntd_2024_weekday_tx.csv"))}
    sh = shares()
    s_dfw = sh["19100"]
    asc_dfw = config.load()["ridership"]["asc"]
    reg = load_registry()
    by = {m["id"]: m for m in reg["metros"]}
    for m in reg["metros"]:
        m.pop("calibration", None)
        m.pop("ridership_asc", None)
    fits = []
    for mid, rows in CALIBRATE.items():
        n = sum(ntd[r] for r in rows)
        by[mid]["calibration"] = {"weekday_boardings": n, "source": "NTD 2024 average typical weekday, " +
                                  " + ".join(f"{a} {b} {ntd[(a, b)]:,}" for a, b in rows)}
        save_registry(reg)
        r = generate.calibrate(mid, log=print)
        x = math.log(sh[by[mid]["cbsa"]] / s_dfw)
        fits.append((mid, x, r["asc"] - asc_dfw, r["asc"], n))
        print(f"{mid}: asc {r['asc']:+.4f} (DFW {asc_dfw:+.4f}), ACS share {sh[by[mid]['cbsa']]:.2%}, "
              f"ln(share / DFW's) {x:+.3f}")
    k = sum(x * y for _, x, y, _, _ in fits) / sum(x * x for _, x, _, _, _ in fits)
    print(f"slope k = {k:.3f}")
    for m in reg["metros"]:
        if m["id"] in CALIBRATE:
            continue
        s = max(sh[m["cbsa"]], FLOOR_SHARE)
        asc = asc_dfw + k * math.log(s / s_dfw)
        m["ridership_asc"] = {"asc": round(asc, 4), "source": (
            f"DFW's constant {asc_dfw:+.4f} + {k:.3f} x ln(ACS 2020-24 transit share {s:.2%} / DFW's {s_dfw:.2%}); "
            "slope fitted on Houston (study/urban_metros.py)")}
    save_registry(reg)
    checks = []
    for mid, rows in CHECK.items():
        n = sum(ntd[r] for r in rows)
        r = generate.calibrate(mid, log=print)
        model = (r["today"] or {}).get("daily_boardings", 0.0)
        checks.append({"id": mid, "asc": r["asc"], "weekday_boardings": n, "model_boardings": round(model)})
        print(f"{mid} (check): asc {r['asc']:+.4f}: today's lines {model:,.0f} boardings in the model, NTD {n:,}")
    reg["_calibration"] = {"asc_dfw": asc_dfw, "share_dfw": s_dfw, "slope_k": round(k, 4),
                           "fits": [{"id": a, "ln_share_ratio": round(x, 4), "asc": c, "weekday_boardings": n}
                                    for a, x, _, c, n in fits], "checks": checks}
    save_registry(reg)


def generate(ids=None, floors=None, sweep_dir=None):
    """Generate each metro's network (urban/generated/<id>/). `floors`: also run the line planner at each of these
    floors from the same pruned network (study/fixed_point.py), written to sweep_dir/<floor>/<id>/."""
    from metro import generate as gen
    fix_inputs()
    reg = load_registry()
    for m in reg["metros"]:
        if ids and m["id"] not in ids:
            continue
        t0 = time.time()
        out = os.path.join(HOME, "generated", m["id"])
        try:
            r = gen.generate(m["id"], budget_musd=m["budget_musd"], out=out, policies=policies(m), future_years=FUTURE,
                             full_model=True, override={"selection": {"plan": {"floor": PLAN_FLOOR}}},
                             plan_floors=floors, sweep_dir=sweep_dir)
        except (Exception, SystemExit) as e:   # one metro failing doesn't stop the rest
            import traceback; traceback.print_exc(); print(f"{m['id']}: FAILED {type(e).__name__}: {e}")
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
                json.dump({"id": m["id"], "failed": f"{type(e).__name__}: {e}"}, f, indent=1)
            continue
        for f, rf in (r.get("sweep") or {}).items():
            write_summary(m, rf, rf["out"], t0)
        write_summary(m, r, out, t0)


def write_summary(m, r, out, t0):
    """summary.json for one generated network (r: metro.generate's result)."""
    if True:
        st, res = r["stats"], r["model"] or {}
        chosen = r["chosen"]
        by_mode = {}
        for c in chosen:
            d = by_mode.setdefault(c.mode, {"lines": 0, "km": 0.0, "capital_musd": 0.0})
            d["lines"] += 1
            d["km"] += c.km
            d["capital_musd"] += c.capital
        ex, g = res.get("existing") or {}, res.get("generated") or {}
        s = {"id": m["id"], "name": m["name"], "texas_pop": m["texas_pop"], "pop": float(r["m"].pop.sum()),
             "jobs": float(r["m"].jobs.sum()), "budget_musd": r["budget"], "capital_musd": st["capital_musd"],
             "opex_new_musd": st["opex_new_musd"], "lines": len(chosen), "by_mode": by_mode,
             "stations_new": st["stations_new"], "existing_lines": len(r["ex_tables"]["lines.csv"]),
             "pop_800m": st["cov800_all"][0] / float(r["m"].pop.sum()),
             "pop_800m_today": st["cov800_existing"][0] / float(r["m"].pop.sum()),
             "trips_today": ex.get("daily_trips", 0.0), "trips": g.get("daily_trips", 0.0),
             "boardings": g.get("daily_boardings", 0.0), "jobs_45": g.get("access_jobs_45", 0.0),
             "jobs_45_today": ex.get("access_jobs_45", 0.0) if ex else None,
             "asc": r["asc"], "asc_note": r["asc_note"], "minutes": (time.time() - t0) / 60}
        oc = r["cfg"]["operating"]
        feeder_usd = oc.get("feeder_usd_per_boarding", 0.0) * oc["days_per_year"] / 1e6   # $M a year per daily boarding
        # the feeder grid's operating cost, as DFW Transit counts it ($ per feeder boarding): the network's less today's
        s["feeder_boardings"], s["feeder_boardings_today"] = g.get("feeder_boardings", 0.0), ex.get("feeder_boardings", 0.0)
        s["feeder_opex_musd"] = (s["feeder_boardings"] - s["feeder_boardings_today"]) * feeder_usd
        commutes = float(r["cfg"]["demand"]["total_commutes"]) * r["cfg"]["ridership"]["telework"]
        s["commutes"], s["share"] = commutes, g.get("transit_commuters", 0.0) / commutes if g else 0.0
        s["future"] = {}
        for y, fr in (res.get("future") or {}).items():   # commutes grow with jobs (dfwt evaluate.year_inputs)
            c = commutes * fr["generated"]["jobs"] / max(float(r["m"].jobs.sum()), 1.0)
            fe = fr["existing"] or {}
            s["future"][str(y)] = {"trips": fr["generated"]["daily_trips"], "trips_today_lines": fe.get("daily_trips", 0.0),
                                   "pop": fr["generated"]["pop"], "jobs": fr["generated"]["jobs"],
                                   "share": fr["generated"]["transit_commuters"] / c,
                                   "share_today_lines": fe.get("transit_commuters", 0.0) / c,
                                   "feeder_opex_musd": (fr["generated"].get("feeder_boardings", 0.0)
                                                        - fe.get("feeder_boardings", 0.0)) * feeder_usd}
        with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)
        print(f"{m['id']}: {len(chosen)} lines, ${st['capital_musd'] / 1e3:.1f}B, {s['trips']:,.0f} trips a day "
              f"({s['trips_today']:,.0f} today), {s['minutes']:.1f} min")


MODES = (("metro", "Metro"), ("streetcar", "Streetcar"), ("brt", "BRT"), ("commuter", "Regional rail"))


def summary():
    reg = load_registry()
    sh = shares()
    cal = reg.get("_calibration", {})
    rows = []
    for m in reg["metros"]:
        p = os.path.join(HOME, "generated", m["id"], "summary.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                rows.append(json.load(f))
        else:
            rows.append({"id": m["id"], "name": m["name"], "failed": "not generated"})
    ok = [r for r in rows if "failed" not in r]
    out = ["# The urban layer: rail and BRT for Texas's other metros", "",
           "Generated by `python study/urban_metros.py summary` from `urban/generated/<id>/` (DFW Transit's network "
           "generator, `vendor/dfw-transit/metro/`, driven from this repo with `METRO_HOME=urban`). Every network is "
           "drawn by the generator from Census population and jobs, LODES commutes, today's GTFS and Overture roads "
           "and rail; nothing is hand-drawn. Each metro's `report.md` lists its centers, corridors and every line "
           "chosen or rejected.", "",
           "**Budget.** DFW Transit's rate per resident ($2.3B a year for 7.47M people) times the metro's Texas "
           "population (2020) over 30 years, the generator's default horizon, in 2025 dollars; over DFW Transit's whole "
           "75-year horizon for Houston, Austin, San Antonio and El Paso, whose layouts can carry a DFW-sized network "
           "(`study/metro_potential.md`). Dallas-Fort Worth is not here: it has its own plan, DFW Transit.", "",
           "**Policies.** Every metro gets the 2 million plan's station-area land use from 2030. Houston, Austin, San "
           "Antonio and El Paso also get its access and parking policies, in force from the start: feeder buses every 15 "
           "minutes, bikes, scooters and drop-off to stations, walks up to 1.6 km on straighter paths, no park & ride "
           "under 1.6 km, and $5 a day to park where jobs reach 15,000 per km2. The generator chooses their lines with "
           "the policies on; the ridership constant is still the one fitted to today's riders under today's conditions. "
           "Austin and San Antonio also run in build-out mode (smaller centers, thinner BRT).", "",
           "**Ridership constant.** The demand model is DFW Transit's commute model. Its constant (how much people "
           "favour transit beyond its times and costs) is fitted per metro where NTD counts today's rail or BRT riders, "
           "and set from the metro's ACS transit share elsewhere:", ""]
    if cal:
        out += ["| Metro | Today's lines carry (NTD 2024, weekday) | ACS transit share of workers | Constant |",
                "|---|---|---|---|",
                f"| Dallas-Fort Worth (DFW Transit) | 80,000 rail | {cal['share_dfw']:.2%} | {cal['asc_dfw']:+.3f} |"]
        name = {m["id"]: m["name"].split(",")[0] for m in reg["metros"]}
        cbsa = {m["id"]: m["cbsa"] for m in reg["metros"]}
        for f in cal["fits"]:
            out.append(f"| {name[f['id']]} | {f['weekday_boardings']:,} | {sh[cbsa[f['id']]]:.2%} | {f['asc']:+.3f} |")
        out += ["", f"Through DFW and Houston, the constant rises {cal['slope_k']:.2f} for each unit of ln(transit share / "
                "DFW's). Every other metro gets that line at its own ACS 2020-2024 share (at least 0.1%); the constants are "
                "in `urban/metros.json`.", ""]
        for c in cal.get("checks", []):
            out += [f"**Check, {name[c['id']]}:** at its constant ({c['asc']:+.2f}) the model puts "
                    f"{c['model_boardings']:,} riders a day on today's Red Line; NTD counts {c['weekday_boardings']:,}. "
                    "Fitting the constant to that one line would take it to about -2.05, as if Austinites liked transit "
                    "far less than Dallasites, against ACS. The miss is the line: one train every 30-60 minutes. DFW's "
                    "calibration is mostly frequent light rail, and the model doesn't penalise infrequent rail enough. "
                    "Generated regional rail (every 20 minutes) and streetcars (every 20) are likely overrated too, "
                    "though less: metro (every 6) and BRT (every 8) are where the calibration holds.", ""]
    out += ["## Every metro", "",
            "Trips are daily transit trips from the model with every line open on today's land use (2026), against "
            "today's rail and BRT; local buses are the model's feeder grid in both. *Per $B* is the new daily trips per "
            "$B of capital.", "",
            "| Metro | People (TX) | Budget | Capital | Lines | Metro / streetcar / BRT / regional rail km | "
            "Within 800 m of a station | Trips a day (today) | New trips per $B | Constant |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "failed" in r:
            out.append(f"| {r['name'].split(',')[0]} | | | | | not generated: {r['failed']} | | | | |")
            continue
        km = " / ".join(f"{r['by_mode'].get(k, {}).get('km', 0):,.0f}" for k, _ in MODES)
        per = (r["trips"] - r["trips_today"]) / max(r["capital_musd"] / 1000, 1e-9) if r["capital_musd"] else 0
        out.append(f"| {r['name'].split(',')[0]} | {r['texas_pop'] / 1e6:.2f}M | ${r['budget_musd'] / 1e3:.1f}B | "
                   f"${r['capital_musd'] / 1e3:.1f}B | {r['lines']} | {km} | {r['pop_800m']:.0%} ({r['pop_800m_today']:.0%}) | "
                   f"{r['trips']:,.0f} ({r['trips_today']:,.0f}) | {per:,.0f} | {r['asc']:+.2f} |")
    if ok:
        cap = sum(r["capital_musd"] for r in ok)
        bud = sum(r["budget_musd"] for r in ok)
        trips = sum(r["trips"] for r in ok)
        today = sum(r["trips_today"] for r in ok)
        pop = sum(r["texas_pop"] for r in ok)
        kms = {k: sum(r["by_mode"].get(k, {}).get("km", 0) for r in ok) for k, _ in MODES}
        out += ["", f"**All {len(ok)} metros:** {pop / 1e6:.1f}M Texans, ${cap / 1e3:.0f}B of capital against "
                f"${bud / 1e3:.0f}B of budget, {sum(r['lines'] for r in ok)} lines ("
                + ", ".join(f"{lab.lower()} {kms[k]:,.0f} km" for k, lab in MODES) + f"), "
                f"{trips:,.0f} daily transit trips against {today:,.0f} today, "
                f"{(trips - today) / (cap / 1e3):,.0f} new daily trips per $B; "
                f"${sum(r['opex_new_musd'] for r in ok) / 1e3:.1f}B a year more to operate.", ""]
        none = [r for r in ok if not r["lines"]]
        unspent = bud - cap
        out += [f"**Unspent: ${unspent / 1e3:.0f}B of the ${bud / 1e3:.0f}B.** {len(none)} metros get no line at all ("
                + ", ".join(r["name"].split(",")[0].split("-")[0] for r in none) + "), and most of the other small ones "
                "one short BRT line. The generator only drafts lines between activity centers, clusters of at least "
                "20,000 people + jobs at 4,000 per km2 or more, and only gives a corridor a mode when the people + jobs "
                "along it reach that mode's density (DFW's calibration, `vendor/dfw-transit/metro/generate.json`). "
                "Texas's smaller metros are mostly too spread out for rail or BRT by those tests; their case is for "
                "local bus, which this generator doesn't draw. The unspent money goes back to the "
                "statewide pot for the timing step.", ""]
        small = [r for r in ok if r["texas_pop"] < 300_000]
        if small:
            sc = sum(r["capital_musd"] for r in small)
            st = sum(r["trips"] - r["trips_today"] for r in small)
            big = [r for r in ok if r["texas_pop"] >= 300_000]
            bc = sum(r["capital_musd"] for r in big)
            bt = sum(r["trips"] - r["trips_today"] for r in big)
            out += [f"Metros under 300,000 people ({len(small)}): ${sc / 1e3:.0f}B for {st:,.0f} new daily trips, "
                    f"{st / max(sc / 1e3, 1e-9):,.0f} per $B; the {len(big)} larger ones: {bt / max(bc / 1e3, 1e-9):,.0f} "
                    "per $B. The flat per-resident budget is a starting point: the statewide timing step moves money to "
                    "where it buys the most riders, urban or intercity.", ""]
    sel = []
    for r in ok:
        cp = os.path.join(HOME, "generated", r["id"], "candidates.csv")
        if not os.path.exists(cp):
            continue
        cs = read_csv(cp)
        kept = [c for c in cs if c["status"] == "chosen"]
        cut = [c for c in cs if c["status"] == "rejected" and c["reason"].startswith("full model")]
        if kept and all(c.get("model_trips") for c in kept):
            sel.append((r, kept, cut))
    if sel:
        out += ["## How the lines were chosen", "",
                "By the full model (DFW Transit `metro/modelselect.py`): the generator's quick sketch, which counts only "
                "commutes between one line's own stations, draws a wide pool (half its usual floor), and the demand "
                "model values every line in 2050, with the metro's growth and the land use of the whole pool, as the "
                "mean of the riders the network loses without it and the riders it adds alone to today's network. "
                "Lines under 1.0 new daily trips per $M of capital plus 20 years' operating cost go, worst first, in "
                "rounds (about the weakest tenth of DFW's own 2 million plan scores lower), and the rest open best value "
                "first.", "",
                "| Metro | Pool | Kept | Cut by the full model | Best kept, trips per $M | Weakest kept | Highest-value line |",
                "|---|---|---|---|---|---|---|"]
        for r, kept, cut in sel:
            v = sorted(float(c["model_trips_per_musd"]) for c in kept)
            top = max(kept, key=lambda c: float(c["model_trips_per_musd"]))
            out.append(f"| {r['name'].split(',')[0]} | {len(kept) + len(cut)} | {len(kept)} | {len(cut)} | {v[-1]:.1f} | "
                       f"{v[0]:.1f} | {top['name']} ({top['mode']}, {float(top['model_trips']):,.0f} trips) |")
        out.append("")
        if not any(cut for _, _, cut in sel):
            weakest = min(float(c["model_trips_per_musd"]) for _, kept, _ in sel for c in kept)
            dup = sum(1 for r, _, _ in sel for c in read_csv(os.path.join(HOME, "generated", r["id"], "candidates.csv"))
                      if c["status"] == "rejected" and c["reason"].startswith("duplicate"))
            brn = sum(1 for _, kept, _ in sel for c in kept if "a branch" in c["reason"])
            out += [f"**The full model cuts nothing.** Every line the generator can draw scores at least {weakest:.1f} "
                    "new daily trips per $M, above the floor and about where DFW's own plan's weaker lines sit: the sketch "
                    "underrates lines that work as a network (Houston's weakest regional rail line scores 0.08 in the sketch, "
                    "1.9 in the full model), and dropping its floor adds lines, mostly in Houston (50 lines and $72B to 71 "
                    "and $121B; 5.8% of commutes by transit in 2100 to 6.8%) with the sketch's floor dropped.", "",
                    f"**Branches.** A candidate that runs within 400 m of chosen lines for more than half its length is a "
                    "duplicate unless it has at least 5 km of route of its own: then it's a branch off a shared trunk, "
                    "charged only for the track it doesn't share with lines of its mode (the network splits shared track's "
                    f"cost among the lines on it). {brn} lines are branches; {dup} candidates are still duplicates "
                    "(parallel copies or near-copies of chosen lines). A metro branch along a BRT trunk is a different "
                    "mode on the same street, so it pays its own way: in effect an upgrade of that stretch.", ""]
    fut = [r for r in ok if r.get("future")]
    if fut:
        try:
            sys.path.insert(0, os.path.join(ROOT, "study"))
            import metro_potential
            yard = metro_potential.dfw_yardstick()
        except Exception as e:   # the DFW reference needs DFW Transit's published layers
            print("no DFW yardstick:", e)
            yard = None
        out += ["## With growth and station-area development, 2050 and 2100", "",
                "The same networks, every line open, in 2050 and 2100: each metro grows on its own counties' trend "
                "(`data/zones/county_growth.csv`; the registry's `growth`, jobs keeping pace with people) instead of "
                "DFW's forecast, and new stations get the 2 million plan's land use: stronger development around them "
                "(up to +75% people downtown), today's stations upzoned from 2030, and a fifth of the growth that would "
                "land elsewhere steered into station areas up to Ontario-style density targets (DFW Transit "
                "`scenarios/two_million/config.json` growth). Share = transit commuters over commuters (after "
                "telework); commuters grow with jobs.", ""]
        if yard:
            out += [f"Dallas-Fort Worth under its own plan, for comparison: {yard[2025]['overall']:.1%} of commutes by "
                    f"transit today, {yard[2050]['overall']:.1%} in 2050 and {yard[2100]['overall']:.1%} in 2100 "
                    "(`study/metro_potential.md`).", ""]
        pol = {m["id"] for m in reg["metros"] if m.get("policies")}
        out += ["| Metro | Package | People 2020 | 2050 | 2100 | Transit share with the network, today's land use | 2050 | "
                "2100 | 2100, today's lines alone | Daily trips 2050 | 2100 | Feeder buses added, $M a year (2050) |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in fut:
            f50, f00 = r["future"]["2050"], r["future"]["2100"]
            out.append(f"| {r['name'].split(',')[0]} | {'policies + land use' if r['id'] in pol else 'land use'} | "
                       f"{r['pop'] / 1e6:.2f}M | {f50['pop'] / 1e6:.2f}M | "
                       f"{f00['pop'] / 1e6:.2f}M | {r['share']:.1%} | {f50['share']:.1%} | {f00['share']:.1%} | "
                       f"{f00['share_today_lines']:.1%} | {f50['trips']:,.0f} | {f00['trips']:,.0f} | "
                       f"{f50.get('feeder_opex_musd', 0.0):,.0f} |")
        t50 = sum(r["future"]["2050"]["trips"] for r in fut)
        t00 = sum(r["future"]["2100"]["trips"] for r in fut)
        c0 = sum(r["commutes"] for r in fut)
        sh = lambda y: sum(r["future"][y]["share"] * r["commutes"] * r["future"][y]["jobs"] / r["jobs"] for r in fut) / \
            sum(r["commutes"] * r["future"][y]["jobs"] / r["jobs"] for r in fut)  # noqa: E731
        fp = [r for r in fut if r["id"] in pol]
        if fp:
            out += ["", f"**The {len(fp)} policy metros in 2100:** " + ", ".join(
                f"{r['name'].split(',')[0].split('-')[0]} {r['future']['2100']['share']:.1%}" for r in fp)
                + (f" of commutes by transit, against {yard[2100]['overall']:.1%} in DFW under its plan" if yard else "")
                + ". With the land use alone and 30-year budgets (Austin and San Antonio 75) they reached 2.9-5.6%: "
                "feeder buses widen every station's reach, priced parking at the densest job centers makes the drive "
                "downtown cost something, and the generator draws a bigger network for riders who will use it. Their feeder buses "
                f"cost ${sum(r['future']['2050']['feeder_opex_musd'] for r in fp):,.0f}M a year to run by 2050."]
        out += ["", f"**All {len(fut)} metros:** {trips:,.0f} daily transit trips on today's land use, {t50:,.0f} in 2050 "
                f"and {t00:,.0f} in 2100; {sum(r['share'] * r['commutes'] for r in fut) / c0:.1%} of commutes by "
                f"transit, then {sh('2050'):.1%} and {sh('2100'):.1%}.", "",
                "Every line is open from 2026 here, so station areas have had their full time to develop by 2050; the "
                "timing step opens lines over the century and scales each metro's riders along these years.", ""]
    out += ["## Caveats", "",
            "- The model is DFW's commute model with one constant moved per metro. Its time and cost weights, access "
            "and parking assumptions are DFW's; the slope rests on one metro, Houston. The Austin check says the model "
            "overrates infrequent rail several times over.",
            "- Rapid buses that NTD files as plain bus (MetroRapid, Primo, Brio) are counted as today's frequent buses, "
            "not BRT, so the generator may propose BRT with its own lanes on their streets, and Austin's and San "
            "Antonio's starting points look emptier than riders see them. Project Connect (Austin) and VIA's Green Line "
            "are not in today's network.",
            "- ACS transit shares in college towns (College Station-Bryan, and San Marcos within Austin) include "
            "university shuttles; the constant reads them as a liking for transit in general.",
            "- Commutes to and from Mexico (El Paso, Laredo, McAllen, Brownsville, Eagle Pass) are not in LODES.",
            "- The first table's trips are on today's land use; the 2050 and 2100 runs add growth on a trend extrapolation "
            "(not an official projection: Austin's counties keep growing fast, to 3.8 times their 2020 population by "
            "2100) and DFW's station-area responses, which assume Texas's other metros zone and build like DFW's plan. "
            "Non-commute trips are not in either (DFW Transit's non-commute prototype is off).",
            "- The policy package is in force from the model's first year in the four policy metros, and its feeder buses "
            "on top of a constant fitted with today's buses: DFW Transit calls that an upper bound (today's bus-to-rail "
            "riders count twice). Priced parking needs cities to set it; the revenue isn't counted anywhere.", ""]
    with open(os.path.join(ROOT, "study", "urban_metros.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    flat = [{k: v for k, v in r.items() if k != "by_mode"} | {f"{k}_km": round(r.get("by_mode", {}).get(k, {}).get("km", 0), 1)
                                                               for k, _ in MODES} for r in rows]
    fields = sorted({k for r in flat for k in r}, key=lambda k: (k != "id", k))
    with open(os.path.join(ROOT, "study", "urban_metros.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(flat)
    print("\n".join(out))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "calibrate":
        calibrate()
    elif cmd == "generate":
        args, floors, sweep_dir = sys.argv[2:], None, None
        if "--sweep" in args:   # --sweep 1,1.75,4 [--sweep-dir DIR]: the line planner at several floors (study/fixed_point.py)
            k = args.index("--sweep")
            floors = [float(x) for x in args[k + 1].split(",")]
            args = args[:k] + args[k + 2:]
        if "--sweep-dir" in args:
            k = args.index("--sweep-dir")
            sweep_dir = args[k + 1]
            args = args[:k] + args[k + 2:]
        generate(args or None, floors, sweep_dir)
    else:
        summary()
