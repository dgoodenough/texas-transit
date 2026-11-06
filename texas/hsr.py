"""High-speed rail corridors for Texas and its neighbours: stations, corridors (chains of
stations), and capital cost.

Stations are approximate sites: downtowns, Texas Central's planned stations, and towns along the
interstates. Track follows the straight line between neighbouring stations times TRACK_FACTOR.

Capital cost (2025 dollars) = track km x COST_PER_KM + a station cost by kind. COST_PER_KM is set
between the two recent US references: Texas Central (240 miles; above $30B in 2023, above $40B by
USDOT's 2025 figure: about $80-105M per km) and Brightline West (218 miles, mostly in a freeway
median; $21.5B: about $60M per km). The study tests $60M and $110M.
"""
from texas.intercity import km

TRACK_FACTOR = 1.12          # track km per straight-line km between neighbouring stations (assumption)
COST_PER_KM = 90.0           # $M per track km, 2025 dollars
STATION_COST = {"major": 600.0, "minor": 150.0}   # $M: a downtown terminal and its approach; a town stop

STATIONS = {
    # name: (lat, lon, kind)
    "Dallas": (32.770, -96.802, "major"),            # Texas Central: the Cedars
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
    "Denton": (33.215, -97.133, "minor"),
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
    "RGV": ("Rio Grande Valley: San Antonio - McAllen - Harlingen - Brownsville",
            ["San Antonio", "McAllen", "Harlingen", "Brownsville"]),
    "CC": ("Houston - Victoria - Corpus Christi", ["Houston", "Victoria", "Corpus Christi"]),
    "GULF": ("Gulf Coast: Houston - Beaumont - Lake Charles - Lafayette - Baton Rouge - New Orleans",
             ["Houston", "Beaumont", "Lake Charles", "Lafayette", "Baton Rouge", "New Orleans"]),
    "OKC": ("Dallas - Denton - Norman - Oklahoma City", ["Dallas", "Denton", "Norman", "Oklahoma City"]),
    "SHV": ("Dallas - Tyler - Longview - Shreveport", ["Dallas", "Tyler", "Longview", "Shreveport"]),
    "WEST": ("West Texas: Fort Worth - Abilene - Midland - Odessa - El Paso",
             ["Fort Worth", "Abilene", "Midland", "Odessa", "El Paso"]),
    "LBB": ("Fort Worth - Lubbock", ["Fort Worth", "Lubbock"]),
}


def point(name):
    la, lo, _ = STATIONS[name]
    return la, lo


def links(chain):
    """[(a, b, track km)] along a chain of stations."""
    return [(a, b, km(point(a), point(b)) * TRACK_FACTOR) for a, b in zip(chain, chain[1:])]


def network_links(corridor_ids):
    seen, out = set(), []
    for cid in corridor_ids:
        for a, b, t in links(CORRIDORS[cid][1]):
            key = tuple(sorted((a, b)))
            if key not in seen:
                seen.add(key)
                out.append((a, b, t))
    return out


def stations_of(corridor_ids):
    return {s for cid in corridor_ids for s in CORRIDORS[cid][1]}


def capital_musd(corridor_ids, cost_per_km=COST_PER_KM, built=()):
    """Capital cost ($M) of the corridors, leaving out track and stations already in `built`."""
    have_links = {tuple(sorted((a, b))) for a, b, _ in network_links(built)}
    have_st = stations_of(built)
    track = sum(t for a, b, t in network_links(corridor_ids) if tuple(sorted((a, b))) not in have_links)
    st = sum(STATION_COST[STATIONS[s][2]] for s in stations_of(corridor_ids) - have_st)
    return track * cost_per_km + st


def track_km(corridor_ids):
    return sum(t for _, _, t in network_links(corridor_ids))
