"""Intercity travel between NextGen zones (metro areas and the rest of each state) and how it
splits between car, air and new rail services.

Base: today's person-trips for every zone pair with a Texas end, from the FHWA / ORNL NextGen
NHTS 2022 origin-destination data (both directions added, annual / 365), with air replaced by
the airline ticket sample (DOT Consumer Airfare Report) where a city-pair market maps onto the
zone pair. Mode choice is a pivot-point nested logit: each pair keeps its observed car/air split
through pair-specific constants; a new rail mode's utility is set against car's from its time,
cost and frequency (texas/intercity.json), and rail shares a nest with air (public modes), so it
draws more from air than the shares alone would say. Only pairs whose centres are at least
`min_km` apart count. Each county of a zone uses its own nearest station, so a metro with several
stations is served where its people live; rail's odds for a zone pair are the people-weighted
average over its county pairs. Trips grow with population (`growth`), and rail adds induced
trips (a share of its riders, `hsr.induced_share`).
"""
import csv
import heapq
import json
import math
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(ROOT, "texas", "intercity.json")


def load_params(path=PARAMS):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def km(a, b):
    """Great-circle km between (lat, lon) points."""
    (la1, lo1), (la2, lo2) = a, b
    h = (math.sin(math.radians(la2 - la1) / 2) ** 2
         + math.cos(math.radians(la1)) * math.cos(math.radians(la2)) * math.sin(math.radians(lo2 - lo1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def load_zones(folder=os.path.join(ROOT, "data", "zones")):
    """{zone_id: {name, state, pop, at: (lat, lon), parts: [((lat, lon), people), ...]}} for zones
    with people; `parts` are its counties."""
    out = {}
    with open(os.path.join(folder, "nextgen_zones.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["lat"]:
                out[r["zone_id"]] = {"name": r["name"], "state": r["state"], "pop": int(r["pop_2020"]),
                                     "at": (float(r["lat"]), float(r["lon"])), "parts": [], "fips": []}
    with open(os.path.join(folder, "county_zones.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["zone_id"] in out:
                out[r["zone_id"]]["parts"].append(((float(r["lat"]), float(r["lon"])), int(r["pop_2020"])))
                out[r["zone_id"]]["fips"].append(r["county_fips"])
    return out


def zone_growth(zones, year, path=os.path.join(ROOT, "data", "zones", "county_growth.csv")):
    """{zone_id: population in `year` / 2020}, from the counties' trend (tools/build_growth.py)."""
    if year <= 2020:
        return {z: 1.0 for z in zones}
    with open(path, encoding="utf-8") as f:
        rows = {r["county_fips"]: r for r in csv.DictReader(f)}
    col = f"pop_{year}"
    out = {}
    for z, v in zones.items():
        now = sum(int(rows[c]["pop_2020"]) for c in v["fips"] if c in rows)
        then = sum(float(rows[c][col]) for c in v["fips"] if c in rows)
        out[z] = then / now if now else 1.0
    return out


def short_name(zone):
    """'Dallas' for 'Dallas-Fort Worth-Arlington, TX'; 'rural TX (NE)' for 'TX-NonMSA areas (NE)'."""
    name = zone["name"]
    if "NonMSA" in name:
        return f"rural {zone['state']} {name[name.find('('):]}" if "(" in name else f"rural {zone['state']}"
    return name.split(",")[0].split("-")[0]


def _market_zone(city, zones):
    """The zone an airline city market belongs to: a zone in the market's state whose name holds
    the market's first city ("Dallas/Fort Worth, TX" -> Dallas-Fort Worth-Arlington, TX)."""
    name, _, st = city.partition(", ")
    st = st[:2]
    first = name.split("/")[0].split(" (")[0].strip()
    for z, v in zones.items():
        if v["state"] == st and first.lower() in v["name"].lower():
            return z
    return None


def base_trips(zones, p, flows=os.path.join(ROOT, "data", "flows")):
    """{(zone a, zone b) sorted: {km, car, air, work_share, air_fare}}: today's daily person-trips
    in both directions."""
    acc = defaultdict(lambda: defaultdict(float))
    with open(os.path.join(flows, "nhts_od_2022_texas.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            a, b = r["origin_zone_id"], r["destination_zone_id"]
            if a == b or a not in zones or b not in zones:
                continue
            d = acc[tuple(sorted((a, b)))]
            for k in ("annual_total_trips", "mode_air", "mode_vehicle", "purpose_work"):
                d[k] += float(r[k] or 0)
    # air from the ticket sample where its market maps onto the pair (both directions)
    tickets = defaultdict(lambda: [0.0, 0.0])
    with open(os.path.join(flows, "air_city_pairs.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            a, b = _market_zone(r["city1"], zones), _market_zone(r["city2"], zones)
            if a and b and a != b:
                t = tickets[tuple(sorted((a, b)))]
                pax = 2 * float(r["passengers_per_day"])
                t[0] += pax
                t[1] += pax * float(r["avg_fare"] or 0)
    out = {}
    for pair, d in acc.items():
        dist = km(zones[pair[0]]["at"], zones[pair[1]]["at"])
        total = d["annual_total_trips"] / 365
        if dist < p["min_km"] or total <= 0:
            continue
        car = d["mode_vehicle"] / 365
        air = d["mode_air"] / 365
        fare = None
        if pair in tickets and tickets[pair][0] > 0:
            air, fare = tickets[pair][0], tickets[pair][1] / tickets[pair][0]
        out[pair] = {"km": dist, "car": car, "air": air, "work_share": d["purpose_work"] / d["annual_total_trips"],
                     "air_fare": fare}
    return out


# ---------- level of service: (in-vehicle minutes, out-of-vehicle minutes, cost per person) ----------
def car_los(dist, purpose, p):
    c = p["car"]
    road = dist * c["circuity"]
    return road / c["speed_kmh"] * 60, c["terminal_min"], road * c["cost_per_vehicle_km"] / p["purposes"][purpose]["occupancy"]


def air_los(dist, pax_per_day, fare, p):
    a = p["air"]
    deps = max(1.0, pax_per_day / 2 / (a["seats_per_flight"] * a["load_factor"]))
    delay = min(a["max_schedule_delay_min"], a["service_hours"] * 60 / deps / 4)
    ivt = a["block_min_fixed"] + dist / a["block_km_per_min"]
    ovt = a["access_min"] + a["egress_min"] + a["terminal_min"] + delay
    return ivt, ovt, fare if fare else a["fare_fixed"] + a["fare_per_km"] * dist


def utility(los, purpose, p):
    ivt, ovt, cost = los
    bc = p["cost_coef_per_dollar"][purpose]
    bt = bc * p["purposes"][purpose]["vot_per_hour"] / 60
    return bt * (ivt + p["out_of_vehicle_weight"] * ovt) + bc * cost


# ---------- a rail network: stations, links, the fastest path ----------
class RailNetwork:
    """Stations {name: (lat, lon)} and links [(a, b, track_km)] run at one average speed with a
    stop at every intermediate station. Each zone uses the station nearest its people on average
    (people-weighted mean distance from its counties), if that's within `reach_km`."""

    def __init__(self, stations, links, svc, reach_km=60):
        self.stations, self.svc, self.reach_km = stations, svc, reach_km
        self._cache, self._ends_cache = {}, {}
        self.adj = defaultdict(list)
        for a, b, track in links:
            t = track / svc["speed_kmh"] * 60
            self.adj[a].append((b, t, track))
            self.adj[b].append((a, t, track))

    def _paths_from(self, a):
        if a not in self._cache:
            best = {a: (0.0, 0.0)}
            heap = [(0.0, 0.0, a)]
            while heap:
                t, k, s = heapq.heappop(heap)
                if t > best[s][0]:
                    continue
                for n, dt, dk in self.adj[s]:
                    nt = t + dt + (self.svc["stop_min"] if s != a else 0)
                    if n not in best or nt < best[n][0]:
                        best[n] = (nt, k + dk)
                        heapq.heappush(heap, (nt, k + dk, n))
            self._cache[a] = best
        return self._cache[a]

    def nearest(self, at):
        """(station, km) nearest a point, or (None, km) beyond reach."""
        name, d = min(((s, km(at, ll)) for s, ll in self.stations.items()), key=lambda x: x[1])
        return (name, d) if d <= self.reach_km else (None, d)

    def _ends(self, zone):
        """[(county point, share of the zone's people, station or None, km to it)] for a zone."""
        key = id(zone)
        if key not in self._ends_cache:
            parts = zone["parts"] or [(zone["at"], 1)]
            total = sum(n for _, n in parts) or 1
            self._ends_cache[key] = [(at, n / total) + self.nearest(at) for at, n in parts]
        return self._ends_cache[key]

    def odds(self, za, zb, purpose, p, local_kmh=60):
        """Rail's odds against car for a zone pair: the people-weighted average over its county
        pairs of exp(V_rail - V_car + constant). Car is measured county to county; a county beyond
        reach of a station, or a county pair under `min_km` apart, adds nothing."""
        s = self.svc
        fixed = s["access_min"] + s["egress_min"] + s["terminal_min"] + min(s["headway_min"] / 2, s["max_wait_min"])
        ea = [e for e in self._ends(za) if e[2]]
        eb = [e for e in self._ends(zb) if e[2]]
        acc = 0.0
        for at_a, wa, sa, da in ea:
            paths = self._paths_from(sa)
            for at_b, wb, sb, db in eb:
                if sa == sb or sb not in paths:
                    continue
                dist = km(at_a, at_b)
                if dist < p["min_km"]:
                    continue
                ride, track = paths[sb]
                los = (ride, fixed + (da + db) / local_kmh * 60, s["fare_fixed"] + s["fare_per_km"] * track)
                v_car = utility(car_los(dist, purpose, p), purpose, p)
                acc += wa * wb * math.exp(utility(los, purpose, p) - v_car + s["asc_vs_car"])
        return acc

    def station_for(self, zone):
        parts = zone["parts"] or [(zone["at"], 1)]
        people = sum(n for _, n in parts) or 1
        name, d = min(((s, sum(km(at, ll) * n for at, n in parts) / people) for s, ll in self.stations.items()),
                      key=lambda x: x[1])
        return (name, d) if d <= self.reach_km else (None, d)

    def path(self, a, b):
        """(minutes including intermediate stops, track km), or None."""
        best = {a: (0.0, 0.0)}
        heap = [(0.0, 0.0, a)]
        while heap:
            t, k, s = heapq.heappop(heap)
            if s == b:
                return t, k
            if t > best[s][0]:
                continue
            for n, dt, dk in self.adj[s]:
                nt = t + dt + (self.svc["stop_min"] if s != a else 0)
                if n not in best or nt < best[n][0]:
                    best[n] = (nt, k + dk)
                    heapq.heappush(heap, (nt, k + dk, n))
        return None

    def los(self, za, zb, purpose, p, local_kmh=60):
        """In-vehicle, out-of-vehicle minutes and fare for a zone pair, or None if the network
        doesn't serve it. Getting from a zone's people to its station is out-of-vehicle time."""
        (sa, da), (sb, db) = self.station_for(za), self.station_for(zb)
        if not sa or not sb or sa == sb:
            return None
        route = self.path(sa, sb)
        if route is None:
            return None
        ride, track = route
        s = self.svc
        ovt = (s["access_min"] + s["egress_min"] + s["terminal_min"] + min(s["headway_min"] / 2, s["max_wait_min"])
               + (da + db) / local_kmh * 60)
        return ride, ovt, s["fare_fixed"] + s["fare_per_km"] * track


def nested_split(s_car, s_air, rail_odds, scale):
    """Shares (car, air, rail) when rail joins: car alone, air and rail in a nest with scale
    `scale` (1 = plain logit; smaller = air and rail closer substitutes). Today's shares stand
    for exp(utility); rail's utility is car's plus log(rail_odds). Without rail it returns
    today's shares."""
    if rail_odds <= 0:
        return s_car, s_air, 0.0
    w_rail = math.log(s_car) + math.log(rail_odds)
    terms = [math.exp(w_rail / scale)] + ([math.exp(math.log(s_air) / scale)] if s_air > 0 else [])
    inclusive = scale * math.log(sum(terms))
    nest = math.exp(inclusive) / (s_car + math.exp(inclusive))
    within_rail = terms[0] / sum(terms)
    return (1 - nest), nest * (1 - within_rail), nest * within_rail


def run(base, zones, p, network=None, growth=None):
    """Mode split for every pair, today and with `network` (a RailNetwork, high-speed by default).
    `growth` ({zone: population factor}, from zone_growth) scales each pair's trips by the
    geometric mean of its two zones' growth. Returns {pair: {km, base: {car, air}, new: {car, air,
    rail, induced}}} in daily person-trips; `induced` is extra rail travel on top of `rail`."""
    out = {}
    for pair, d in base.items():
        g = math.sqrt(growth[pair[0]] * growth[pair[1]]) if growth else 1.0
        total = (d["car"] + d["air"]) * g
        if total <= 0:
            continue
        res = {"km": d["km"], "base": {"car": d["car"] * g, "air": d["air"] * g},
               "new": {"car": 0.0, "air": 0.0, "rail": 0.0, "induced": 0.0}}
        for purpose, share in (("work", d["work_share"]), ("nonwork", 1 - d["work_share"])):
            trips = total * share
            s_car, s_air = d["car"] / (d["car"] + d["air"]), d["air"] / (d["car"] + d["air"])
            rail_odds = 0.0   # rail's odds against car: exp(V_rail + asc - V_car)
            if network is not None:
                rail_odds = network.odds(zones[pair[0]], zones[pair[1]], purpose, p)
            # pivot point: today's shares stand for exp(V + pair constant); rail joins relative to car
            c, a, r = nested_split(s_car, s_air, rail_odds, p["nest_public_scale"]) if s_car > 0 else (0, s_air, 0)
            res["new"]["car"] += trips * c
            res["new"]["air"] += trips * a
            res["new"]["rail"] += trips * r
        res["new"]["induced"] = res["new"]["rail"] * p["hsr"].get("induced_share", 0.0)
        out[pair] = res
    return out


def flights_per_day(air_trips, p):
    """Daily departures (both directions) to carry a pair's air trips."""
    a = p["air"]
    return air_trips / (a["seats_per_flight"] * a["load_factor"])
