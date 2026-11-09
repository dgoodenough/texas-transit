"""High-speed rail corridors for Texas and its neighbours: stations, corridors (chains of
stations), and capital cost.

Stations are approximate sites: downtowns, Texas Central's planned stations, and towns along the
interstates. Track follows the straight line between neighbouring stations times TRACK_FACTOR.

Capital cost (2025 dollars) = track km x COST_PER_KM + a station cost by kind. COST_PER_KM is set
between the two recent US references: Texas Central (240 miles; above $30B in 2023, above $40B by
USDOT's 2025 figure: about $80-105M per km) and Brightline West (218 miles, mostly in a freeway
median; $21.5B: about $60M per km). The study tests $60M and $110M.

Operating cost a year (assumptions, 2025 dollars): every link runs the timetable's trains both ways
over the service day (intercity.json hsr: a train every headway_min for SERVICE_HOURS) at
OPEX_PER_TRAIN_KM, plus MAINTENANCE_PER_KM of track and systems upkeep. European high-speed
operators run about $25-45 a train-km before infrastructure.

Phase 2 (study/hsr_buildout.md; study/cabinet/infra.md, network.md) adds, through SETTINGS:
  - drawn track km: each link's length along texas/hsr_alignments.json where it is drawn, else the
    straight line x DRAWN_FACTOR (SETTINGS["drawn"]; off = straight line x TRACK_FACTOR, as before);
  - unit costs by context (SETTINGS["case"] low / central / high; "flat" = COST_PER_KM everywhere,
    as before): urban approaches into the big metros, mid-city approaches, towns, rugged and flat
    rural ground, with each corridor's rugged share;
  - design standards per corridor (SETTINGS["standards"]): S1 320 km/h double track (the default),
    S2 250 km/h double, S3 250 km/h single track with passing loops graded for a second, S4 200 km/h
    single track; a factor on rural cost and an average speed between stops;
  - a learning curve on cumulative statewide km (SETTINGS["learning"]): 10% cheaper per doubling past
    500 km, floored at 0.75, earned by a permanent delivery office and standard designs.
The network is redrawn (study/cabinet/network.md): West Texas branches at Abilene (the Big Country
trunk Fort Worth - Weatherford - Abilene, then El Paso and Lubbock - Amarillo legs), and the Valley is
reached from Corpus Christi (a Gulf spine through Kingsville and Harlingen to Brownsville, McAllen a
spur from Harlingen; Brownsville and Harlingen share a county, so the model can't value a Brownsville
spur), instead of separate Fort Worth - Lubbock and San Antonio - McAllen lines.
"""
import json
import math
import os

from texas.intercity import km

TRACK_FACTOR = 1.12          # track km per straight-line km between neighbouring stations (assumption)
COST_PER_KM = 90.0           # $M per track km, 2025 dollars
STATION_COST = {"major": 600.0, "minor": 150.0}   # $M: a downtown terminal and its approach; a town stop
SERVICE_HOURS = 18
OPEX_PER_TRAIN_KM = 40.0     # $ (trains of about 400 seats)
MAINTENANCE_PER_KM = 0.25    # $M per track km a year

STATIONS = {
    # name: (lat, lon, kind)
    "Dallas": (32.7728, -96.8080, "major"),          # beside Union Station, DFW Transit's busiest hub (TRE, Red and
                                                     # Blue lines, streetcar, BRT): 300 m on foot (study/timing.md)
    "Fort Worth": (32.749, -97.327, "major"),
    "Brazos Valley": (30.590, -96.050, "minor"),     # Texas Central: Grimes County
    "Houston": (29.807, -95.458, "major"),           # Texas Central: Northwest Mall
    "Waco": (31.555, -97.130, "minor"),
    "Temple": (31.098, -97.343, "minor"),
    "Austin": (30.267, -97.743, "major"),
    "San Marcos": (29.883, -97.941, "minor"),
    "San Antonio": (29.424, -98.493, "major"),
    "Columbus": (29.706, -96.540, "minor"),
    "Seguin": (29.569, -97.965, "minor"),
    "Brenham": (30.167, -96.398, "minor"),
    "Laredo": (27.506, -99.507, "major"),
    "Corpus Christi": (27.800, -97.396, "major"),
    "Victoria": (28.805, -97.003, "minor"),
    "McAllen": (26.203, -98.230, "major"),
    "Harlingen": (26.190, -97.696, "minor"),
    "Brownsville": (25.902, -97.497, "minor"),
    "Beaumont": (30.080, -94.101, "minor"),
    "Lake Charles": (30.226, -93.217, "minor"),
    "Lafayette": (30.224, -92.020, "minor"),
    "Baton Rouge": (30.451, -91.187, "major"),
    "New Orleans": (29.951, -90.071, "major"),
    "Denton": (33.2139, -97.1262, "minor"),          # Downtown Denton Transit Center (A-train, DFW Transit's BRT)
    "Norman": (35.222, -97.439, "minor"),
    "Oklahoma City": (35.468, -97.516, "major"),
    "Tyler": (32.351, -95.301, "minor"),
    "Longview": (32.500, -94.740, "minor"),
    "Shreveport": (32.525, -93.750, "major"),
    "Abilene": (32.449, -99.733, "minor"),
    "Midland": (31.997, -102.078, "minor"),
    "Odessa": (31.846, -102.367, "minor"),
    "El Paso": (31.759, -106.487, "major"),
    "Lubbock": (33.577, -101.855, "major"),
    "Weatherford": (32.759, -97.797, "minor"),
    "Amarillo": (35.207, -101.834, "major"),
    "Kingsville": (27.516, -97.856, "minor"),
}

# corridor id: (name, chain of stations)
CORRIDORS = {
    "TC": ("Texas Central: Dallas - Brazos Valley - Houston", ["Dallas", "Brazos Valley", "Houston"]),
    "FW": ("Fort Worth - Dallas", ["Fort Worth", "Dallas"]),
    "I35N": ("I-35 north: Dallas - Waco - Temple - Austin", ["Dallas", "Waco", "Temple", "Austin"]),
    "I35S": ("I-35 south: Austin - San Marcos - San Antonio", ["Austin", "San Marcos", "San Antonio"]),
    "I10": ("I-10: Houston - Columbus - Seguin - San Antonio", ["Houston", "Columbus", "Seguin", "San Antonio"]),
    "US290": ("US 290: Houston - Brenham - Austin", ["Houston", "Brenham", "Austin"]),
    "LRD": ("San Antonio - Laredo", ["San Antonio", "Laredo"]),
    "CC": ("Houston - Victoria - Corpus Christi", ["Houston", "Victoria", "Corpus Christi"]),
    "GULF": ("Gulf Coast: Houston - Beaumont - Lake Charles - Lafayette - Baton Rouge - New Orleans",
             ["Houston", "Beaumont", "Lake Charles", "Lafayette", "Baton Rouge", "New Orleans"]),
    "OKC": ("Dallas - Denton - Norman - Oklahoma City", ["Dallas", "Denton", "Norman", "Oklahoma City"]),
    "SHV": ("Dallas - Tyler - Longview - Shreveport", ["Dallas", "Tyler", "Longview", "Shreveport"]),
    "BIGC": ("Big Country: Fort Worth - Weatherford - Abilene", ["Fort Worth", "Weatherford", "Abilene"]),
    "WEST": ("West Texas: Abilene - Midland - Odessa - El Paso", ["Abilene", "Midland", "Odessa", "El Paso"]),
    "PANH": ("Panhandle: Abilene - Lubbock - Amarillo", ["Abilene", "Lubbock", "Amarillo"]),
    "VALLEY": ("Rio Grande Valley: Corpus Christi - Kingsville - Harlingen - Brownsville",
               ["Corpus Christi", "Kingsville", "Harlingen", "Brownsville"]),
    "MFE": ("McAllen: Harlingen - McAllen", ["Harlingen", "McAllen"]),
}
# a corridor can't open (or be valued) before these: the redrawn branches hang off trunks
REQUIRES = {"BIGC": ["FW"], "WEST": ["BIGC"], "PANH": ["BIGC"], "VALLEY": ["CC"], "MFE": ["VALLEY"]}
# the corridors these replace, for comparison (study/hsr_options.md)
REPLACED = {
    "RGV": ("Rio Grande Valley: San Antonio - McAllen - Harlingen - Brownsville",
            ["San Antonio", "McAllen", "Harlingen", "Brownsville"]),
    "LBB": ("Fort Worth - Lubbock", ["Fort Worth", "Lubbock"]),
    "WEST_OLD": ("West Texas: Fort Worth - Abilene - Midland - Odessa - El Paso",
                 ["Fort Worth", "Abilene", "Midland", "Odessa", "El Paso"]),
}

# ---------- cost model (Phase 2; study/cabinet/infra.md) ----------
SETTINGS = {"case": "high", "learning": False, "drawn": True, "standards": {}}
DRAWN_FACTOR = 1.06   # track km per straight-line km where no alignment is drawn
BIG = {"Dallas", "Fort Worth", "Houston", "Austin", "San Antonio", "Oklahoma City", "El Paso", "New Orleans"}
MID = {"Laredo", "McAllen", "Lubbock", "Amarillo", "Corpus Christi", "Shreveport", "Baton Rouge"}
RATES = {   # $M per double-track km, 2025 dollars: low, central, high
    "urban": (150, 200, 300),    # the first 12 km out of a big-metro terminal
    "mid": (90, 120, 160),       # the first 6 km out of a mid-size city's station
    "town": (70, 90, 110),       # the next 10 km past a big-metro approach; 3 km each side of a town stop
    "rugged": (50, 75, 95),      # escarpments, river bottoms, the Arbuckles, the Trans-Pecos
    "flat": (32, 50, 62),        # flat ground beside a highway or railroad
}
APPROACH_KM = {"urban": 12, "mid": 6, "town_big": 10, "town_minor": 3}
RUGGED = {"TC": .40, "I35N": .30, "I35S": .50, "I10": .25, "US290": .30, "CC": .25, "GULF": .55, "SHV": .35, "OKC": .30,
          "LRD": .15, "BIGC": .25, "WEST": .25, "PANH": .15, "VALLEY": .10, "MFE": .10, "FW": .0}
STANDARDS = {   # rural-cost factor (approaches stay double track at full cost), average speed between stops km/h
    "S1": (1.00, 260), "S2": (0.90, 210), "S3": (0.66, 200), "S4": (0.52, 160)}
CASE_INDEX = {"low": 0, "central": 1, "high": 2}
_WAYPOINTS = None


def _alignments():
    global _WAYPOINTS
    if _WAYPOINTS is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hsr_alignments.json")
        with open(path, encoding="utf-8") as f:
            wp = json.load(f)["waypoints"]
        _WAYPOINTS = {}
        for segs in wp.values():
            for k, pts in segs.items():
                a, b = k.split("|")
                _WAYPOINTS[(a, b)] = pts
                _WAYPOINTS[(b, a)] = pts[::-1]
    return _WAYPOINTS


def link_km(a, b):
    """Track km between neighbouring stations: along the drawn alignment where there is one (SETTINGS
    drawn), else the straight line x DRAWN_FACTOR; with drawn off, the straight line x TRACK_FACTOR."""
    if not SETTINGS.get("drawn"):
        return km(point(a), point(b)) * TRACK_FACTOR
    pts = _alignments().get((a, b))
    if pts is None:
        return km(point(a), point(b)) * DRAWN_FACTOR
    chain = [point(a)] + [tuple(p) for p in pts] + [point(b)]
    return sum(km(p, q) for p, q in zip(chain, chain[1:]))


def standard_of(cid):
    return SETTINGS.get("standards", {}).get(cid, "S1")


def link_speed(a, b, corridor_ids):
    """Average speed on a link: the best standard among the corridors that run on it."""
    speeds = [STANDARDS[standard_of(c)][1] for c in corridor_ids if _on(a, b, CORRIDORS[c][1])]
    return max(speeds) if speeds else STANDARDS["S1"][1]


def _on(a, b, chain):
    return any({x, y} == {a, b} for x, y in zip(chain, chain[1:]))


def link_cost(a, b, cid):
    """Capital ($M) of a link's track by context: approaches out of each end at their rates (double
    track), the rest rural at the corridor's rugged share, times its design standard's factor."""
    i = CASE_INDEX[SETTINGS["case"]]
    L = link_km(a, b)
    approach = 0.0
    cost = 0.0
    for s in (a, b):
        half = L / 2
        if s in BIG:
            u = min(APPROACH_KM["urban"], half)
            t = min(APPROACH_KM["town_big"], half - u)
            cost += u * RATES["urban"][i] + t * RATES["town"][i]
            approach += u + t
        elif s in MID:
            m = min(APPROACH_KM["mid"], half)
            cost += m * RATES["mid"][i]
            approach += m
        else:
            t = min(APPROACH_KM["town_minor"], half)
            cost += t * RATES["town"][i]
            approach += t
    rural = max(0.0, L - approach)
    rg = RUGGED.get(cid, 0.25)
    factor = STANDARDS[standard_of(cid)][0]
    cost += rural * (rg * RATES["rugged"][i] + (1 - rg) * RATES["flat"][i]) * factor
    return cost


def learning_factor(km_before):
    """Unit-cost factor once km_before km have been built statewide (SETTINGS learning): 10% cheaper
    per doubling past 500 km, never below 0.75; 1 with learning off."""
    if not SETTINGS.get("learning") or km_before <= 500:
        return 1.0
    return max(0.75, 0.9 ** math.log2(km_before / 500))


def point(name):
    la, lo, _ = STATIONS[name]
    return la, lo


def links(chain):
    """[(a, b, track km)] along a chain of stations."""
    return [(a, b, link_km(a, b)) for a, b in zip(chain, chain[1:])]


def network_links(corridor_ids, with_speed=False):
    """[(a, b, track km)] of the corridors' links, each once; with_speed adds each link's average
    speed (km/h) by design standard, for texas/intercity.RailNetwork."""
    seen, out = set(), []
    for cid in corridor_ids:
        for a, b, t in links(CORRIDORS[cid][1]):
            key = tuple(sorted((a, b)))
            if key not in seen:
                seen.add(key)
                out.append((a, b, t, link_speed(a, b, corridor_ids)) if with_speed else (a, b, t))
    return out


def stations_of(corridor_ids):
    return {s for cid in corridor_ids for s in CORRIDORS[cid][1]}


def capital_musd(corridor_ids, cost_per_km=None, built=()):
    """Capital cost ($M) of the corridors, leaving out track and stations already in `built`. With
    SETTINGS case "flat" (or an explicit cost_per_km) every track km costs the same, as before Phase 2;
    else by context and design standard. The learning factor follows the km built before it (`built`)."""
    have_links = {tuple(sorted((a, b))) for a, b, _ in network_links(built)}
    have_st = stations_of(built)
    st = sum(STATION_COST[STATIONS[s][2]] for s in stations_of(corridor_ids) - have_st)
    new = [(a, b) for a, b, _ in network_links(corridor_ids) if tuple(sorted((a, b))) not in have_links]
    if cost_per_km is not None or SETTINGS["case"] == "flat":
        return sum(link_km(a, b) for a, b in new) * (cost_per_km or COST_PER_KM) + st
    owner = {}
    for cid in corridor_ids:
        for a, b in zip(CORRIDORS[cid][1], CORRIDORS[cid][1][1:]):
            owner.setdefault(tuple(sorted((a, b))), cid)
    track = sum(link_cost(a, b, owner[tuple(sorted((a, b)))]) for a, b in new)
    return (track + st) * learning_factor(track_km(built))


def track_km(corridor_ids):
    return sum(t for _, _, t in network_links(corridor_ids))


def opex_musd(corridor_ids, headway_min, built=()):
    """Operating cost a year ($M) of the corridors' own links (those not already in `built`)."""
    have = {tuple(sorted((a, b))) for a, b, _ in network_links(built)}
    track = sum(t for a, b, t in network_links(corridor_ids) if tuple(sorted((a, b))) not in have)
    trains = SERVICE_HOURS * 60 / headway_min   # each way, a day
    return (2 * track * trains * 365 * OPEX_PER_TRAIN_KM) / 1e6 + track * MAINTENANCE_PER_KM


# ---------- service patterns (Phase 2; study/cabinet/network.md) ----------
# Through trains once every corridor they run over is built: (corridors, station chain, headway minutes).
PATTERNS = [
    (["FW", "TC"], ["Fort Worth", "Dallas", "Brazos Valley", "Houston"], 30),
    (["FW", "I35N", "I35S"], ["Fort Worth", "Dallas", "Waco", "Temple", "Austin", "San Marcos", "San Antonio"], 30),
    (["I10"], ["Houston", "Columbus", "Seguin", "San Antonio"], 30),
    (["US290"], ["Houston", "Brenham", "Austin"], 60),
    (["OKC", "I35N"], ["Oklahoma City", "Norman", "Denton", "Dallas", "Waco", "Temple", "Austin"], 60),
    (["LRD", "I10"], ["Laredo", "San Antonio", "Seguin", "Columbus", "Houston"], 60),
    (["VALLEY", "CC"], ["Brownsville", "Harlingen", "Kingsville", "Corpus Christi", "Victoria", "Houston"], 60),
    (["MFE", "VALLEY", "CC"], ["McAllen", "Harlingen", "Kingsville", "Corpus Christi", "Victoria", "Houston"], 60),
    (["SHV"], ["Dallas", "Tyler", "Longview", "Shreveport"], 60),
    (["GULF"], ["Houston", "Beaumont", "Lake Charles", "Lafayette", "Baton Rouge", "New Orleans"], 60),
    (["WEST", "BIGC", "FW"], ["El Paso", "Odessa", "Midland", "Abilene", "Weatherford", "Fort Worth", "Dallas"], 120),
    (["PANH", "BIGC", "FW"], ["Amarillo", "Lubbock", "Abilene", "Weatherford", "Fort Worth", "Dallas"], 120),
]
SHUTTLE_HEADWAY = {"FW": 30, "TC": 30, "I35N": 30, "I35S": 30, "I10": 30, "US290": 60, "OKC": 60, "LRD": 60, "CC": 60,
                   "VALLEY": 60, "MFE": 60, "SHV": 60, "GULF": 60, "BIGC": 120, "WEST": 120, "PANH": 120}


def services_for(corridor_ids):
    """Service patterns for a built network: every through pattern whose corridors are all built, and a
    shuttle along each built corridor no such pattern covers in full (at SHUTTLE_HEADWAY). For
    texas/intercity.RailNetwork(services=...): a trip no pattern serves pays a transfer."""
    built = set(corridor_ids)
    out, covered = [], set()
    for cids, chain, h in PATTERNS:
        if set(cids) <= built:
            out.append((chain, h))
            covered |= set(cids)
    for cid in corridor_ids:
        if cid not in covered:
            out.append((CORRIDORS[cid][1], SHUTTLE_HEADWAY.get(cid, 60)))
    return out


def pattern_opex_musd(corridor_ids):
    """Operating cost a year ($M) of a built network run as services_for(): every pattern's trains both
    ways over the service day at OPEX_PER_TRAIN_KM, plus MAINTENANCE_PER_KM of its track."""
    train_km = 0.0
    for chain, h in services_for(corridor_ids):
        trains = SERVICE_HOURS * 60 / h
        train_km += 2 * trains * sum(link_km(a, b) for a, b in zip(chain, chain[1:]))
    return train_km * 365 * OPEX_PER_TRAIN_KM / 1e6 + track_km(corridor_ids) * MAINTENANCE_PER_KM
