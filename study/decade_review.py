"""The Auditor's decade review (study/hsr_buildout.md, guardrails and Phase 5).

    python study/decade_review.py [SCENARIO]       (default: whole_map)

Reads the plan as scheduled (docs/data/timeline.json, from study/timing.py) and, for every decade from
2030 to 2100, lists the intercity projects due to start and checks each against the guardrails:

  gate 2   a branch starts only after the corridor it hangs off has run three years
           (and, once there are riders to count, carried at least 80% of its forecast)
  gate 3   approval needs a ratio of at least 0.8 under the stress (cost x1.45, riders x0.70), or a
           connectivity designation (the Connectivity Program)
  money    the program's own corridors are funded from the program, not the statewide budget

Observed riders, when there are any, go in data/observed/ridership.csv (project_id, year,
trips_year); until then gate 2's ridership half reads "awaiting riders". Writes
study/decade_review.md: proceed, proceed with a designation, or hold, for each project.
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_YEARS, GATE_SHARE, STRESS_MIN = 3, 0.8, 0.8


def observed():
    path = os.path.join(ROOT, "data", "observed", "ridership.csv")
    out = {}
    if os.path.exists(path):
        for r in csv.DictReader(open(path, encoding="utf-8")):
            out.setdefault(r["project_id"], {})[int(r["year"])] = float(r["trips_year"])
    return out


def review(T, scen):
    S = T["scenarios"][scen]
    when = S["when"]
    P = {p["id"]: p for p in T["projects"]}
    for p in T.get("whole_map_projects", []) if scen == "whole_map" else []:
        P[p["id"]] = {**P.get(p["id"], {}), **p}
    obs = observed()
    rows = []
    for pid, (start, opens) in sorted(when.items(), key=lambda kv: kv[1][0]):
        p = P.get(pid)
        if not p or p["layer"] == "urban":
            continue
        deps = [d for d in p.get("after", []) if d in P]
        gate2, notes, slip = "pass", [], start
        for d in deps:
            dopen = (when.get(d) or [None, None])[1]
            if dopen is None:
                gate2 = "hold"
                notes.append(f"{P[d]['name'].split(':')[0]} not built")
                continue
            if start < dopen + GATE_YEARS:
                gate2 = "hold"
                slip = max(slip, dopen + GATE_YEARS)
                notes.append(f"starts {start}, {start - dopen:+d} years after {P[d]['name'].split(':')[0]} opens ({dopen})")
            seen = obs.get(d, {})
            yrs = [y for y in seen if dopen <= y < start]
            if yrs:
                fc = P[d].get("trips_year") or 0
                share = sum(seen[y] for y in yrs) / len(yrs) / fc if fc else 0
                if share < GATE_SHARE:
                    gate2 = "hold"
                    notes.append(f"{P[d]['name'].split(':')[0]} carries {share:.0%} of forecast")
            elif dopen <= 2026:
                pass
            else:
                notes.append(f"awaiting riders on {P[d]['name'].split(':')[0]}")
        stress = p.get("bcr_stress")
        designated = pid in T.get("connectivity", []) and scen == "whole_map"
        gate3 = "pass" if (stress or 0) >= STRESS_MIN else ("designated" if designated else "fail")
        verdict = ("hold" if gate2 == "hold" else "proceed" if gate3 == "pass" else
                   "proceed (connectivity)" if gate3 == "designated" else "right-of-way and design only: fails the stress gate")
        rows.append({"decade": start // 10 * 10, "id": pid, "name": p["name"], "start": start, "opens": opens,
                     "ratio": p.get("bcr"), "stress": stress, "gate2": gate2, "slip_to": slip, "gate3": gate3, "verdict": verdict,
                     "notes": "; ".join(notes)})
    return rows


def to_pass(stress):
    """How much better than today's estimate a project's numbers must come in to clear the stress gate: the
    ratio scales with riders and inversely with cost (the operating deficit aside)."""
    if stress is None or stress >= STRESS_MIN:
        return ""
    k = STRESS_MIN / max(stress, 1e-9)
    return f"costs {1 - 1 / k:.0%} under the estimate, or riders {k - 1:.0%} over it" if k < 20 else "out of reach"


def urban_gate(T, scen):
    """The metro lines against the same gate (study/third_session.md, item 1): how many pass, and by how much the rest miss."""
    when = T["scenarios"][scen]["when"]
    ps = [p for p in T["projects"] if p["layer"] == "urban" and p["id"] in when and p.get("bcr_stress") is not None]
    ok = [p for p in ps if p["bcr_stress"] >= STRESS_MIN]
    ks = sorted(STRESS_MIN / max(p["bcr_stress"], 1e-9) for p in ps if p["bcr_stress"] < STRESS_MIN)
    return len(ps), ok, ks


def main():
    scen = sys.argv[1] if len(sys.argv) > 1 else "whole_map"
    T = json.load(open(os.path.join(ROOT, "docs", "data", "timeline.json"), encoding="utf-8"))
    rows = review(T, scen)
    L = ["# Decade review", "",
         f"Generated by `python study/decade_review.py {scen}` from `docs/data/timeline.json` "
         f"({T['scenarios'][scen]['label']}). The Auditor's guardrails (`study/hsr_buildout.md`): a branch starts only "
         f"after its trunk has run {GATE_YEARS} years (and carried {GATE_SHARE:.0%} of its forecast, once there are riders "
         f"to count: `data/observed/ridership.csv`); approval needs a ratio of {STRESS_MIN} under the stress (cost x1.45, "
         "riders x0.70) or a connectivity designation. Intercity projects only; each metro's lines are reviewed by its "
         "own agency.", ""]
    for dec in sorted({r["decade"] for r in rows}):
        L += [f"## {dec}s", "", "| Project | Starts | Opens | Ratio | Under stress | Gate 2 (trunk first) | Gate 3 | Verdict | To pass the gate | Notes |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for r in (r for r in rows if r["decade"] == dec):
            L.append(f"| {r['name']} | {r['start']} | {r['opens']} | {r['ratio']:.2f} | "
                     f"{r['stress']:.2f} | {r['gate2']} | {r['gate3']} | {r['verdict']} | {to_pass(r['stress'])} | {r['notes']} |"
                     if r["ratio"] is not None and r["stress"] is not None else
                     f"| {r['name']} | {r['start']} | {r['opens']} | | | {r['gate2']} | {r['gate3']} | {r['verdict']} | | {r['notes']} |")
        L.append("")
    holds = [r for r in rows if r["gate2"] == "hold"]
    L += ["## What the review changes", "",
          (f"{len(holds)} project(s) start before the corridor they hang off has run {GATE_YEARS} years: the schedule "
           "lets a branch be built alongside its trunk to open no earlier than it, which the gate doesn't allow. Held to "
           f"the gate, each starts {GATE_YEARS} years after its trunk opens: "
           + ", ".join(f"{r['name'].split(':')[0]} (starts {r['start']}, held to {r['slip_to']})" for r in holds) + "."
           if holds else "Every project passes gate 2 as scheduled: the whole map's schedule applies the gate itself (`study/timing.py` GATE_YEARS)."), "",
          (lambda fail, n: f"{len(fail)} of {n} projects fail the stress gate without a designation"
           + (": every one that isn't in the Connectivity Program" if len(fail) == sum(1 for r in rows if r["gate3"] != "designated") else "")
           + (f" ({', '.join(fail)})" if fail else "")
           + (". Under the governor's rule (`study/second_session.md`, item 2) each gets its right-of-way protected and "
              "its design done, and no construction money, until it passes the gate at current costs and riders or the "
              "Legislature designates it by name. Read strictly, the gate would stop them all, the Triangle included: at "
              "cost x1.45 and riders x0.70 no corridor in the plan clears 0.8 (`study/hsr_buildout.md`, Phase 1 results), "
              "so the designations are where the decisions are made." if fail else "."))(
              [r["name"].split(":")[0] for r in rows if r["gate3"] == "fail"], len(rows)), ""]
    n, ok, ks = urban_gate(T, scen)
    if n:
        med = ks[len(ks) // 2] if ks else None
        L += ["## The binding gate (third session)", "",
              "The governor's rule since the third session (`study/third_session.md`, items 1 and 10): every corridor and "
              "every metro line keeps its place in the plan and gets its design and right-of-way, but signs construction only "
              f"when its refreshed cost estimate (at 30% design) and refreshed forecast clear {STRESS_MIN} under the stress; "
              "a metro line also waits until its city has zoned its station districts by right, and the refreshed forecast "
              "uses the zoning the city has actually adopted. The money of a project that fails waits in the fund for the "
              "next decade's review. The **To pass the gate** column says how much better than today's estimate a "
              "project's numbers must come in.", "",
              f"**The metro lines** under the same gate: {len(ok)} of {n} pass "
              + (f"({', '.join(p['name'] for p in ok)})" if ok else "") + "."
              + (f" The median of the rest needs costs {1 - 1 / med:.0%} under the estimate or riders {med - 1:.0%} over it." if med else ""), ""]
    with open(os.path.join(ROOT, "study", "decade_review.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
