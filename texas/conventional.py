"""Conventional intercity rail: a few trains a day at up to 79 mph on upgraded freight track, to
Texas's neighbours and Monterrey. The interstate layer, at a high level.

Stations are the Amtrak stations where there is one (approximate), otherwise downtowns. Track
follows the straight line between neighbouring stations times TRACK_FACTOR (freight lines wind
more than a new high-speed alignment).

Capital (2025 dollars, all assumptions, tested in the study):
- track: route km x (TRACK_BASE + TRACK_PER_TRAIN x trains a day each way) $M: sidings,
  signals, crossings and track to carry the passenger trains on a freight railroad. About $2-3M
  per km for two to four trains a day; restorations on lightly used lines have cost about $1M
  per km, capacity programmes on busy lines several times that.
- stations: a new station STATION_NEW, a stop Amtrak already serves STATION_EXISTING.
- trainsets: TRAINSET each, enough for the timetable plus one spare.
- the Monterrey corridor adds a border station with customs (BORDER_STATION).
Operating cost: OPEX_PER_TRAIN_KM $ a train-km (state-supported Amtrak routes run about $35-60 a
train-mile, so $25-40 a train-km).
"""
import math

from texas.intercity import km

TRACK_FACTOR = 1.2
TRACK_BASE, TRACK_PER_TRAIN = 1.0, 0.5           # $M per route km, + per train a day each way
STATION_NEW, STATION_EXISTING = 20.0, 5.0         # $M
TRAINSET = 35.0                                   # $M
BORDER_STATION = 150.0                            # $M
OPEX_PER_TRAIN_KM = 32.0                          # $
TURN_MIN = 60                                     # minutes at each end

STATIONS = {   # name: (lat, lon, Amtrak stop today)
    "Dallas": (32.776, -96.808, True), "Fort Worth": (32.749, -97.327, True),
    "Gainesville": (33.625, -97.135, True), "Ardmore": (34.174, -97.128, True),
    "Pauls Valley": (34.740, -97.222, True), "Purcell": (35.012, -97.360, True),
    "Norman": (35.222, -97.439, True), "Oklahoma City": (35.465, -97.509, True),
    "Ponca City": (36.707, -97.086, False), "Wichita": (37.686, -97.333, False),
    "Newton": (38.047, -97.345, True), "Emporia": (38.404, -96.181, False),
    "Topeka": (39.048, -95.678, True), "Kansas City": (39.085, -94.586, True),
    "Mineola": (32.663, -95.488, True), "Longview": (32.495, -94.740, True),
    "Marshall": (32.545, -94.367, True), "Shreveport": (32.512, -93.747, False),
    "Ruston": (32.523, -92.638, False), "Monroe": (32.509, -92.119, False),
    "Vicksburg": (32.353, -90.878, False), "Jackson": (32.300, -90.185, True),
    "Texarkana": (33.420, -94.043, True), "Arkadelphia": (34.121, -93.054, True),
    "Little Rock": (34.738, -92.276, True), "Memphis": (35.136, -90.050, True),
    "Houston": (29.767, -95.367, True), "Beaumont": (30.080, -94.101, True),
    "Lake Charles": (30.226, -93.217, True), "Lafayette": (30.224, -92.020, True),
    "New Iberia": (30.003, -91.818, True), "Schriever": (29.743, -90.810, True),
    "New Orleans": (29.946, -90.078, True),
    "El Paso": (31.759, -106.493, True), "Las Cruces": (32.312, -106.778, False),
    "Socorro": (34.058, -106.891, False), "Albuquerque": (35.081, -106.648, True),
    "San Antonio": (29.424, -98.478, True), "Laredo": (27.506, -99.507, False),
    "Monterrey": (25.686, -100.316, False),
}

# id: (name, chain, trains a day each way today)
CORRIDORS = {
    "FLYER": ("Heartland Flyer: Fort Worth - Oklahoma City",
              ["Fort Worth", "Gainesville", "Ardmore", "Pauls Valley", "Purcell", "Norman", "Oklahoma City"], 1),
    "KC": ("Oklahoma City - Wichita - Kansas City",
           ["Oklahoma City", "Ponca City", "Wichita", "Newton", "Emporia", "Topeka", "Kansas City"], 0),
    "I20": ("I-20: Dallas - Shreveport - Monroe - Jackson",
            ["Dallas", "Mineola", "Longview", "Marshall", "Shreveport", "Ruston", "Monroe", "Vicksburg", "Jackson"], 0),
    "EAGLE": ("Texas Eagle east: Longview - Texarkana - Little Rock - Memphis",
              ["Longview", "Texarkana", "Arkadelphia", "Little Rock", "Memphis"], 1),
    "SUNSET": ("Sunset: Houston - Lake Charles - Lafayette - New Orleans",
               ["Houston", "Beaumont", "Lake Charles", "Lafayette", "New Iberia", "Schriever", "New Orleans"], 3 / 7),
    "ABQ": ("El Paso - Las Cruces - Albuquerque", ["El Paso", "Las Cruces", "Socorro", "Albuquerque"], 0),
    "MTY": ("San Antonio - Laredo - Monterrey", ["San Antonio", "Laredo", "Monterrey"], 0),
    "DFW": ("Dallas - Fort Worth (connector on the TRE line)", ["Dallas", "Fort Worth"], 2),
}


def point(name):
    la, lo, _ = STATIONS[name]
    return la, lo


def links(chain):
    return [(a, b, km(point(a), point(b)) * TRACK_FACTOR) for a, b in zip(chain, chain[1:])]


def network_links(ids):
    seen, out = set(), []
    for cid in ids:
        for a, b, t in links(CORRIDORS[cid][1]):
            if tuple(sorted((a, b))) not in seen:
                seen.add(tuple(sorted((a, b))))
                out.append((a, b, t))
    return out


def stations_of(ids):
    return {s for cid in ids for s in CORRIDORS[cid][1]}


def route_km(cid):
    return sum(t for _, _, t in links(CORRIDORS[cid][1]))


def run_minutes(cid, svc):
    chain = CORRIDORS[cid][1]
    return route_km(cid) / svc["speed_kmh"] * 60 + (len(chain) - 2) * svc["stop_min"]


def trainsets(cid, trains_per_day, svc):
    """Sets to run `trains_per_day` each way over the service day, plus a spare."""
    cycle = 2 * (run_minutes(cid, svc) + TURN_MIN)
    return max(2, math.ceil(cycle * trains_per_day / (svc["service_hours"] * 60)) + 1)


def capital_musd(cid, trains_per_day, svc, track_base=TRACK_BASE):
    """Capital to run `trains_per_day` each way, beyond today's service (stations already served
    cost less; track is sized for the whole timetable)."""
    chain = CORRIDORS[cid][1]
    track = route_km(cid) * (track_base + TRACK_PER_TRAIN * trains_per_day)
    stations = sum(STATION_EXISTING if STATIONS[s][2] else STATION_NEW for s in chain)
    border = BORDER_STATION if "Monterrey" in chain else 0.0
    return track + stations + trainsets(cid, trains_per_day, svc) * TRAINSET + border


def opex_musd(cid, trains_per_day):
    return 2 * route_km(cid) * trains_per_day * 365 * OPEX_PER_TRAIN_KM / 1e6


def service(svc, trains_per_day):
    """The service parameters for a timetable of `trains_per_day` each way."""
    out = dict(svc)
    out["trains_per_day"] = trains_per_day
    out["headway_min"] = svc["service_hours"] * 60 / trains_per_day
    return out
