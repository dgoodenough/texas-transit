"""How much of DFW's transit share could each Texas metro reach? A first look.

    python study/metro_potential.py                 # structure and DFW's yardstick (fast)
    python study/metro_potential.py --model austin san-antonio houston el-paso corpus-christi midland dfw

DFW Transit's 2 million riders plan takes DFW from about 0.6% of commutes by transit today to about 4%
in 2050 and 9% in 2100. The generated plans for the other metros (study/urban_metros.md) don't get
close, and they shouldn't all: a metro's layout limits what any network can do. This study separates
the two:

1. **DFW's yardstick.** DFW Transit's map layers (vendor/dfw-transit/docs/layers/two_million.js) give
   every block group's share of commutes by transit, year by year, under the full plan (network,
   policies, growth steered to stations). Grouped by how dense the area around each block group is
   (people + jobs within 1 km, per km2), that is the share DFW's plan reaches at each density.
2. **Structure.** The same density for every block group in the 25 metros (2020 people, LODES jobs).
   Applying DFW's share at each density to a metro's residents gives its **DFW-equivalent share**:
   what it would reach if it got DFW's whole package and responded like DFW at each density. Its
   layout, not its size, sets the number.
3. **Model test (--model).** The network generator at DFW's per-resident spending over 75 years
   (instead of 30), with the 2 million plan's policies at their mature settings: 15-minute feeder
   buses, bike and scooter access to stations, 1.6 km walks, drop-off, parking prices doubled in
   paid districts and $5 a day at job centers of 15,000+ jobs per km2. Every metro, and DFW itself,
   on today's land use, so the comparison is like for like (no growth, no station-area development).

Writes study/metro_potential.md (part 3 is kept from the last --model run in study/metro_potential.json).
"""
import argparse
import copy
import csv
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DFW = os.path.join(ROOT, "vendor", "dfw-transit")
BANDS = [0, 1000, 3000, 6000, 10000, float("inf")]
BAND_LABELS = ["under 1,000", "1,000-3,000", "3,000-6,000", "6,000-10,000", "10,000 or more"]
KERNEL_KM = 1.0
# the second dimension: the job market a place sits in (jobs within REACH_KM, straight line)
REACH_KM = 10.0
REACH = [0, 100_000, 250_000, 500_000, float("inf")]
REACH_LABELS = ["under 100k", "100k-250k", "250k-500k", "500k or more"]
DENSE = [0, 3000, 6000, float("inf")]
DENSE_LABELS = ["under 3,000", "3,000-6,000", "6,000 or more"]
DFW_POP, DFW_MUSD_YEAR, YEARS = 7_468_799, 2300, 75
PER_RESIDENT_75 = DFW_MUSD_YEAR * YEARS / DFW_POP          # $M per resident over 75 years
MODEL_JSON = os.path.join(ROOT, "study", "metro_potential.json")
LEVERS = {   # the 2 million plan's policies (scenarios/two_million/config.json) at their mature settings, in force
             # from the model's first year (it runs on 2026 land use)
    "access": {"feeder": {"headway_min": {"2025": 15}},
               "micromobility": {"enabled": True, "from_year": 2025, "max_km": 5, "speed_kmh": 15},
               "kiss_ride": {"enabled": True, "from_year": 2025},
               "walk_max_m": 1600, "walk_circuity": 1.15, "pnr_min_km": 1.6, "pnr_suburban": {"enabled": False}},
    "ridership": {"parking_policy": {"start_year": 2020, "full_year": 2025, "price_growth": 1.0,
                                     "priced_centers": {"min_jobs_per_km2": 15000, "usd_per_day": 5}}},
}


def density(lat, lon, act, radius=KERNEL_KM, per_area=True):
    """People + jobs per km2 within `radius` km of each point (or the total, per_area False)."""
    k = math.cos(math.radians(float(np.mean(lat))))
    x, y = lon * 111.2 * k, lat * 111.2
    order = np.argsort(x)
    xs = x[order]
    out = np.zeros(len(x))
    for i in range(len(x)):
        lo, hi = np.searchsorted(xs, x[i] - radius), np.searchsorted(xs, x[i] + radius)
        idx = order[lo:hi]
        near = (x[idx] - x[i]) ** 2 + (y[idx] - y[i]) ** 2 <= radius ** 2
        out[i] = act[idx][near].sum() / ((math.pi * radius ** 2) if per_area else 1.0)
    return out


def band_of(d):
    return np.digitize(d, BANDS[1:-1])


def cell_of(dens, reach):
    """(density band, job-market band) as one index into DENSE x REACH."""
    return np.digitize(dens, DENSE[1:-1]) * len(REACH_LABELS) + np.digitize(reach, REACH[1:-1])


def dfw_layers():
    """{year: (pop, jobs, transit share)} per DFW block group (in data/metroplex_density.csv order)."""
    text = open(os.path.join(DFW, "docs", "layers", "two_million.js"), encoding="utf-8").read()
    obj = json.loads(text[text.index("{", text.index('"] =')):text.rindex("}") + 1])   # after (window...)["two_million"] =
    out = {}
    acc = {k: None for k in ("pop", "jobs", "transit")}
    for i, y in enumerate(obj["years"]):
        for k in acc:
            row = np.array(obj[k][i], dtype=float)
            acc[k] = row if acc[k] is None else acc[k] + row
        out[y] = (acc["pop"] * 10, acc["jobs"] * 10, acc["transit"] / 1000)
    return out


def dfw_yardstick():
    rows = list(csv.DictReader(open(os.path.join(DFW, "data", "metroplex_density.csv"), encoding="utf-8-sig")))
    lat = np.array([float(r["lat"]) for r in rows])
    lon = np.array([float(r["lon"]) for r in rows])
    lay = dfw_layers()
    out = {}
    for y in (2025, 2050, 2100):
        pop, jobs, share = lay[y]
        b = band_of(density(lat, lon, pop + jobs))
        bands = []
        for i in range(len(BAND_LABELS)):
            m = b == i
            w = pop[m].sum()
            bands.append({"pop_share": float(w / pop.sum()), "share": float((share[m] * pop[m]).sum() / w) if w else 0.0})
        dens = density(lat, lon, pop + jobs)
        reach = density(lat, lon, jobs, REACH_KM, per_area=False)
        c = cell_of(dens, reach)
        cells = []
        for i in range(len(DENSE_LABELS) * len(REACH_LABELS)):
            m = c == i
            w = pop[m].sum()
            cells.append({"pop_share": float(w / pop.sum()), "share": float((share[m] * pop[m]).sum() / w) if w else None})
        out[y] = {"overall": float((share * pop).sum() / pop.sum()), "bands": bands, "cells": cells,
                  "dense_share": float(pop[b >= 3].sum() / pop.sum())}
    return out


def metro_structure():
    reg = json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))
    out = []
    rows = list(csv.DictReader(open(os.path.join(DFW, "data", "metroplex_density.csv"), encoding="utf-8-sig")))
    entries = [("dfw", "Dallas-Fort Worth", rows)] + [
        (m["id"], m["name"].split(",")[0],
         list(csv.DictReader(open(os.path.join(ROOT, "urban", "data", "metros", m["id"], "zones.csv"), encoding="utf-8"))))
        for m in reg["metros"]]
    for mid, name, zs in entries:
        lat = np.array([float(z["lat"]) for z in zs])
        lon = np.array([float(z["lon"]) for z in zs])
        pop = np.array([float(z["pop"] or 0) for z in zs])
        jobs = np.array([float(z["jobs"] or 0) for z in zs])
        d = density(lat, lon, pop + jobs)
        b = band_of(d)
        jd = density(lat, lon, jobs)
        reach = density(lat, lon, jobs, REACH_KM, per_area=False)
        c = cell_of(d, reach)
        out.append({"id": mid, "name": name, "pop": float(pop.sum()), "jobs": float(jobs.sum()),
                    "pop_cells": [float(pop[c == i].sum() / pop.sum()) for i in range(len(DENSE_LABELS) * len(REACH_LABELS))],
                    "median_reach": float(np.median(np.repeat(reach, np.maximum(pop.astype(int) // 100, 0)))) if pop.sum() else 0,
                    "pop_bands": [float(pop[b == i].sum() / pop.sum()) for i in range(len(BAND_LABELS))],
                    "median_density": float(np.median(np.repeat(d, np.maximum(pop.astype(int) // 100, 0)))) if pop.sum() else 0,
                    "jobs_in_centers": float(jobs[jd >= 5000].sum() / max(jobs.sum(), 1))})
    return out


def equivalent(struct, yard, year):
    """DFW's share in each (density, job market) cell, weighted by the metro's residents there. A cell
    DFW has nobody in falls back to DFW's share at that density alone."""
    tot = 0.0
    for i, ps in enumerate(struct["pop_cells"]):
        cell = yard[year]["cells"][i]
        if ps <= 0:
            continue
        sh = cell["share"]
        if sh is None:
            d = i // len(REACH_LABELS)
            sh = yard[year]["bands"][min(2 + d, 4) if d else 1]["share"]
        tot += ps * sh
    return tot


# ---------------------------------------------------------------- model test
def model_test(ids, buildout=False, log=print):
    """The generator in each metro at DFW's 75-year spending per resident: network alone and with the
    policies, or (buildout) in build-out mode with the policies (vendor/dfw-transit metro/generate.json
    buildout), added to the earlier runs."""
    os.environ["METRO_HOME"] = os.path.join(ROOT, "urban")
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    sys.path.insert(0, DFW)
    from dfwt import config
    from metro import generate, inputs
    reg = {m["id"]: m for m in json.load(open(os.path.join(ROOT, "urban", "metros.json"), encoding="utf-8"))["metros"]}
    results = json.load(open(MODEL_JSON, encoding="utf-8")) if os.path.exists(MODEL_JSON) else {}
    for mid in ids:
        pop = DFW_POP if mid == "dfw" else reg[mid]["texas_pop"]
        budget = PER_RESIDENT_75 * pop
        runs = {}
        configs = [("buildout_policies", True, True)] if buildout else [("network", False, False), ("network_policies", True, False)]
        for key, levers, bo in configs:
            t0 = time.time()
            out = os.path.join(ROOT, "urban", "potential", f"{mid}_{key}")
            # the policies go on top of the constant fitted to today's riders (generate's `policies`):
            # fitting it with them on would cancel them wherever the constant is fitted on every run (Houston)
            r = generate.generate(mid, budget_musd=budget, out=out, log=lambda s: None, buildout=bo,
                                  policies=copy.deepcopy(LEVERS) if levers else None)
            res = r["model"] or {}
            g, ex = res.get("generated") or {}, res.get("existing") or {}
            m = r["m"]
            commutes = float(r["cfg"]["demand"]["total_commutes"]) * r["cfg"]["ridership"]["telework"]
            runs[key] = {"capital": r["stats"]["capital_musd"], "lines": len(r["chosen"]),
                         "trips": g.get("daily_trips", 0.0), "today": ex.get("daily_trips", 0.0) if ex else 0.0,
                         "commuters": g.get("transit_commuters", 0.0), "share": g.get("transit_commuters", 0.0) / commutes,
                         "pop": float(m.pop.sum()), "minutes": (time.time() - t0) / 60}
            log(f"  {mid} {key}: ${runs[key]['capital'] / 1e3:.0f}B, {runs[key]['lines']} lines, "
                f"{runs[key]['share']:.2%} of commutes, {runs[key]['trips']:,.0f} trips a day ({runs[key]['minutes']:.1f} min)")
        results[mid] = {**results.get(mid, {}), "budget": budget, **runs}
        with open(MODEL_JSON, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)
    return results


# ---------------------------------------------------------------- report
def write(yard, structs, model):
    L = ["# How much of DFW's transit share could each metro reach?", "",
         "Generated by `python study/metro_potential.py`. A first look: DFW's plan as a yardstick, each metro's layout, "
         "and a model test of the biggest metros with DFW's spending and policies. Method in the script's docstring.", "",
         "## DFW's yardstick", "",
         f"Under DFW Transit's 2 million riders plan, the share of DFW's commutes made by transit is "
         f"{yard[2025]['overall']:.1%} today, {yard[2050]['overall']:.1%} in 2050 and {yard[2100]['overall']:.1%} in 2100. "
         "It depends heavily on how dense a place is:", "",
         "| People + jobs within 1 km, per km2 | Share of DFW residents, 2050 | Transit share of commutes, 2050 | Share of residents, 2100 | Transit share, 2100 |",
         "|---|---|---|---|---|"]
    for i, lab in enumerate(BAND_LABELS):
        a, b = yard[2050]["bands"][i], yard[2100]["bands"][i]
        L.append(f"| {lab} | {a['pop_share']:.0%} | {a['share']:.1%} | {b['pop_share']:.0%} | {b['share']:.1%} |")
    L += ["", "And on the size of the job market around a place (jobs within 10 km, straight line), DFW's 2050 share:", "",
          "| People + jobs within 1 km, per km2 | " + " | ".join(f"Jobs within 10 km: {r}" for r in REACH_LABELS) + " |",
          "|---|" + "---|" * len(REACH_LABELS)]
    for d, dl in enumerate(DENSE_LABELS):
        cells = [yard[2050]["cells"][d * len(REACH_LABELS) + r] for r in range(len(REACH_LABELS))]
        L.append(f"| {dl} | " + " | ".join(f"{c['share']:.1%} ({c['pop_share']:.0%})" if c["share"] is not None else "nobody"
                                           for c in cells) + " |")
    L += ["", "(In brackets: the share of DFW's residents in each cell.) Density matters, but so does the job market: "
          "the same density carries several times the transit share where hundreds of thousands of jobs are within reach.",
          ""]
    L += ["Densities are those of each year (2100's include the plan's growth steered to station areas: by then "
          f"{yard[2100]['dense_share']:.0%} of DFW's residents live at 6,000+ per km2, against {yard[2025]['dense_share']:.0%} "
          "today).", "",
          "## Each metro's layout, and what DFW's plan would do there", "",
          "*DFW-equivalent share*: each metro's residents in each cell of the table above (2020 density and job market), "
          "times the share DFW's plan reaches in that cell. It assumes the metro gets DFW's whole package (network, policies, growth steered to "
          "stations) and responds like DFW at each density; it doesn't add the densification DFW's plan brings, so the "
          "2100 column is the share on today's layout.", "",
          "| Metro | People | Residents at 6,000+ per km2 | Jobs in centers (5,000+ jobs per km2) | Median resident's density | "
          "Median resident's jobs within 10 km | DFW-equivalent share, 2050 | 2100 | Relative to DFW |", "|---|---|---|---|---|---|---|---|---|"]
    dfw = next(s for s in structs if s["id"] == "dfw")
    base = equivalent(dfw, yard, 2100)
    for s in sorted(structs, key=lambda s: -equivalent(s, yard, 2100)):
        e50, e100 = equivalent(s, yard, 2050), equivalent(s, yard, 2100)
        L.append(f"| {s['name']} | {s['pop'] / 1e6:.2f}M | {sum(s['pop_bands'][3:]):.0%} | {s['jobs_in_centers']:.0%} | "
                 f"{s['median_density']:,.0f} | {s['median_reach'] / 1e3:,.0f}k | {e50:.1%} | {e100:.1%} | {e100 / base:.0%} |")
    L += ["", f"Read across: DFW itself scores {base:.1%} here against the {yard[2100]['overall']:.1%} its plan reaches in "
          "2100, the difference being the densification the plan brings. Houston and Austin have DFW's layout: dense "
          "cores, big job markets, the same share of people at transit-friendly densities. With DFW's package, growth "
          "steered to stations included, they should reach DFW's 2100 share or close to it. San Antonio, Lubbock and El "
          "Paso can get two thirds to three quarters of the way. The small metros top out at a fifth to a quarter of "
          "DFW's share: their people live where even DFW's plan carries about 1% of commutes, because there are too few "
          "jobs within reach to fill trains.", ""]
    if model:
        L += ["## Model test: DFW's spending and policies, today's land use", "",
              f"The generator at DFW's per-resident spending over 75 years (${PER_RESIDENT_75 * 1e6:,.0f} a resident), "
              "first with the network alone, then with the 2 million plan's policies at their mature settings; DFW "
              "itself run the same way. Share = transit commuters over commuters (after telework). No growth and no "
              "station-area development, so all shares are below the plan's published 2100 figures; what matters is "
              "each metro against DFW.", "",
              "| Metro | Budget | Capital the generator finds lines for | Lines | Network alone: share | Trips a day | With policies: share | Trips a day | Relative to DFW (with policies) | Build-out with policies: capital, share, trips a day |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        ref = model.get("dfw", {}).get("network_policies", {}).get("share")
        for mid, r in sorted(model.items(), key=lambda kv: -kv[1]["network_policies"]["share"]):
            n, p = r["network"], r["network_policies"]
            name = next((s["name"] for s in structs if s["id"] == mid), mid)
            L.append(f"| {name} | ${r['budget'] / 1e3:.0f}B | ${p['capital'] / 1e3:.0f}B | {p['lines']} | {n['share']:.2%} | {n['trips']:,.0f} | "
                     f"{p['share']:.2%} | {p['trips']:,.0f} | {p['share'] / ref:.0%} | "
                     + (f"${r['buildout_policies']['capital'] / 1e3:.0f}B, {r['buildout_policies']['share']:.2%}, "
                        f"{r['buildout_policies']['trips']:,.0f} |" if "buildout_policies" in r else " |") if ref else "")
        L += ["", "Three things stand out:", "",
              "- **Per resident, Austin, El Paso and San Antonio match or beat DFW** under the same treatment (121%, 131% "
              "and 100% of DFW's share with the policies). Their layouts can carry DFW-level transit use; Midland gets "
              "no line at any budget.",
              "- **The generator can't spend DFW's money.** It stops when the next line would carry fewer than 0.5 new "
              "daily trips per $M (`vendor/dfw-transit/metro/generate.json` selection.min_trips_per_musd), judged by its "
              "quick sketch model. Austin finds lines for $17B of $53B; DFW itself for $73B of $172B, where DFW "
              "Transit's hand-built plan spends $135B. The hand plan's extra network (an arterial BRT grid, infill "
              "stations, more regional rail) is a big part of how it reaches 7-9% of commutes by 2100.",
              "- **Houston's earlier drop with the policies was a modelling artefact, now fixed.** Houston is the one metro "
              "whose ridership constant is fitted on every run, and it was being fitted with the policies already on, "
              "so today's lines kept today's riders despite them and the policies cancelled out on every line "
              "(`study/houston_policies.md`: on a fixed network every policy raises Houston's share, 2.48% to 3.57% "
              "together, unless the constant is refitted under them, which drops it to 2.21%). DFW Transit's "
              "generator now applies a policy package on top of today's calibration (`generate(policies=...)`), and "
              "Houston with the policies reaches 3.75% ($72B, 51 lines), 117% of DFW's share.",
              "- **Build-out mode** (`vendor/dfw-transit/metro/generate.json` buildout: smaller activity centers, BRT down "
              "to 2,000 people + jobs per route-km, a 0.25 cut-off) is the last column. It lifts Austin from 3.9% to 5.2% "
              "of commutes ($28B, 17 lines) and San Antonio from 3.2% to 4.2% ($27B, 22 lines). It doesn't help DFW: at "
              "its budget it adds $17B of BRT ($86B against $69B) for the same 230,000 trips without the policies, and "
              "neither mode reaches the hand plan's 315,000 (the downtown subway and through-running regional rail aren't "
              "corridors a generator draws). El Paso does worse (its few strong corridors split), and Houston gains "
              "nothing (3.6% with build-out against 3.75% without, for $9B more). So the plan uses build-out in "
              "Austin and San Antonio only "
              "(`tools/build_metro_registry.py` BUILDOUT), with DFW's whole 75-year horizon as their budget.", ""]
    L += ["## What it would take", "",
          "- **A bigger network in the big metros.** The generated plans spend 30 years of DFW's rate, and even at 75 "
          "years the generator stops at a third of the money. Loosening its cut-off and adding what DFW's hand plan has "
          "(an arterial BRT grid on the densest streets, infill stations) is the first job; Austin, Houston, San Antonio "
          "and El Paso have the layout to fill it.",
          "- **The policies, everywhere it's dense.** Frequent feeder buses, bikes and scooters to stations, longer walks "
          "to good stations, and parking that costs something at the biggest job centers do as much as the network in "
          "DFW's plan; they cost little capital.",
          "- **Steer growth to stations.** DFW's 2100 share leans on growth steered to station areas and upzoning. A metro "
          "that grows the way it has, outward, keeps its density and its ceiling.",
          "- **Accept a lower ceiling in the small metros.** Midland, Odessa, Tyler and Victoria have almost nobody at "
          "the densities where DFW's plan reaches double digits; their transit is local buses, and a share near today's "
          "Austin (1%) would be a success.", "",
          "Done: build-out mode, used in Austin and San Antonio; Houston's policy result (above); each metro's own "
          "growth and the plan's station-area development, in 2050 and 2100; the policy package and DFW's 75-year budget "
          "in Austin, Houston, San Antonio and El Paso, and the timing study with their bigger networks "
          "(`study/urban_metros.md`, `study/timing.md`). The target was DFW's 2100 share, about 7% of commutes: Austin "
          "and San Antonio pass it (8.0% and 7.9%), Houston and El Paso reach 5.8% and 5.9%. Then the selection by the "
          "full model (`study/urban_metros.md`, How the lines were chosen): it cuts nothing, the generator's candidates "
          "are the limit, and dropping the sketch's floor takes Houston to 6.8%. Then branches off shared trunks (the "
          "duplicate rule loosened): Houston 7.7%, San Antonio 9.0%, Austin 10.3%, El Paso 6.5%.", ""]
    with open(os.path.join(ROOT, "study", "metro_potential.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", nargs="*", help="metro ids for the model test (dfw for DFW itself)")
    ap.add_argument("--buildout", action="store_true", help="with --model: the build-out run (with policies)")
    a = ap.parse_args()
    model = model_test(a.model, a.buildout) if a.model else (json.load(open(MODEL_JSON, encoding="utf-8")) if os.path.exists(MODEL_JSON) else {})
    write(dfw_yardstick(), metro_structure(), model)


if __name__ == "__main__":
    main()
