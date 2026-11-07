"""Houston west: should high-speed rail from Houston to Austin and to San Antonio be one combined
line instead of the separate corridors in texas/hsr.py (US 290 to Austin, I-10 to San Antonio)?

    python study/hsr_houston_west.py

Each alternative is a set of track links and service patterns (trains and how often they run).
Where trains split at a junction, each branch gets half the trunk's trains: the model's one
headway is replaced by the patterns' own (texas/intercity.py, RailNetwork `services`). Every
alternative is run on its own and on top of the rest of the first four corridors (I-35 north
Dallas - Austin and Dallas - Shreveport), in 2050 with induced trips, as study/hsr_options.py
does. Writes study/hsr_houston_west.md.
"""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "study"))
from texas import hsr, intercity as ic  # noqa: E402
import hsr_options  # noqa: E402

YEAR = 2050
HEADWAY = 30            # minutes: p["hsr"]["headway_min"], the trunk's trains
BRANCH = 2 * HEADWAY    # each branch of a wye gets half of them

# New station sites (lat, lon, kind), at towns on the roads the lines would follow.
EXTRA = {
    "Giddings": (30.183, -96.936, "minor"),          # US 290 at US 77: where a US 290 line would split
    "Flatonia": (29.687, -97.108, "minor"),          # I-10 at SH 95: where an I-10 line would split
    "La Grange": (29.906, -96.876, "minor"),         # SH 71, on the straight line Houston - Lockhart
    "Lockhart": (29.885, -97.670, "minor"),          # US 183: 43 km from Austin, 95 from San Antonio
    "College Station": (30.615, -96.335, "minor"),   # Texas A&M: the Texas T-Bone's Houston leg
}

H, BR, AU, SM, SA = "Houston", "Brenham", "Austin", "San Marcos", "San Antonio"
US290, I35S, I10 = hsr.CORRIDORS["US290"][1], hsr.CORRIDORS["I35S"][1], hsr.CORRIDORS["I10"][1]

# id: (name, [(service pattern: chain of stations, headway minutes)]); track is every link a
# pattern uses.
ALTERNATIVES = {
    "A": ("One line Houston - Brenham - Austin - San Marcos - San Antonio (US 290 + I-35 south)",
          [([H, BR, AU, SM, SA], HEADWAY)]),
    "S": ("Separate lines: US 290 + I-35 south + I-10",
          [(US290, HEADWAY), (I35S, HEADWAY), (I10, HEADWAY)]),
    "B1": ("Wye at Giddings: Houston - Brenham - Giddings, branches to Austin and to Seguin - San Antonio; "
           "plus I-35 south",
           [([H, BR, "Giddings", AU], BRANCH), ([H, BR, "Giddings", "Seguin", SA], BRANCH), (I35S, HEADWAY)]),
    "B2": ("Wye at Flatonia: Houston - Columbus - Flatonia, branches to Austin and to Seguin - San Antonio; "
           "plus I-35 south",
           [([H, "Columbus", "Flatonia", AU], BRANCH), ([H, "Columbus", "Flatonia", "Seguin", SA], BRANCH),
            (I35S, HEADWAY)]),
    "B3": ("Wye at Lockhart, no I-35 south: Houston - La Grange - Lockhart, branches to Austin and to "
           "San Marcos - San Antonio; Austin - San Antonio trains through Lockhart",
           [([H, "La Grange", "Lockhart", AU], BRANCH), ([H, "La Grange", "Lockhart", SM, SA], BRANCH),
            ([AU, "Lockhart", SM, SA], HEADWAY)]),
    "C1": ("I-10 line with an Austin branch at Columbus (along SH 71); plus I-35 south",
           [(I10, BRANCH), ([H, "Columbus", AU], BRANCH), (I35S, HEADWAY)]),
    "C2": ("I-10 line, Austin via a Seguin - San Marcos link; plus I-35 south",
           [(I10, BRANCH), ([H, "Columbus", "Seguin", SM, AU], BRANCH), (I35S, HEADWAY)]),
    "C3": ("Triangle as usually drawn: I-10 + I-35 south (Houston - Austin via San Antonio)",
           [(I10, HEADWAY), (I35S, HEADWAY)]),
    "D": ("Texas T-Bone: Houston - College Station - Temple - Austin - San Marcos - San Antonio",
          [([H, "College Station", "Temple", AU, SM, SA], HEADWAY)]),
}
REST = [(hsr.CORRIDORS["I35N"][1], HEADWAY), (hsr.CORRIDORS["SHV"][1], HEADWAY)]   # the rest of the first four
PAIRS = [(H, AU), (H, SA), (AU, SA)]


def site(name):
    return EXTRA[name] if name in EXTRA else hsr.STATIONS[name]


def links_of(patterns):
    """{sorted station pair: track km} over every link a pattern runs on."""
    out = {}
    for chain, _ in patterns:
        for a, b in zip(chain, chain[1:]):
            out[tuple(sorted((a, b)))] = ic.km(site(a)[:2], site(b)[:2]) * hsr.TRACK_FACTOR
    return out


def stations_of(patterns):
    return {s for chain, _ in patterns for s in chain}


def capital_musd(patterns, cost_per_km=hsr.COST_PER_KM, built=()):
    """Capital ($M) as hsr.capital_musd: track x cost per km plus stations, leaving out what's in `built`."""
    have, have_st = links_of(built), stations_of(built)
    track = sum(t for k, t in links_of(patterns).items() if k not in have)
    return track * cost_per_km + sum(hsr.STATION_COST[site(s)[2]] for s in stations_of(patterns) - have_st)


def track_km(patterns, built=()):
    have = links_of(built)
    return sum(t for k, t in links_of(patterns).items() if k not in have)


def opex_musd(patterns, built=()):
    """Operating cost a year ($M), as hsr.opex_musd but per pattern: each pattern's trains over its
    own length, plus upkeep of the track. With `built`, the patterns' cost minus built's."""
    def cost(pats):
        lk = links_of(pats)
        train_km = sum(2 * sum(lk[tuple(sorted(k))] for k in zip(c, c[1:])) * hsr.SERVICE_HOURS * 60 / h
                       for c, h in pats)
        return train_km * 365 * hsr.OPEX_PER_TRAIN_KM / 1e6 + sum(lk.values()) * hsr.MAINTENANCE_PER_KM
    return cost(list(patterns) + list(built)) - (cost(built) if built else 0.0)


def network(patterns, p):
    lk = links_of(patterns)
    return ic.RailNetwork({s: site(s)[:2] for s in stations_of(patterns)}, [(a, b, t) for (a, b), t in lk.items()],
                          p["hsr"], services=patterns)


def evaluate(patterns, tx, zones, p, growth):
    """(rail trips a day incl. induced, travellers' gain $ a day, the network)."""
    net = network(patterns, p)
    res = ic.run(tx, zones, p, net, growth)
    return (sum(r["new"]["rail"] + r["new"]["induced"] for r in res.values()),
            sum(r["benefit_usd"] for r in res.values()), net)


def times(net):
    """'in-vehicle minutes / every N minutes' for the three pairs."""
    out = []
    for a, b in PAIRS:
        t = net.path(a, b)
        out.append(f"{t[0]:.0f} / {net.headway(a, b):.0f}" if t else "-")
    return out


def with_headways(patterns, to_austin, to_san_antonio):
    """The same patterns with Houston's trains to Austin every `to_austin` minutes and those to
    San Antonio every `to_san_antonio`; patterns not calling at Houston unchanged."""
    return [(c, (to_austin if c[-1] == AU else to_san_antonio) if H in c else h) for c, h in patterns]


def main():
    p = ic.load_params()
    assert p["hsr"]["headway_min"] == HEADWAY
    zones = ic.load_zones()
    base = ic.base_trips(zones, p)
    tx = {k: v for k, v in base.items() if "TX" in (zones[k[0]]["state"], zones[k[1]]["state"])}
    growth = ic.zone_growth(zones, YEAR)
    yr = 365 / 1e6

    # one headway everywhere reproduces study/hsr_options.py
    for alt, ids in (("A", ["US290", "I35S"]), ("S", ["US290", "I35S", "I10"])):
        mine = evaluate(ALTERNATIVES[alt][1], tx, zones, p, growth)[0]
        theirs = hsr_options.evaluate(ids, tx, zones, p, growth)[0]
        assert abs(mine - theirs) < 1e-6 * theirs, (alt, mine, theirs)
        assert abs(capital_musd(ALTERNATIVES[alt][1]) - hsr.capital_musd(ids)) < 1e-6
        assert abs(opex_musd(ALTERNATIVES[alt][1]) - hsr.opex_musd(ids, HEADWAY)) < 1e-6

    rest_trips, rest_gain, _ = evaluate(REST, tx, zones, p, growth)
    rows = {}
    for alt, (name, pats) in ALTERNATIVES.items():
        trips, gain, net = evaluate(pats, tx, zones, p, growth)
        t2, g2, net2 = evaluate(pats + REST, tx, zones, p, growth)
        rows[alt] = {"name": name, "km": track_km(pats), "cap": capital_musd(pats), "opex": opex_musd(pats),
                     "trips": trips * yr, "gain": gain * yr, "times": times(net),
                     "cap2": capital_musd(pats, built=REST), "km2": track_km(pats, built=REST),
                     "opex2": opex_musd(pats, built=REST),
                     "trips2": (t2 - rest_trips) * yr, "gain2": (g2 - rest_gain) * yr, "net2": t2 * yr,
                     "times2": times(net2)}
        r = rows[alt]
        print(f"{alt:3s} ${r['cap'] / 1000:5.1f}B {r['trips']:5.1f}M {r['gain']:6.0f}  "
              f"on top: ${r['cap2'] / 1000:5.1f}B +{r['trips2']:5.1f}M +{r['gain2']:6.0f}  {r['times']}")

    def per_b(x, cap):
        return x / (cap / 1000)

    out = ["# Houston west: one line or two?", "",
           "Generated by `python study/hsr_houston_west.py`. `texas/hsr.py` runs two lines west from Houston: "
           "US 290 to Austin (Houston - Brenham - Austin) and I-10 to San Antonio (Houston - Columbus - Seguin - "
           "San Antonio), next to I-35 south (Austin - San Marcos - San Antonio). In `study/hsr_options.md` I-35 south "
           "ranks first, US 290 second and I-10 ninth (+2.8M trips a year for $30.3B once the others exist). This "
           "tests whether one combined line serves Houston better per dollar.", "",
           "**Method.** Each alternative is a set of service patterns: a chain of stations and how often its trains "
           f"run. Track is every link a pattern uses, costed as `texas/hsr.py` does (${hsr.COST_PER_KM:.0f}M per track "
           f"km, track km = straight-line km between neighbouring stations x {hsr.TRACK_FACTOR}, a major station "
           f"${hsr.STATION_COST['major']:.0f}M and a minor one ${hsr.STATION_COST['minor']:.0f}M). Demand is "
           f"`texas/intercity.py` in {YEAR} with trend growth and induced trips, as in `study/hsr_options.py`; trips "
           "a year include induced trips, and travellers' gain is the sum of `benefit_usd` x 365 (consumer surplus, "
           f"induced trips' own gain left out). Where a line splits, each branch gets half the trunk's trains: the "
           f"trunk runs every {HEADWAY} minutes and each branch every {BRANCH}. The model's one network headway is "
           "replaced by the patterns' own (`RailNetwork(..., services=...)`): a trip waits for the trains of every "
           "pattern calling at both its stations, half the headway, capped at "
           f"{p['hsr']['max_wait_min']} minutes; a trip no single pattern serves (Dallas - Houston via Austin, say) "
           "waits for the least frequent link of its route, with no transfer penalty, as elsewhere in the model. "
           "Operating cost is `texas/hsr.py`'s rate per train-km, counted per pattern, so a wye's branches run half "
           "the trains. With one headway everywhere, the script reproduces `study/hsr_options.py` for A and S.", "",
           "**Geography.** From Houston (Texas Central's Northwest Mall site) Austin is 226 km west-northwest and "
           "San Antonio 296 km west; they are 118 km apart. The angle between them seen from Houston is small, so a "
           "shared trunk can run a long way west before splitting. Junctions are at towns on the roads a line would "
           "follow, and are stations ($150M each): Giddings (US 290 trunk via Brenham, 151 km from Houston, "
           "the Austin branch carrying on along US 290 and the San Antonio branch heading south-west to Seguin), "
           "Flatonia (I-10 trunk via Columbus, 160 km; the Austin branch north-west past Bastrop, the San Antonio "
           "branch on along I-10), Columbus (I-10, 105 km; the Austin branch along SH 71 through La Grange and "
           "Bastrop, which lie on the straight line) and Lockhart (214 km, via La Grange, which lies on the straight "
           "line; 43 km from Austin and 100 from San Antonio via San Marcos, the junction closest to both). B3 alone drops I-35 south: Austin - San Antonio trains run through a "
           "triangle junction at Lockhart. C2 reaches Austin from the I-10 line over a 35 km Seguin - San Marcos "
           "link and I-35 south. C3 is the Texas Triangle as it is usually drawn on maps: Houston - San Antonio "
           "direct and Austin on I-35, with no Houston - Austin line. D is the Texas T-Bone of the Texas High Speed "
           "Rail and Transportation Corporation (2000s): an I-35 spine from Dallas - Fort Worth to San Antonio, with "
           "Houston's leg joining it near Temple and Killeen via College Station.", ""]

    out += ["### The alternatives", "",
            "Travel times are in-vehicle minutes between the downtown stations, including stops, then how often trains "
            "run (minutes between trains) for that trip, built alone.", "",
            "| | Configuration | Track km | Capital | Houston - Austin | Houston - San Antonio | Austin - San Antonio |",
            "|---|---|---|---|---|---|---|"]
    for alt, r in rows.items():
        out.append(f"| {alt} | {r['name']} | {r['km']:,.0f} | ${r['cap'] / 1000:.1f}B | " + " | ".join(r["times"]) + " |")

    out += ["", "### Built alone", "",
            "| | Capital | Operating cost a year | Trips a year | Travellers' gain a year | Trips per $B | Gain per $B |",
            "|---|---|---|---|---|---|---|"]
    for alt, r in rows.items():
        out.append(f"| {alt} | ${r['cap'] / 1000:.1f}B | ${r['opex']:,.0f}M | {r['trips']:.1f}M | ${r['gain']:,.0f}M | "
                   f"{per_b(r['trips'], r['cap']):.2f}M | ${per_b(r['gain'], r['cap']):.0f}M |")

    out += ["", f"### On top of I-35 north (Dallas - Austin) and Dallas - Shreveport", "",
            f"The rest of the first four corridors alone: {rest_trips * yr:.1f}M trips a year, ${rest_gain * yr:,.0f}M "
            "of travellers' gain. Capital, operating cost, trips and gain are what the Houston-west alternative adds "
            "(D shares Temple - Austin with I-35 north). Dallas - Houston trips ride through Austin (or Temple), "
            "since Texas Central is not in this network.", "",
            "| | Capital added | Operating cost added | Trips a year added | Gain a year added | Trips per $B | "
            "Gain per $B | Network trips a year |", "|---|---|---|---|---|---|---|---|"]
    for alt, r in rows.items():
        out.append(f"| {alt} | ${r['cap2'] / 1000:.1f}B | ${r['opex2']:,.0f}M | {r['trips2']:.1f}M | ${r['gain2']:,.0f}M | "
                   f"{per_b(r['trips2'], r['cap2']):.2f}M | ${per_b(r['gain2'], r['cap2']):.0f}M | {r['net2']:.1f}M |")

    a = rows["A"]
    out += ["", "### Against the one line (A)", "",
            "What each alternative adds over A, on top of I-35 north and Dallas - Shreveport: the price of a faster "
            "Houston - San Antonio (or the saving, where it is negative).", "",
            "| | Extra capital | Extra trips a year | Extra gain a year | Extra trips per $B | Extra gain per $B |",
            "|---|---|---|---|---|---|"]
    for alt, r in rows.items():
        if alt == "A":
            continue
        dc, dt, dg = r["cap2"] - a["cap2"], r["trips2"] - a["trips2"], r["gain2"] - a["gain2"]
        ratio = (f"{per_b(dt, dc):.2f}M | ${per_b(dg, dc):.0f}M" if dc > 0 else "- | -")
        out.append(f"| {alt} | ${dc / 1000:+.1f}B | {dt:+.1f}M | ${dg:+,.0f}M | {ratio} |")

    out += ["", "### Cost per km", "",
            "On top of I-35 north and Dallas - Shreveport (trips and gain don't depend on the cost).", "",
            "| | $60M per km: capital, trips per $B, gain per $B | $110M per km: capital, trips per $B, gain per $B |",
            "|---|---|---|"]
    for alt, r in rows.items():
        cells = []
        for cpk in (60.0, 110.0):
            c = capital_musd(ALTERNATIVES[alt][1], cpk, built=REST)
            cells.append(f"${c / 1000:.1f}B, {per_b(r['trips2'], c):.2f}M, ${per_b(r['gain2'], c):.0f}M")
        out.append(f"| {alt} | " + " | ".join(cells) + " |")

    out += ["", "### Robustness: with Texas Central built too", "",
            "The same, on top of I-35 north, Dallas - Shreveport and Texas Central (Dallas - Houston no longer rides "
            "through Austin or Temple).", "",
            "| | Capital added | Trips a year added | Gain a year added | Trips per $B | Gain per $B |",
            "|---|---|---|---|---|---|"]
    rest_tc = REST + [(hsr.CORRIDORS["TC"][1], HEADWAY)]
    tc_trips, tc_gain, _ = evaluate(rest_tc, tx, zones, p, growth)
    for alt, (name, pats) in ALTERNATIVES.items():
        t3, g3, _ = evaluate(pats + rest_tc, tx, zones, p, growth)
        c3, t3, g3 = capital_musd(pats, built=rest_tc), (t3 - tc_trips) * yr, (g3 - tc_gain) * yr
        rows[alt]["per_b_tc"] = per_b(t3, c3)
        out.append(f"| {alt} | ${c3 / 1000:.1f}B | {t3:.1f}M | ${g3:,.0f}M | {per_b(t3, c3):.2f}M | ${per_b(g3, c3):.0f}M |")

    out += ["", "### How much the split costs the wyes", "",
            f"On top of I-35 north and Dallas - Shreveport, with other frequencies for Houston's trains. *60 / 60*: "
            f"each branch every {BRANCH} minutes, as above. *30 / 60*: Houston - Austin trains every {HEADWAY} minutes "
            f"and Houston - San Antonio every {BRANCH} (trunk every {HEADWAY * 2 // 3}). *30 / 30*: both every "
            f"{HEADWAY}, the trunk twice as busy (every {HEADWAY // 2}). Operating cost is what the alternative adds. "
            f"*One headway (naive)*: the 60 / 60 trains, but every trip waits as if trains ran every {HEADWAY} "
            "minutes: what the model says without service patterns.", "",
            "| | 60 / 60: trips, gain, operating cost | 30 / 60: trips, gain, operating cost | "
            "30 / 30: trips, gain, operating cost | One headway (naive): trips, gain |", "|---|---|---|---|---|"]
    for alt in ("B1", "B2", "B3", "C1", "C2"):
        r, pats = rows[alt], ALTERNATIVES[alt][1]
        cells = [f"{r['trips2']:.1f}M, ${r['gain2']:,.0f}M, ${r['opex2']:,.0f}M"]
        for h_au, h_sa in ((HEADWAY, BRANCH), (HEADWAY, HEADWAY)):
            q = with_headways(pats, h_au, h_sa)
            t_q, g_q, _ = evaluate(q + REST, tx, zones, p, growth)
            r[f"split_{h_au}_{h_sa}"] = ((t_q - rest_trips) * yr, (g_q - rest_gain) * yr, opex_musd(q, built=REST))
            cells.append(f"{(t_q - rest_trips) * yr:.1f}M, ${(g_q - rest_gain) * yr:,.0f}M, "
                         f"${opex_musd(q, built=REST):,.0f}M")
        net = ic.RailNetwork({s: site(s)[:2] for s in stations_of(pats + REST)},
                             [(x, y, t) for (x, y), t in links_of(pats + REST).items()], p["hsr"])
        res = ic.run(tx, zones, p, net, growth)
        t_n = sum(v["new"]["rail"] + v["new"]["induced"] for v in res.values())
        g_n = sum(v["benefit_usd"] for v in res.values())
        cells.append(f"{(t_n - rest_trips) * yr:.1f}M, ${(g_n - rest_gain) * yr:,.0f}M")
        out.append(f"| {alt} | " + " | ".join(cells) + " |")

    out += ["", "### Demand assumptions", "",
            "Trips per $B on top of I-35 north and Dallas - Shreveport, with rail's constant against car and the "
            "induced trips changed (`texas/intercity.json`; as above: constant -0.5, induced 10%).", "",
            "| | As above | Constant 0 | Constant -1.0 | No induced trips |", "|---|---|---|---|---|"]
    sens = {}
    for label, key, val in (("asc0", "asc_vs_car", 0.0), ("asc1", "asc_vs_car", -1.0), ("ind0", "induced_share", 0.0)):
        q = copy.deepcopy(p)
        q["hsr"][key] = val
        t0 = evaluate(REST, tx, zones, q, growth)[0]
        sens[label] = {alt: (evaluate(pats + REST, tx, zones, q, growth)[0] - t0) * yr / (rows[alt]["cap2"] / 1000)
                       for alt, (_, pats) in ALTERNATIVES.items()}
    for alt, r in rows.items():
        out.append(f"| {alt} | {per_b(r['trips2'], r['cap2']):.2f}M | " +
                   " | ".join(f"{sens[k][alt]:.2f}M" for k in ("asc0", "asc1", "ind0")) + " |")

    pair_zones = [("Austin", "12420_TX"), ("Houston", "26420_TX"), ("San Antonio", "41700_TX"),
                  ("Dallas", "19100_TX"), ("rural TX (E)", "RTX10_TX")]
    z = dict(pair_zones)
    shown = [("Houston", "Austin"), ("Houston", "San Antonio"), ("Austin", "San Antonio"), ("Dallas", "Houston"),
             ("Houston", "rural TX (E)")]
    by_pair = {}
    for alt in ("A", "S", "B1"):
        res = ic.run(tx, zones, p, network(ALTERNATIVES[alt][1] + REST, p), growth)
        by_pair[alt] = {k: res[tuple(sorted((z[k[0]], z[k[1]])))] for k in shown}
    out += ["", "### Where the wye loses", "",
            "Rail trips a year for some pairs, on top of I-35 north and Dallas - Shreveport: the one line (A), the "
            "separate lines (S) and the best wye (B1, branches every 60 minutes).", "",
            "| Pair | A | S | B1 |", "|---|---|---|---|"]
    for k in shown:
        out.append(f"| {k[0]} - {k[1]} | " + " | ".join(
            f"{(by_pair[alt][k]['new']['rail'] + by_pair[alt][k]['new']['induced']) * yr:.2f}M" for alt in ("A", "S", "B1"))
            + " |")

    def pair_trips(alt, k):
        return (by_pair[alt][k]["new"]["rail"] + by_pair[alt][k]["new"]["induced"]) * yr

    best = max(rows, key=lambda k: rows[k]["trips2"] / rows[k]["cap2"])
    assert best == "A", best   # the prose below says so
    assert max(rows, key=lambda k: rows[k]["trips"] / rows[k]["cap"]) == "A"
    assert max(rows, key=lambda k: rows[k]["per_b_tc"]) == "A"
    assert all(max(v, key=v.get) == "A" for v in sens.values())
    assert all(rows[k]["trips2"] < a["trips2"] for k in ("B1", "B2", "C1"))
    s, b1 = rows["S"], rows["B1"]
    wyes = ("B1", "B2", "C1")
    extra = [rows[k]["cap2"] - a["cap2"] for k in wyes]
    b1_full = b1["split_30_30"]
    b1_au = b1["split_30_60"]
    out += ["", "### Recommendation", "",
            f"The one line (A) is the best Houston-west configuration on every measure per dollar. On top of I-35 "
            f"north and Dallas - Shreveport it adds {a['trips2']:.1f}M trips a year and ${a['gain2']:,.0f}M of "
            f"travellers' gain for ${a['cap2'] / 1000:.1f}B ({per_b(a['trips2'], a['cap2']):.2f}M trips and "
            f"${per_b(a['gain2'], a['cap2']):.0f}M of gain a year per $B), and it stays first built alone, with Texas "
            "Central built, and at $60M and $110M per km. Its Houston - San Antonio trains run through Austin in "
            f"{a['times'][1].split(' /')[0]} minutes, {int(a['times'][1].split(' /')[0]) - int(s['times'][1].split(' /')[0])} "
            "more than a direct I-10 line, and that difference is worth little: the separate set (S) adds "
            f"{s['trips2'] - a['trips2']:.1f}M trips for ${(s['cap2'] - a['cap2']) / 1000:.1f}B more "
            f"({per_b(s['trips2'] - a['trips2'], s['cap2'] - a['cap2']):.2f}M per $B), as I-10's ninth place in "
            "`study/hsr_options.md` already said.", "",
            f"No wye helps. Each wye that keeps I-35 south (B1, B2, C1) costs ${min(extra) / 1000:.0f}-"
            f"{max(extra) / 1000:.0f}B more than A, because the San Antonio branch is new track, and carries fewer "
            "trips: splitting the trains halves every Houston service (every 60 minutes, so the wait doubles from 15 "
            "to 30 minutes, which outweighs the 6-16 minutes a branch saves on Houston - San Antonio). In B1 Houston - Austin falls from "
            f"{pair_trips('A', ('Houston', 'Austin')):.1f}M trips a year to {pair_trips('B1', ('Houston', 'Austin')):.1f}M, "
            f"Dallas - Houston (through Austin) from {pair_trips('A', ('Dallas', 'Houston')):.2f}M to "
            f"{pair_trips('B1', ('Dallas', 'Houston')):.2f}M, and even Houston - San Antonio, 6 minutes faster on its "
            f"branch, carries {pair_trips('B1', ('Houston', 'San Antonio')):.1f}M against "
            f"{pair_trips('A', ('Houston', 'San Antonio')):.1f}M through Austin. Giddings (B1) is the best junction, since it keeps US 290's direct line to "
            f"Austin. Even with Houston - Austin trains every 30 minutes and San Antonio's every 60, B1 carries "
            f"{b1_au[0]:.1f}M trips, {b1_au[0] - a['trips2']:.1f}M more than A for ${(b1['cap2'] - a['cap2']) / 1000:.1f}B; "
            f"with both branches every 30 minutes it carries {b1_full[0]:.1f}M, "
            f"{per_b(b1_full[0] - a['trips2'], b1['cap2'] - a['cap2']):.2f}M per extra $B, below I-10's, at "
            f"${b1_full[2] - a['opex2']:,.0f}M a year more operating cost than A. The cheap combined lines lose "
            f"riders: the Lockhart wye without I-35 south (B3, ${rows['B3']['cap2'] / 1000:.1f}B) slows Austin - "
            "San Antonio, the busiest pair, and Houston - Austin; the Texas Triangle as usually drawn (C3) sends "
            "Houston - Austin round by San Antonio; reaching Austin from I-10 over a Seguin - San Marcos link (C2) does "
            "no better per $B. The T-Bone (D) costs about what A does once I-35 north exists and comes close "
            f"({per_b(rows['D']['trips2'], rows['D']['cap2']):.2f}M per $B) only because Dallas - Houston rides via "
            f"Temple; with Texas Central built it falls to {rows['D']['per_b_tc']:.2f}M against A's "
            f"{a['per_b_tc']:.2f}M.", "",
            "For `texas/hsr.py`: no change to its corridors. US 290 + I-35 south already is the one line A (with one "
            "headway, the model runs Houston - San Antonio through Austin), and I-10 should stay a separate, late "
            "candidate rather than become a wye's San Antonio branch: as an increment over A it is worth more per $B "
            "than any branch, and both are near the bottom of the ranking. Replacing US 290 + I-10 with a wye would "
            "lower the network's value. The one thing worth noting in `texas/hsr.py` is that US290 and I35S are meant "
            "to run as one line, Houston - San Antonio trains through Austin; the demand model and `hsr.opex_musd` "
            "already treat them that way.", "",
            "### Caveats", "",
            "- There is no transfer penalty, and a trip no single pattern serves waits for the least frequent link of "
            "its route. That flatters configurations where big pairs change trains: Houston - Austin at San Antonio "
            "in C3 most, and Dallas - Houston at Austin (or Temple) in every alternative alike.",
            "- Each county uses its nearest station. A branch station at Seguin (B1, B2) pulls Guadalupe County off "
            "the I-35 south trains onto the hourly branch, which is why Austin - San Antonio carries a little less in "
            "B1 than in A; people would choose the better station. That costs B1 under 0.5M trips a year, far less "
            "than its gap to A.",
            "- Every link is straight line x 1.12 at $90M per km. A junction's flying junctions and the triangle at "
            "Lockhart cost more than plain track, and the Colorado and Guadalupe crossings of the branches are not "
            "costed separately; both would only add to the wyes' cost.",
            "- Junction sites are towns on the roads, each a $150M station that also serves its county. Other sites "
            "(Elgin, Bastrop, La Grange or Luling as junctions) fall between the ones tested: the geometry is a "
            "trade between a long shared trunk and direct branches, and none tested comes near A.",
            "- One speed (260 km/h between stops, 3 minutes a stop) everywhere, and the demand model's parameters are "
            "the documented assumptions of `texas/intercity.json`. Rail's constant and induced trips move the totals "
            "a lot (A from {:.2f}M to {:.2f}M trips per $B) but not the ranking: A is first in every run.".format(
                sens["asc1"]["A"], sens["asc0"]["A"]),
            "- Operating cost, fares and wider benefits are not netted here; `study/timing.py` values the corridors "
            "in `texas/hsr.py` and is unchanged."]

    text = "\n".join(out) + "\n"
    with open(os.path.join(ROOT, "study", "hsr_houston_west.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
