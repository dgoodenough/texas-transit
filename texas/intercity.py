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
    add_border_twins(out, zones, p)
    return out


def add_border_twins(base, zones, p):
    """Trips by the Mexican twin cities' residents (p["border_twins"]): each border zone's pairs with
    the rest of Texas and beyond grow by factor x twin-city people / the zone's people (in place)."""
    bt = p.get("border_twins") or {}
    f = bt.get("factor", 0.0)
    if not f:
        return base
    for pair, d in base.items():
        for z in pair:
            other = pair[1] if z == pair[0] else pair[0]
            if z in bt["cities"] and other not in bt["cities"] and zones[other]["state"] != "MX":
                k = 1 + f * bt["cities"][z][1] / zones[z]["pop"]
                d["car"] *= k
                d["air"] *= k
                d["border_twins"] = k
    return base


# ---------- level of service: (in-vehicle minutes, out-of-vehicle minutes, cost per person) ----------
def car_los(dist, purpose, p):
    c = p["car"]
    road = dist * c["circuity"]
    per_vkm = c["cost_per_vehicle_km"] + (p.get("policy") or {}).get("car_toll_per_vkm", 0.0)
    return road / c["speed_kmh"] * 60, c["terminal_min"], road * per_vkm / p["purposes"][purpose]["occupancy"]


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


def wait_min(svc, headway_min=None):
    """Waiting for a train: a share of the headway (half for a turn-up-and-go service; less when
    people plan around a timetable), capped. `headway_min` overrides the service's own."""
    h = svc["headway_min"] if headway_min is None else headway_min
    return min(h * svc.get("wait_share", 0.5), svc["max_wait_min"])


# ---------- a rail network: stations, links, the fastest path ----------
class RailNetwork:
    """Stations {name: (lat, lon)} and links [(a, b, track_km)] run at one average speed with a
    stop at every intermediate station. Each zone uses the station nearest its people on average
    (people-weighted mean distance from its counties), if that's within `reach_km`.

    Every trip waits for svc's one headway, unless `services` gives service patterns: [(chain of
    stations, headway minutes)], e.g. the two branches of a wye. Then a trip between two stations
    waits for the trains of every pattern calling at both (their frequencies add); a trip no single
    pattern serves waits for the least frequent link of its fastest route (a link's frequency is
    that of the patterns running over it; a link no pattern runs takes svc's headway), plus
    svc's transfer_min for changing trains (transfer)."""

    def __init__(self, stations, links, svc, reach_km=60, services=None):
        self.stations, self.svc, self.reach_km = stations, svc, reach_km
        self.services = services
        self._cache, self._ends_cache, self._wait_cache = {}, {}, {}
        self.adj = defaultdict(list)
        for a, b, track in links:
            t = track / svc["speed_kmh"] * 60
            self.adj[a].append((b, t, track))
            self.adj[b].append((a, t, track))
        self._link_freq = defaultdict(float)   # trains an hour each way over a link, from the patterns
        for chain, h in services or ():
            for a, b in zip(chain, chain[1:]):
                self._link_freq[tuple(sorted((a, b)))] += 60 / h

    def route(self, a, b):
        """Stations along the fastest path from a to b (as `path` times it), or None."""
        best, prev = {a: 0.0}, {a: None}
        heap = [(0.0, a)]
        while heap:
            t, s = heapq.heappop(heap)
            if s == b:
                out = [b]
                while prev[out[-1]] is not None:
                    out.append(prev[out[-1]])
                return out[::-1]
            if t > best[s]:
                continue
            for n, dt, _ in self.adj[s]:
                nt = t + dt + (self.svc["stop_min"] if s != a else 0)
                if n not in best or nt < best[n]:
                    best[n], prev[n] = nt, s
                    heapq.heappush(heap, (nt, n))
        return None

    def headway(self, a, b):
        """Minutes between trains from station a to station b (see the class notes)."""
        if not self.services:
            return self.svc["headway_min"]
        direct = sum(60 / h for chain, h in self.services if a in chain and b in chain)
        if direct > 0:
            return 60 / direct
        stops = self.route(a, b) or [a, b]
        return max(60 / self._link_freq[tuple(sorted(k))] if self._link_freq[tuple(sorted(k))] else
                   self.svc["headway_min"] for k in zip(stops, stops[1:]))

    def transfer(self, a, b):
        """Minutes for changing trains (svc transfer_min) when service patterns are given and none
        calls at both stations; 0 otherwise (without patterns every pair is a one-seat ride)."""
        if not self.services or self.svc.get("transfer_min", 0) == 0:
            return 0.0
        return 0.0 if any(a in chain and b in chain for chain, _ in self.services) else self.svc["transfer_min"]

    def wait(self, a, b):
        """Minutes waiting for a train from station a to station b."""
        if (a, b) not in self._wait_cache:
            self._wait_cache[(a, b)] = wait_min(self.svc, self.headway(a, b) if self.services else None)
        return self._wait_cache[(a, b)]

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
        fixed = s["access_min"] + s["egress_min"] + s["terminal_min"]
        border = za.get("border_min", 0) + zb.get("border_min", 0)   # both modes wait at the border
        ea = [e for e in self._ends(za) if e[2]]
        eb = [e for e in self._ends(zb) if e[2]]
        acc = 0.0
        for at_a, wa, sa, da in ea:
            paths = self._paths_from(sa)
            for at_b, wb, sb, db in eb:
                if sa == sb or sb not in paths:
                    continue
                dist = km(at_a, at_b)
                if dist < s.get("min_km", p["min_km"]):
                    continue
                ride, track = paths[sb]
                los = (ride, fixed + self.wait(sa, sb) + self.transfer(sa, sb) + border + (da + db) / local_kmh * 60,
                       s["fare_fixed"] + s["fare_per_km"] * track)
                ivt, ovt, cost = car_los(dist, purpose, p)
                v_car = utility((ivt + border, ovt, cost), purpose, p)
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
        ovt = (s["access_min"] + s["egress_min"] + s["terminal_min"] + self.wait(sa, sb) + self.transfer(sa, sb)
               + (da + db) / local_kmh * 60
               + za.get("border_min", 0) + zb.get("border_min", 0))
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


def logsum_gain(s_car, s_air, rail_odds, scale):
    """Change in the logsum (utils per traveller) when rail joins: today's shares stand for
    exp(utility), so today's logsum is ln(s_car + s_air) = 0 and the new one is ln(s_car + exp(I)),
    I the air-rail nest's inclusive value. Divided by the cost coefficient it is the traveller's
    gain in dollars (consumer surplus)."""
    if rail_odds <= 0 or s_car <= 0:
        return 0.0
    w_rail = math.log(s_car) + math.log(rail_odds)
    terms = [math.exp(w_rail / scale)] + ([math.exp(math.log(s_air) / scale)] if s_air > 0 else [])
    return math.log(s_car + math.exp(scale * math.log(sum(terms))))


def policy_shares(d, purpose, p):
    """Today's car and air shares of a pair with the policy's charges on car and air (p["policy"]):
    each mode's weight times exp(cost coefficient x the extra charge), renormalized. Without a policy,
    today's shares."""
    s_car, s_air = d["car"] / (d["car"] + d["air"]), d["air"] / (d["car"] + d["air"])
    pol = p.get("policy") or {}
    toll, sur = pol.get("car_toll_per_vkm", 0.0), pol.get("air_surcharge", 0.0)
    if not toll and not sur:
        return s_car, s_air
    bc = p["cost_coef_per_dollar"][purpose]
    w_car = s_car * math.exp(bc * toll * d["km"] * p["car"]["circuity"] / p["purposes"][purpose]["occupancy"])
    w_air = s_air * math.exp(bc * sur)
    return w_car / (w_car + w_air), w_air / (w_car + w_air)


def run(base, zones, p, network=None, growth=None, year=None):
    """Mode split for every pair, today and with `network` (a RailNetwork, high-speed by default).
    `growth` ({zone: population factor}, from zone_growth) scales each pair's trips by the
    geometric mean of its two zones' growth. Returns {pair: {km, base: {car, air}, new: {car, air,
    rail, induced}, benefit_usd}} in daily person-trips; `induced` is extra rail travel on top of `rail`;
    `benefit_usd` is the travellers' gain a day (logsum_gain), induced trips' own gain left out.
    Growth enters as (g_a x g_b) ^ growth_elasticity; with `year`, trips per person also grow with
    income_growth_per_year from 2022. Charges on car and air (p["policy"]) shift today's split before
    rail joins, so the gain is measured against a world with the same charges; an air ban
    (air_ban_rail_minutes) drops air on pairs where rail's ride is shorter, once rail runs."""
    out = {}
    e = p.get("growth_elasticity", 0.5)
    inc = (1 + p.get("income_growth_per_year", 0.0)) ** max(0, (year or 2022) - 2022)
    ban = (p.get("policy") or {}).get("air_ban_rail_minutes", 0)
    for pair, d in base.items():
        g = ((growth[pair[0]] * growth[pair[1]]) ** e if growth else 1.0) * inc
        total = (d["car"] + d["air"]) * g
        if total <= 0:
            continue
        s0 = [policy_shares(d, pu, p) for pu in ("work", "nonwork")]
        wk = d["work_share"]
        res = {"km": d["km"], "base": {"car": total * (wk * s0[0][0] + (1 - wk) * s0[1][0]),
                                       "air": total * (wk * s0[0][1] + (1 - wk) * s0[1][1])},
               "new": {"car": 0.0, "air": 0.0, "rail": 0.0, "induced": 0.0}, "benefit_usd": 0.0}
        banned = False
        if ban and network is not None:
            los = network.los(zones[pair[0]], zones[pair[1]], "work", p)
            banned = los is not None and los[0] < ban
        for purpose, share in (("work", d["work_share"]), ("nonwork", 1 - d["work_share"])):
            trips = total * share
            s_car, s_air = policy_shares(d, purpose, p)
            rail_odds = 0.0   # rail's odds against car: exp(V_rail + asc - V_car)
            if network is not None:
                rail_odds = network.odds(zones[pair[0]], zones[pair[1]], purpose, p)
            if banned and rail_odds > 0:   # no flights once rail runs: air's travellers choose car or rail
                c, _, r = nested_split(s_car, 0.0, rail_odds, p["nest_public_scale"])
                res["new"]["car"] += trips * c
                res["new"]["rail"] += trips * r
                res["benefit_usd"] += trips * logsum_gain(s_car, 0.0, rail_odds, p["nest_public_scale"]) / \
                    abs(p["cost_coef_per_dollar"][purpose])
                continue
            # pivot point: today's shares stand for exp(V + pair constant); rail joins relative to car
            c, a, r = nested_split(s_car, s_air, rail_odds, p["nest_public_scale"]) if s_car > 0 else (0, s_air, 0)
            res["new"]["car"] += trips * c
            res["new"]["air"] += trips * a
            res["new"]["rail"] += trips * r
            if rail_odds > 0:   # travellers' gain, $ a day (induced trips' own gain is left out)
                res["benefit_usd"] += trips * logsum_gain(s_car, s_air, rail_odds, p["nest_public_scale"]) / \
                    abs(p["cost_coef_per_dollar"][purpose])
        svc = network.svc if network is not None else p["hsr"]
        res["new"]["induced"] = res["new"]["rail"] * svc.get("induced_share", 0.0)
        out[pair] = res
    return out


def flights_per_day(air_trips, p):
    """Daily departures (both directions) to carry a pair's air trips."""
    a = p["air"]
    return air_trips / (a["seats_per_flight"] * a["load_factor"])
