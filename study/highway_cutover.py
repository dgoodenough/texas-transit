"""Highway cutover: when is a dollar on an urban transit line worth less than a dollar on widening a freeway?

    python study/highway_cutover.py

Writes study/highway_cutover.md. Directional only: one representative widened Texas urban freeway against the
plan's own urban lines (docs/data/timeline.json, from study/timing.py), valued in the same framework as
study/timing.py (50 years at 3%, 300 weekday-equivalent days, the same car externalities and agglomeration share).

1. Capacity and capital. A freeway lane-mile's cost from recent Texas projects (HIGHWAY_PROJECTS) against the
   plan's lines' capital per route-km; a lane's throughput (LANE_VPH x occupancy) against a line's at the plan's
   headways and vehicle sizes (vendor/dfw-transit/config.json modes).
2. Use. What the money actually carries: passenger-km a day per $M, a lane at a typical Texas urban freeway's
   traffic against each line's model riders (2050).
3. Value. A widening is valued as travel time saved on a congested segment (BPR delay curve) at the plan's own
   value of time, plus the same 20% agglomeration share transit gets, minus crash and emission costs of any
   induced traffic (texas/benefits.json). Induced demand follows the fundamental law of road congestion
   (Duranton & Turner 2011): vehicle-km rise with lane-km at elasticity ELASTICITY, phased in over RAMP_YEARS,
   which takes back the time saved; induced drivers get the rule of half. The widening's benefit-cost ratio is
   the cutover: a transit line whose ratio (study/timing.py's, all benefits) is below it delivers less per
   dollar. In riders: new daily trips per $M of whole-life cost (capital plus 50 years' operating cost) at
   which a line's ratio equals the highway's.
"""
import json
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "study"))
import timing as tm  # noqa: E402

CFG = json.load(open(os.path.join(ROOT, "vendor", "dfw-transit", "config.json"), encoding="utf-8"))
BEN = tm.BEN
PV = tm.PV_FACTOR                       # 25.7: 50 years at 3%
DAYS = tm.URBAN_DAYS                    # 300 weekday-equivalent days, as the transit side
MILE_KM = 1.609344

# ---------------------------------------------------------------- highway constants (2025 $)
# Recent Texas freeway widenings: (name, cost $M as reported, cost year, corridor miles, lanes added (both
# directions), what the cost covers). Lanes added are the new through lanes (general purpose or managed),
# not rebuilt ones or frontage roads; the cost is the whole project's, which is what a lane costs in practice
# (rebuilt interchanges, drainage, right of way).
HIGHWAY_PROJECTS = [
    ("I-35 Capital Express South, Austin (SH 71 - SH 45 SE)", 548, 2023, 9.0, 4,
     "2 non-tolled managed lanes each way, suburban (TxDOT Mobility35 FAQ)"),
    ("I-35 Capital Express North, Austin (US 290 E - SH 45 N)", 606, 2023, 11.5, 2,
     "1 managed lane each way (TxDOT Mobility35 FAQ)"),
    ("I-10 Katy Freeway, Houston (2003-2008)", 2800, 2005, 23.0, 7,
     "11 to 18 main + managed lanes; program cost incl. right of way (H-GAC 2008; FHWA project profile)"),
    ("I-635 LBJ Express, Dallas (2011-2015)", 2645, 2012, 13.0, 5,
     "2-3 managed lanes each way (taken as 2.5) over rebuilt main lanes (FHWA project profile)"),
    ("I-45 NHHIP, Houston (2024-2042)", 13000, 2024, 24.0, 4,
     "2 managed lanes each way plus rerouting downtown (Construction Dive / Equipment World 2024)"),
    ("I-35 Capital Express Central, Austin (US 290 E - SH 71)", 5600, 2024, 8.0, 4,
     "2 managed lanes each way, lowered freeway, decks removed (TxDOT; $4.5B on Texas Clear Lanes)"),
]
# FHWA National Highway Construction Cost Index (2003 Q1 = 1), approximate annual levels read from FHWA's
# series: flat near 1.5-1.6 from 2006 to 2016 after the 2004-06 jump, about 1.86 at the end of 2020 and
# about 3.16 in mid-2024 (70% above end-2020, Eno Center's NHCCI tables). 2025 taken as 2024.
NHCCI = {2005: 1.40, 2012: 1.55, 2023: 3.00, 2024: 3.16, 2025: 3.16}
HWY_COST_LOW, HWY_COST_HIGH = 20.0, 150.0   # $M per lane-mile: suburban add-a-lane; urban core rebuild

LANES_PER_DIRECTION = 4      # the widened freeway before the project: 4 + 4 lanes, adding 1 each way
AADT = 200_000               # vehicles a day on the main lanes (I-35 central Austin ~180,000, TTI;
                             # 244,000 on Austin-area main lanes in 2018, TxDOT): 25,000 a lane
LANE_VPH = 2000              # vehicles an hour a lane at capacity (HCM: 2,000-2,400 passenger cars, less
                             # with trucks and in queues)
OCC = BEN["urban_car_occupancy"]          # 1.1, the plan's commute occupancy
DELAY_MIN_PER_MILE = 0.35    # average delay per vehicle-mile over the day on the segment: e.g. 40% of
                             # traffic in peaks at about twice free-flow time (0.9 min/mile). With AADT and
                             # OCC it is about 470,000 person-hours a mile a year, a Texas Top 100 congested
                             # segment (the No. 1, West Loop 610, ~0.9-1.7M a mile; TTI/TxDOT 2021-2025)
DELAY_HIGH = 0.70            # sensitivity: a segment as congested as the very worst in Texas
BPR_POWER = 4                # delay grows with (volume / capacity)^4 (BPR curve)
VOT = CFG["ridership"]["b_ivt_per_min"] / CFG["ridership"]["b_per_dollar"] * 60   # $12/h: the plan's own
VOT_USDOT = 13.45 * 1.36     # USDOT 2016 local all-purpose $13.45/h (2014 $) x CPI-U 2014-2025: ~$18.3/h
AGGLOM = BEN["agglomeration_share"]["urban"]                                      # 20%, as transit
EXT_NONCONG = BEN["car_externality_per_vkm"]["urban"]["crashes"] + \
    BEN["car_externality_per_vkm"]["urban"]["emissions"]                          # $0.10 a vehicle-km
ELASTICITY = 1.0             # vehicle-km per lane-km, long run: Duranton & Turner 2011 (~1.0 for metro
                             # interstates); Handy & Boarnet 2014 for CARB: long run 0.6-1.0
ELASTICITY_PARTIAL = 0.6
RAMP_YEARS = 10              # induced traffic phases in over a decade (Duranton & Turner use 10-year changes;
                             # Katy Freeway peak times were back above pre-widening levels within ~6 years)

# ---------------------------------------------------------------- transit (the plan's own)
TRIP_KM = BEN["urban_car_km_per_new_trip"]   # 12 km: a new transit trip's length, as the car trip it replaces
MODES = ("brt", "metro", "commuter", "streetcar")
MODE_NAME = {"brt": "BRT", "metro": "Metro / light rail", "commuter": "Regional rail", "streetcar": "Streetcar"}
MAX_HEADWAY = {"metro": 2.5, "brt": 2.0, "commuter": 10.0, "streetcar": 6.0}   # practical minimums, for scale
USER = 1 / tm.URBAN_B_PER_DOLLAR                  # $8 a new trip to its rider
CARKM = tm.URBAN_WIDER_PER_TRIP                   # $2.32: car-km off the road x $0.25
AGG_T = USER * BEN["agglomeration_share"]["urban"]  # $1.60


def lane_mile_costs():
    rows = []
    for name, cost, year, miles, lanes, note in HIGHWAY_PROJECTS:
        lm = miles * lanes
        idx = NHCCI[2025] / NHCCI[year]
        rows.append({"name": name, "cost": cost, "year": year, "lane_miles": lm, "nominal": cost / lm,
                     "musd_2025": cost * idx / lm, "note": note})
    return rows


def highway(cost_per_lane_mile, elasticity=0.0, delay=DELAY_MIN_PER_MILE, vot=VOT, ramp=RAMP_YEARS, ext=EXT_NONCONG):
    """Benefit-cost ratio and its parts for one lane-mile added (one more lane each way on a mile of a
    4 + 4 lane freeway: 2 lane-miles), over 50 years at 3%, the plan's horizon and rate."""
    g = 1.0 / LANES_PER_DIRECTION                            # capacity +25%
    person_h = AADT * OCC * 365 * delay / 60                 # delay a corridor-mile a year, person-hours
    vkm_day = AADT * MILE_KM
    pv_time = pv_induced_users = pv_ext = 0.0
    for t in range(1, 51):
        i = elasticity * g * min(t / ramp, 1.0)              # induced vehicle-km, share of today's
        saved = 1 - ((1 + i) / (1 + g)) ** BPR_POWER         # share of delay per vehicle removed
        d = 1.03 ** -t
        pv_time += person_h * saved * vot * (1 + AGGLOM) * d
        pv_induced_users += 0.5 * i * person_h * saved * vot * d        # rule of half
        pv_ext += i * vkm_day * 365 * ext * d
    per_lane = 1e-6 / 2                                       # $ a corridor-mile -> $M a lane-mile
    b = (pv_time + pv_induced_users - pv_ext) * per_lane
    year1 = person_h * (1 - (1 / (1 + g)) ** BPR_POWER) * vot * (1 + AGGLOM) * per_lane
    return {"bcr": b / cost_per_lane_mile, "pv_benefit": b, "pv_time": (pv_time + pv_induced_users) * per_lane,
            "pv_ext": pv_ext * per_lane, "year1": year1, "person_h": person_h}


# ---------------------------------------------------------------- transit lines
def lines():
    d = json.load(open(os.path.join(ROOT, "docs", "data", "timeline.json"), encoding="utf-8"))
    return [p for p in d["projects"] if p["layer"] == "urban"], d


def line_bcr(p, user=1.0, carkm=1.0, agg=1.0):
    """study/timing.py's ratio with the benefit parts scaled: travellers' gain, car-km avoided, agglomeration."""
    q = dict(p)
    q["benefit"] = p["benefit"] * user
    q["wider"] = p["wider"] * carkm
    q["agglom"] = p["agglom"] * agg * user
    return tm.ratio(q)


def breakeven_trips_per_musd(h, value):
    """New daily trips per $M of whole-life cost (capital + PV of operating cost) at which a line's ratio is h.
    ratio = trips*DAYS*value*PV / (K + (opex - trips*DAYS*fare)*PV); solved for trips / (K + opex*PV)."""
    return max(h, 0.0) * 1e6 / (DAYS * PV * (value + max(h, 0.0) * tm.URBAN_FARE))


def money(m):
    return f"${m / 1000:.1f}B" if abs(m) >= 1000 else f"${m:,.0f}M"


def main():
    P, tl = lines()
    hw_rows = lane_mile_costs()
    base_cost = st.median(r["musd_2025"] for r in hw_rows)
    by_mode = {m: [p for p in P if p["mode"] == m] for m in MODES}
    total_cap = sum(p["capital"] for p in P)
    v_all = USER + CARKM + AGG_T

    # ---- cases: (key, label, highway kwargs, transit scaling)
    cases = [
        ("base", "No induced demand (the lane's capacity view)", dict(cost_per_lane_mile=base_cost), {}),
        ("low", "No induced demand, cheap suburban lane (same congestion: generous)",
         dict(cost_per_lane_mile=HWY_COST_LOW), {}),
        ("high", "No induced demand, urban-core rebuild", dict(cost_per_lane_mile=HWY_COST_HIGH), {}),
        ("worst", "No induced demand, Texas's worst bottleneck (delay x2)",
         dict(cost_per_lane_mile=base_cost, delay=DELAY_HIGH), {}),
        ("usdot", "No induced demand, USDOT value of time for both",
         dict(cost_per_lane_mile=base_cost, vot=VOT_USDOT), {"user": VOT_USDOT / VOT}),
        ("half", "No induced demand, transit's wider benefits halved",
         dict(cost_per_lane_mile=base_cost), {"carkm": 0.5, "agg": 0.5}),
        ("partial", f"Partial induced demand (elasticity {ELASTICITY_PARTIAL})",
         dict(cost_per_lane_mile=base_cost, elasticity=ELASTICITY_PARTIAL), {}),
        ("law", f"Fundamental law (elasticity {ELASTICITY:.1f})",
         dict(cost_per_lane_mile=base_cost, elasticity=ELASTICITY), {}),
        ("law_noext", "Fundamental law, induced driving's crashes and emissions not charged",
         dict(cost_per_lane_mile=base_cost, elasticity=ELASTICITY, ext=0.0), {}),
        ("law_both", "Same, and transit's car-km benefits refill too",
         dict(cost_per_lane_mile=base_cost, elasticity=ELASTICITY, ext=0.0), {"carkm": 0.0}),
    ]
    res = {}
    for key, lab, hk, tk in cases:
        h = highway(**hk)
        value = USER * tk.get("user", 1.0) + CARKM * tk.get("carkm", 1.0) + AGG_T * tk.get("agg", 1.0) * tk.get("user", 1.0)
        bcrs = {p["id"]: line_bcr(p, **tk) for p in P}
        above = [p for p in P if bcrs[p["id"]] >= h["bcr"]]
        res[key] = {"label": lab, "h": h, "value": value, "bcrs": bcrs, "above": above,
                    "trips_per_musd": breakeven_trips_per_musd(h["bcr"], value)}
    for p in P:
        p["bcr_now"] = line_bcr(p)

    L = []
    A = L.append
    A("# Highway cutover: when is a transit dollar worth less than a dollar on widening?")
    A("")
    A("Generated by `python study/highway_cutover.py`. **Directional only.** One representative widened Texas urban "
      "freeway, valued with the plan's own framework (`study/timing.py`: 50 years at 3%, the plan's value of time, "
      "the same car externalities and agglomeration share), set against the plan's 143 urban lines at 2050 travel "
      "(`docs/data/timeline.json`). No network model of the highway: a BPR delay curve on one segment, with and "
      "without induced traffic.")
    A("")

    # ---- verdict first
    b, law, part = res["base"], res["law"], res["partial"]
    cap_above = sum(p["capital"] for p in b["above"])
    A("## Short answer")
    A("")
    A(f"- **The cutover is a benefit-cost ratio of about {b['h']['bcr']:.1f}** if a new lane kept its congestion "
      f"relief for 50 years (no induced traffic): a lane-mile at ${base_cost:.0f}M returns "
      f"${b['h']['pv_benefit']:.0f}M. In riders that is **about {b['trips_per_musd']:.0f} new daily transit trips "
      f"per $M of whole-life cost** (capital plus 50 years' operating cost), roughly "
      f"{b['trips_per_musd'] * (1 + st.median(p['opex'] / p['capital'] for p in P) * PV):.0f} per $M of capital. "
      f"{len(b['above'])} of the plan's {len(P)} urban lines ({money(cap_above)} of {money(total_cap)}, "
      f"{cap_above / total_cap:.0%} of the capital) clear it.")
    A(f"- **With induced traffic the cutover mostly disappears.** At the fundamental law's elasticity of "
      f"{ELASTICITY:.1f} (Duranton & Turner 2011) the lane fills within a decade, the time saved goes, and the extra "
      f"driving's crashes and emissions outweigh what is left: ratio {law['h']['bcr']:.2f}, below doing nothing, and "
      f"every line beats it. Not charging those crashes and emissions, the decade of relief alone is worth "
      f"{res['law_noext']['h']['bcr']:.2f} ({len(res['law_noext']['above'])} lines clear it). "
      f"At a partial elasticity of {ELASTICITY_PARTIAL} the cutover is {part['h']['bcr']:.2f} "
      f"({part['trips_per_musd']:.1f} trips per $M whole-life), and {len(part['above'])} lines "
      f"({sum(p['capital'] for p in part['above']) / total_cap:.0%} of the capital) clear it.")
    A("- **The capacity argument (a line carries far more than a lane) holds only at metro headways the plan doesn't run.** "
      "At the plan's headways a metro line's capacity is about two freeway lanes, regional rail one, BRT a third; and "
      "the money buys far fewer passenger-km than a lane carries (table 2). Transit's case rests on what each new rider "
      "is worth, and on induced demand eroding what a lane is worth.")
    A("- **Verdict: still on the right track against highway widening, but not by the margin the capacity argument "
      "suggests.** For the congested metro freeways where the plan's lines run, the evidence (fundamental law; the "
      "Katy Freeway) says widening buys little lasting relief, so the plan's lines beat it. If one believes a lane "
      f"keeps its relief, a typical widening (ratio ~{b['h']['bcr']:.1f}) beats most of the plan's lines (median ratio "
      f"{st.median(p['bcr_now'] for p in P):.2f}). Either way the weakest lines (ratios 0.1-0.2, table 4) lose to a "
      "widening in almost every case, and most lines are below 1 on their own: the stronger reason to trim them is "
      "that they don't return their cost, not highways.")
    hou = [p for p in P if p["metro"] == "houston"]
    A(f"- **Nearest and below the cutover:** Austin's, San Antonio's and a few small metros' first BRT lines and Austin's first metro "
      f"line clear even the no-induced-demand case; Houston's {len(hou)} lines "
      f"({money(sum(p['capital'] for p in hou))}, median ratio {st.median(p['bcr_now'] for p in hou):.2f}) have none "
      f"above it; regional rail (median {st.median(p['bcr_now'] for p in by_mode['commuter']):.2f}) and later outer "
      "BRT and metro extensions are the furthest below.")
    A("")

    # ---- 1. capacity and cost
    A("## 1. What a dollar buys: capital and capacity")
    A("")
    A("**Freeway lane-miles in Texas.** Whole-project cost over the through lanes added (both directions), so it "
      "includes the interchanges, drainage, frontage and right of way a lane needs in practice; indexed to 2025 with "
      "FHWA's National Highway Construction Cost Index (approximate levels, which roughly doubled 2020-2024).")
    A("")
    A("| Project | Cost as reported | Year | Lane-miles added | $M per lane-mile (nominal) | $M per lane-mile (2025) | Notes |")
    A("|---|---|---|---|---|---|---|")
    for r in hw_rows:
        A(f"| {r['name']} | {money(r['cost'])} | {r['year']} | {r['lane_miles']:.0f} | {r['nominal']:.0f} | "
          f"{r['musd_2025']:.0f} | {r['note']} |")
    A("")
    A(f"Used here: **${base_cost:.0f}M per lane-mile** (the median, ${base_cost / MILE_KM:.0f}M per lane-km), "
      f"${HWY_COST_LOW:.0f}M for a cheap suburban add-a-lane and ${HWY_COST_HIGH:.0f}M for an urban-core rebuild. "
      "Maintenance is left out (favours highways).")
    A("")
    lane_cap = LANE_VPH * OCC
    A(f"**Capacity, one direction.** A freeway lane: {LANE_VPH:,} vehicles an hour x {OCC} people = "
      f"**{lane_cap:,.0f} people an hour**. A line: vehicles an hour at its headway x vehicle capacity "
      "(`vendor/dfw-transit/config.json` modes). Capital per km for a line is both directions; for the freeway, "
      "one lane each way (2 lane-km).")
    A("")
    A("| | Capital per route-km (median of the plan's lines) | People an hour each way, at the plan's headway | Same, at a short headway | Freeway lanes equivalent (plan's headway) | $M per km per 1,000 people an hour |")
    A("|---|---|---|---|---|---|")
    A(f"| Freeway, +1 lane each way | ${2 * base_cost / MILE_KM:.0f}M | {lane_cap:,.0f} | {lane_cap:,.0f} | 1.0 | "
      f"{2 * base_cost / MILE_KM / lane_cap * 1000:.1f} |")
    for m in MODES:
        mc = CFG["modes"][m]
        hw = mc["default_headway_min"]
        cap = 60 / hw * mc["vehicle_capacity"]
        capmax = 60 / MAX_HEADWAY[m] * mc["vehicle_capacity"]
        ck = st.median(p["capital"] / p["km"] for p in by_mode[m])
        A(f"| {MODE_NAME[m]} (every {hw:g} min; {MAX_HEADWAY[m]:g} min) | ${ck:.0f}M | {cap:,.0f} | {capmax:,.0f} | "
          f"{cap / lane_cap:.1f} | {ck / cap * 1000:.1f} |")
    A("")
    A("Per dollar of capacity a freeway lane is in the same range as BRT and regional rail and cheaper than metro at the "
      "plan's headways. Rail's advantage is headroom: more trains cost operating money, not new right of way, and a "
      "metro line at 2-3 minute headways carries 4-5 lanes' worth.")
    A("")

    # ---- 2. use
    A("## 2. But capacity isn't use: passenger-km a day per $M of capital")
    A("")
    lane_pkm = AADT / (2 * LANES_PER_DIRECTION) * OCC          # per lane-km a day
    lane_per_musd = lane_pkm / (base_cost / MILE_KM)
    A(f"A Texas urban freeway lane carries about {AADT / (2 * LANES_PER_DIRECTION):,.0f} vehicles a day "
      f"({AADT:,} on 4 + 4 lanes), {lane_pkm:,.0f} passenger-km per lane-km: **{lane_per_musd:,.0f} passenger-km a "
      f"day per $M** at ${base_cost:.0f}M a lane-mile. The plan's lines carry their model's new daily trips (2050) x "
      f"{TRIP_KM} km:")
    A("")
    A("| Mode | Lines | Best | Median | Weakest kept | New daily trips per $M capital (median) |")
    A("|---|---|---|---|---|---|")
    for m in MODES:
        q = [p["trips_day"] * TRIP_KM / p["capital"] for p in by_mode[m]]
        A(f"| {MODE_NAME[m]} | {len(q)} | {max(q):,.0f} | {st.median(q):,.0f} | {min(q):,.0f} | "
          f"{st.median(p['trips_day'] / p['capital'] for p in by_mode[m]):.1f} |")
    allq = [p["trips_day"] * TRIP_KM / p["capital"] for p in P]
    A(f"| All urban lines | {len(P)} | {max(allq):,.0f} | {st.median(allq):,.0f} | {min(allq):,.0f} | "
      f"{st.median(p['trips_day'] / p['capital'] for p in P):.1f} |")
    A("")
    A(f"A dollar of lane carries several times the passenger-km of a dollar of the plan's lines (the median line "
      f"{st.median(allq) / lane_per_musd:.0%} as much). But the two numbers don't mean the same thing. The line's are "
      "*new* transit trips, mostly out of cars (each worth $8 to its rider in the plan's commute logit, $12 with the "
      "wider benefits). The lane's are mostly trips that were already being made: without induced traffic they are "
      "the same drivers, a little faster; with it (Duranton & Turner: vehicle-km rise about one for one with "
      "lane-km in US metros, from more driving by residents, more trucks and in-migration, little diverted from other "
      "roads) they are new trips worth barely more than their cost to the driver, and speeds go back to where they "
      "were. Houston's Katy Freeway, widened to 18-26 lanes for $2.8B by 2008, had peak travel times 30-55% longer by "
      "2014 than in 2011 (City Observatory, from TranStar data).")
    A("")

    # ---- 3. value
    A("## 3. The cutover")
    A("")
    h0 = b["h"]
    A(f"**The widening.** A 4 + 4 lane freeway, {AADT:,} vehicles a day, {DELAY_MIN_PER_MILE} minutes of delay per "
      f"vehicle-mile averaged over the day ({h0['person_h']:,.0f} person-hours a mile a year, a Texas Top 100 congested "
      f"segment). One more lane each way is +25% capacity; on a BPR curve (delay ~ (volume/capacity)^{BPR_POWER}) that "
      f"removes {1 - (1 / 1.25) ** BPR_POWER:.0%} of the delay. At the plan's value of time (${VOT:.0f}/h: the commute "
      f"model's 0.025 per minute over 0.125 per $, the same model that makes a new transit trip worth $8) plus 20% "
      f"agglomeration, as transit gets: ${h0['year1']:.2f}M a lane-mile a year, ${h0['pv_benefit']:.0f}M over 50 years. "
      f"Induced traffic (elasticity e, phased in over {RAMP_YEARS} years) refills the lane, takes back the saving, gets "
      f"the rule of half for its own drivers, and adds ${EXT_NONCONG:.2f} of crashes and emissions per vehicle-km "
      "(`texas/benefits.json`; its congestion is already in the delay curve).")
    A("")
    A(f"In the same money, a new transit trip's $8 is {USER / VOT * 60:.0f} minutes of in-vehicle time; the widening "
      f"saves each vehicle {(1 - (1 / 1.25) ** BPR_POWER) * DELAY_MIN_PER_MILE:.2f} minutes a mile, but for "
      f"{AADT:,} vehicles a day.")
    A("")
    A("**The line.** study/timing.py's ratio, unchanged: $8 a new trip to the rider, $2.32 of car-km avoided, $1.60 "
      "agglomeration, fares and operating cost, 2050 riders.")
    A("")
    A(f"**Break-even.** A line's ratio equals the highway's H when its new daily trips per $M of whole-life cost "
      f"(capital + 50 years' operating cost at 3%) = H x 10^6 / ({DAYS} x {PV:.1f} x (${v_all:.2f} + H x $1.25 fare)).")
    A("")
    A("| Case | Highway ratio (cutover) | Break-even new daily trips per $M whole-life | Per $M capital (median line) | Lines above | Capital above | Share of urban capital |")
    A("|---|---|---|---|---|---|---|")
    med_ok = st.median(p["opex"] / p["capital"] for p in P)
    for key, *_ in cases:
        r = res[key]
        ca = sum(p["capital"] for p in r["above"])
        A(f"| {r['label']} | {r['h']['bcr']:.2f} | {r['trips_per_musd']:.1f} | "
          f"{r['trips_per_musd'] * (1 + med_ok * PV):.1f} | {len(r['above'])} of {len(P)} | {money(ca)} | "
          f"{ca / total_cap:.0%} |")
    A("")
    A(f"For scale: the plan's own selection floor is 1.0 new daily trip per $M of capital plus 20 years' operating "
      f"cost (DFW Transit `metro/modelselect.py`), and a ratio of 1 (benefits equal costs) needs "
      f"{breakeven_trips_per_musd(1.0, v_all):.1f} per $M whole-life.")
    A("")

    # ---- by mode
    A("### Where the lines sit, by mode (2050 travel)")
    A("")
    A(f"Cutover: no induced demand {b['h']['bcr']:.2f}; partial induced demand {part['h']['bcr']:.2f}; fundamental law "
      f"{law['h']['bcr']:.2f}.")
    A("")
    A("| Mode | Lines | Capital | Ratio: best / median / weakest | Above, no induced demand | Capital above | Above, partial induced | Capital above |")
    A("|---|---|---|---|---|---|---|---|")

    def row(group, name):
        ab = [p for p in group if p["bcr_now"] >= b["h"]["bcr"]]
        ap = [p for p in group if p["bcr_now"] >= part["h"]["bcr"]]
        rs = [p["bcr_now"] for p in group]
        A(f"| {name} | {len(group)} | {money(sum(p['capital'] for p in group))} | {max(rs):.2f} / {st.median(rs):.2f} / "
          f"{min(rs):.2f} | {len(ab)} | {money(sum(p['capital'] for p in ab))} | {len(ap)} | "
          f"{money(sum(p['capital'] for p in ap))} |")
    for m in MODES:
        row(by_mode[m], MODE_NAME[m])
    row(P, "All urban lines")
    A("")

    # ---- by metro
    A("### By metro")
    A("")
    A("| Metro | Lines | Capital | Median ratio | Above, no induced demand | Capital above | Above, partial induced | Capital above |")
    A("|---|---|---|---|---|---|---|---|")
    metros = {}
    for p in P:
        metros.setdefault(p["metro_name"], []).append(p)
    for name, group in sorted(metros.items(), key=lambda kv: -sum(p["capital"] for p in kv[1])):
        ab = [p for p in group if p["bcr_now"] >= b["h"]["bcr"]]
        ap = [p for p in group if p["bcr_now"] >= part["h"]["bcr"]]
        A(f"| {name} | {len(group)} | {money(sum(p['capital'] for p in group))} | "
          f"{st.median(p['bcr_now'] for p in group):.2f} | {len(ab)} | {money(sum(p['capital'] for p in ab))} | "
          f"{len(ap)} | {money(sum(p['capital'] for p in ap))} |")
    dfw = tl["dfw"]
    dfw_bcr = (dfw["benefit"] + dfw["wider"]) * PV / (dfw["spent"] + max(-dfw["margin"], 0) * PV)
    A("")
    A(f"Dallas-Fort Worth's own plan (75 lines, valued the same way in `study/timing.py`, at 2100 travel): ratio "
      f"{dfw_bcr:.2f} as a whole, above the no-induced-demand cutover only if {dfw_bcr:.2f} >= {b['h']['bcr']:.2f}: "
      f"{'yes' if dfw_bcr >= b['h']['bcr'] else 'no'}. High-speed and conventional rail compete with rural interstate "
      "widening, which is cheaper per lane-mile but relieves little congestion; they are not compared here.")
    A("")

    # ---- best and weakest
    A("## 4. Lines nearest and furthest from the cutover")
    A("")
    srt = sorted(P, key=lambda p: -p["bcr_now"])
    A(f"**Above the no-induced-demand cutover ({b['h']['bcr']:.2f}):**")
    A("")
    A("| Line | Capital | New daily trips (2050) | Trips per $M whole-life | Ratio |")
    A("|---|---|---|---|---|")
    for p in [p for p in srt if p["bcr_now"] >= b["h"]["bcr"]]:
        A(f"| {tm.label(p)} | {money(p['capital'])} | {p['trips_day']:,.0f} | "
          f"{p['trips_day'] / (p['capital'] + p['opex'] * PV):.1f} | {p['bcr_now']:.2f} |")
    A("")
    weak = [p for p in srt if p["bcr_now"] < part["h"]["bcr"]]
    A(f"**Below even the partial-induced-demand cutover ({part['h']['bcr']:.2f}): {len(weak)} lines, "
      f"{money(sum(p['capital'] for p in weak))}.** By mode: " +
      ", ".join(f"{MODE_NAME[m]} {sum(1 for p in weak if p['mode'] == m)} "
                f"({money(sum(p['capital'] for p in weak if p['mode'] == m))})" for m in MODES
                if any(p["mode"] == m for p in weak)) + ". The weakest ten:")
    A("")
    A("| Line | Capital | km | New daily trips (2050) | Trips per $M whole-life | Ratio |")
    A("|---|---|---|---|---|---|")
    for p in srt[-10:][::-1]:
        A(f"| {tm.label(p)} | {money(p['capital'])} | {p['km']:.0f} | {p['trips_day']:,.0f} | "
          f"{p['trips_day'] / (p['capital'] + p['opex'] * PV):.1f} | {p['bcr_now']:.2f} |")
    A("")
    small = [p for p in P if p["metro"] not in ("houston", "san-antonio", "austin", "el-paso")]
    big = [p for p in P if p["metro"] in ("houston", "san-antonio", "austin", "el-paso")]
    A(f"Small-metro lines ({len(small)} outside outside the big four, {money(sum(p['capital'] for p in small))}) has a "
      f"median ratio of {st.median(p['bcr_now'] for p in small):.2f}, against {st.median(p['bcr_now'] for p in big):.2f} "
      "in Houston, San Antonio, Austin and El Paso: the small metros' few lines are their best corridors and cheap; "
      "but their freeways are also less congested, so a widening there would be worth less than the Top 100 segment "
      "assumed here, which helps them. Long regional rail (median ratio "
      f"{st.median(p['bcr_now'] for p in by_mode['commuter']):.2f}) and Houston's later metro and BRT lines are the "
      "furthest below.")
    A("")

    # ---- caveats
    A("## What this leaves out")
    A("")
    A("- One segment, not a network: no bottleneck shifting downstream (which lowers the highway's gain), no relief "
      "on parallel roads (which raises it), no reliability or vehicle operating savings (raises it a little).")
    A("- The highway's traffic is today's; by 2050 Texas metros grow 40-60%, which raises the delay a lane relieves "
      "and, with induced demand, how fast it refills. The lines are at 2050 travel.")
    A("- Transit's car-km benefits ($0.25 a km) assume the road space it frees stays free. The fundamental law says it "
      "refills too (Duranton & Turner find transit doesn't lower VKT), hence the last case.")
    A("- Managed (tolled or HOV) lanes, which most of the projects above are, can hold speeds with pricing and resist "
      "induced demand better than free lanes: closer to the no-induced-demand cases.")
    A("- Congestion pricing would beat both on congestion; neither the plan nor this note models it.")
    A("")
    A("## Sources")
    A("")
    A("- Duranton, G. and Turner, M. (2011), The Fundamental Law of Road Congestion: Evidence from US Cities, "
      "*American Economic Review* 101(6): 2616-52. https://economics.brown.edu/sites/g/files/dprerj726/files/news/Duranton_Turner_AER_2011.pdf")
    A("- Handy, S. and Boarnet, M. (2014), Impact of Highway Capacity and Induced Travel on Passenger Vehicle Use and "
      "Greenhouse Gas Emissions, policy brief and technical background for the California Air Resources Board. "
      "https://ww2.arb.ca.gov/sites/default/files/2020-06/Impact_of_Highway_Capacity_and_Induced_Travel_on_Passenger_Vehicle_Use_and_Greenhouse_Gas_Emissions_Technical_Background_Document.pdf")
    A("- TxDOT Mobility35 FAQ (Capital Express North $606M, South $548M, Central). https://www.txdot.gov/mobility35/about/faq.html ; "
      "TxDOT Texas Clear Lanes, Austin projects (Central $4.5B). https://www.txdot.gov/texasclearlanes/projects/austin.html ; "
      "Construction Equipment Guide, TxDOT starts $5.6B I-35 Capital Express Central. https://www.constructionequipmentguide.com/txdot-starts-56b-i-35-capital-express-central-road-project/66727")
    A("- NHHIP: Construction Dive (2024), I-45 Houston groundbreaking. https://www.constructiondive.com/news/i-45-houston-groundbreaking-flooding/730555/ ; "
      "Equipment World, TxDOT begins $13B overhaul of I-45. https://www.equipmentworld.com/roadbuilding/article/15707597/texas-dot-begins-13b-overhaul-of-i45-in-houston")
    A("- Katy Freeway: FHWA project profile https://www.fhwa.dot.gov/ipd/project_profiles/tx_katy_freeway.aspx ; "
      "H-GAC 2008 progress report https://h-gac.com/getmedia/c423bcbf-db09-4e49-9da3-e55f10e5db02/2008_progress_report ; "
      "City Observatory, Reducing congestion: Katy didn't (2015) https://cityobservatory.org/reducing-congestion-katy-didnt-2/")
    A("- LBJ Express: FHWA project profile ($2,645M, 13 miles). https://www.fhwa.dot.gov/ipd/project_profiles/tx_lbj_express.aspx")
    A("- FHWA National Highway Construction Cost Index https://www.fhwa.dot.gov/policy/otps/nhcci ; Eno Center, NHCCI "
      "tables (2024: ~70% above end-2020). https://enotrans.org/article/highway-construction-costs-dropped-slightly-in-spring-2024/")
    A("- TTI / TxDOT, Texas' Top 100 Congested Road Segments (person-hours of delay per mile). "
      "https://mobility.tamu.edu/project/texas-most-congested-roadways ; https://www.txdot.gov/projects/planning/top-100-congested-road-segments.html")
    A("- I-35 Austin traffic: TTI (180,000 a day, US 183 - SH 71) https://tti.tamu.edu/tag/traffic-modeling ; "
      "TxDOT fact sheet via Pulice (244,450 in 2018) https://www.pulice.com/news/highways/2025/i-35-capital-express-north-project-to-meet-austins-growing-population")
    A("- Highway Capacity Manual freeway lane capacity (2,250-2,400 passenger cars an hour at base conditions; HCM 2010).")
    A("- USDOT, Revised Departmental Guidance on Valuation of Travel Time (2016): local all-purpose $13.45/h (2014 $). "
      "https://www.transportation.gov/office-policy/transportation-policy/revised-departmental-guidance-valuation-travel-time-economic")
    A("")
    out = os.path.join(ROOT, "study", "highway_cutover.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"wrote {out}")
    for key, *_ in cases:
        r = res[key]
        print(f"  {key:9s} H={r['h']['bcr']:.2f} trips/$M={r['trips_per_musd']:.1f} above={len(r['above'])}")
    return res


if __name__ == "__main__":
    main()
