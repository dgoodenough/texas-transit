"""A cross-border line: El Paso - Ciudad Juárez (study/second_session.md, item 19).

    python tools/fetch_juarez.py        (once: data/urban/juarez_cells.csv)
    python study/cross_border.py        -> study/cross_border.md, study/cross_border.json

El Paso's planner asked for a line into Juárez once border demand was in the metros (item 18, done:
the people who cross on foot or by bus are in El Paso's trip tables at their bridge). The census and LODES
stop at the river, so this is a study of its own, not the generator's:

  Juárez    500 m cells (tools/fetch_juarez.py: Overture building footprints and places); people in
            proportion to footprint area, scaled to the municipio's 2020 census count (INEGI: 1,512,450).
            A cell is Mexican when most of its places have a Mexican address; cells with no places take
            their neighbours' side.
  Crossers  the downtown El Paso port (BTS 2024, data/urban/border_crossings.json): 13,899 people a day
            north on foot or by bus, and 34,909 in cars. Each is assumed to cross back the same day.
            Where they start: Juárez's people near the downtown bridges rather than Ysleta's,
            weighted exp(-d / 5 km) by distance to the bridge.
  Today     a walker reaches the bridge on foot (up to 2 km) or by Juárez bus: a 5-minute walk, an
            8-minute wait, and the trip at 15 km/h on roads 1.3 times the straight line. A car
            passenger drives at 30 km/h and waits in the vehicle queue.
  The line  a streetcar or BRT from San Jacinto Plaza (El Paso's streetcar) over the Paso del Norte
            bridge, routed on Juárez's streets (the generator's BRT street profile) to one of several
            ends in Juárez. Stations every 800 m; riders within 1 km walk to them. Inspection at a
            station by the bridge, as on foot today.
  Choice    a binary logit on generalized minutes (walking and waiting count double, fares at the
            value of time, scale 5 min). Walkers and bus riders keep their pedestrian lane wait either way.
            Car passengers compare the line, plus the pedestrian wait, with driving plus the vehicle
            queue: VEHICLE_WAIT_MIN against PED_WAIT_MIN, assumptions (CBP publishes live waits, not
            averages, and none are reachable from here). Their car bias is CAR_BIAS_MIN, and only the
            share of El Paso's jobs within 800 m of a station (the plan's network) can be reached by transit.
  Value     generalized minutes saved at USDOT's local value of time (about $19 an hour), rule of a
            half for new riders, fares, the timing study's wider benefits for each car trip off the road,
            less operating cost, over 50 years at 3%, against capital. Texas pays for the track on its
            side and for the inspection station; Mexico pays for its side, as for the Monterrey line
            (texas/finance.py).
"""
import csv
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor", "dfw-transit"))
sys.path.insert(0, os.path.join(ROOT, "study"))
os.environ.setdefault("METRO_HOME", os.path.join(ROOT, "urban"))

import numpy as np  # noqa: E402

JUAREZ_POP = 1_512_450          # INEGI, Censo de Población y Vivienda 2020, municipio de Juárez
VOT = 19.0                      # $ an hour: USDOT benefit-cost guidance, local personal travel (about)
WALK_KMH, BUS_KMH, CAR_KMH, CIRCUITY = 4.8, 15.0, 30.0, 1.3
BUS_WALK, BUS_WAIT = 5.0, 8.0
JUAREZ_BUS_FARE, LINE_FARE = 0.6, 1.25
PED_WAIT_MIN, VEHICLE_WAIT_MIN = 20.0, 45.0
CAR_BIAS_MIN = 15.0
SCALE_MIN = 5.0
ORIGIN_KM = 5.0
STATION_KM, WALK_REACH_KM = 0.8, 1.0
INSPECTION_MUSD = (75.0, 150.0, 300.0)    # low, central, high: a transit inspection station at the bridge
DAYS = 300
PV = (1 - 1.03 ** -50) / 0.03
KMH = {"streetcar": 15.0, "brt": 20.0}
HEADWAY = {"streetcar": 10, "brt": 8}

DOWNTOWN_EP = (31.7587, -106.4869)        # San Jacinto Plaza: El Paso's streetcar
BRIDGE_MX = (31.7450, -106.4866)          # Paso del Norte bridge, the Juárez end (Av. Juárez)
YSLETA = (31.6726, -106.3352)


def km(a, b):
    return math.hypot((a[0] - b[0]) * 110.57, (a[1] - b[1]) * 111.32 * math.cos(math.radians(a[0])))


def cells():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "urban", "juarez_cells.csv"), encoding="utf-8")))
    lat = np.array([float(r["lat"]) for r in rows])
    lon = np.array([float(r["lon"]) for r in rows])
    m2 = np.array([float(r["building_m2"]) for r in rows])
    mx, us = np.array([int(r["places_mx"]) for r in rows]), np.array([int(r["places_us"]) for r in rows])
    side = np.where(mx > us, 1, np.where(us > mx, -1, 0))
    known = side != 0
    for i in np.where(~known)[0]:   # no places, or a tie: the side of its five nearest known neighbours
        d = (lat[known] - lat[i]) ** 2 + ((lon[known] - lon[i]) * 0.85) ** 2
        side[i] = 1 if side[known][np.argsort(d)[:5]].sum() > 0 else -1
    is_mx = side > 0
    pop = np.where(is_mx, m2, 0.0)
    pop = pop / pop.sum() * JUAREZ_POP
    return lat, lon, pop, is_mx


def crossers():
    d = json.load(open(os.path.join(ROOT, "data", "urban", "border_crossings.json"), encoding="utf-8"))
    p = next(p for p in d["ports"] if p["port_code"] == "2402")
    return p.get("pedestrians_day", 0) + p.get("bus_passengers_day", 0), p.get("personal_vehicle_passengers_day", 0), d["year"]


def origins(lat, lon, pop, is_mx):
    """Each cell's share of the downtown port's crossers."""
    d_br = np.array([km((a, b), BRIDGE_MX) for a, b in zip(lat, lon)])
    d_ys = np.array([km((a, b), YSLETA) for a, b in zip(lat, lon)])
    w = np.where(is_mx & (d_br <= d_ys), pop * np.exp(-d_br / ORIGIN_KM), 0.0)
    return w / w.sum(), d_br


def today_minutes(d_br):
    """Generalized minutes to the bridge today: walk, or Juárez bus (walk and wait x2, fare at VOT)."""
    walk = np.where(d_br <= 2.0, 2 * d_br / WALK_KMH * 60, np.inf)
    bus = 2 * (BUS_WALK + BUS_WAIT) + d_br * CIRCUITY / BUS_KMH * 60 + JUAREZ_BUS_FARE / VOT * 60
    return np.minimum(walk, bus)


def line_minutes(lat, lon, stations, along, mode):
    """Generalized minutes to the bridge by the line: walk to the nearest station (within WALK_REACH_KM),
    wait half the headway, ride. stations: [(lat, lon)], along: km from each to the bridge."""
    best = np.full(len(lat), np.inf)
    for (a, b), s in zip(stations, along):
        dw = np.hypot((lat - a) * 110.57, (lon - b) * 111.32 * math.cos(math.radians(a)))
        t = np.where(dw <= WALK_REACH_KM, 2 * dw / WALK_KMH * 60 + 2 * HEADWAY[mode] / 2 + s / KMH[mode] * 60, np.inf)
        best = np.minimum(best, t)
    return best + LINE_FARE / VOT * 60


def logit(gain):
    return 1 / (1 + np.exp(-np.clip(gain, -500, 500) / SCALE_MIN))


def ends(lat, lon, pop, is_mx):
    """Ends for the line in Juárez: in each 45-degree sector from the bridge, at about 5, 9 and 13 km, the
    busiest cell within 1.5 km of the ring."""
    out = []
    for ang in range(0, 360, 45):
        for r in (5.0, 9.0, 13.0):
            a = BRIDGE_MX[0] + r * math.sin(math.radians(ang)) / 110.57
            b = BRIDGE_MX[1] + r * math.cos(math.radians(ang)) / (111.32 * math.cos(math.radians(BRIDGE_MX[0])))
            d = np.hypot((lat - a) * 110.57, (lon - b) * 111.32 * math.cos(math.radians(a)))
            ok = is_mx & (d <= 1.5)
            if ok.any():
                i = int(np.argmax(np.where(ok, pop, -1)))
                out.append((ang, r, (float(lat[i]), float(lon[i]))))
    return out


def evaluate(route, lat, lon, pop, is_mx, w, d_br, t0, ped, car, reach, cfg, inspection):
    """A line along `route` [(lat, lon)] from downtown El Paso into Juárez. Returns its numbers."""
    from metro import candidates
    cum = [0.0]
    for p, q in zip(route, route[1:]):
        cum.append(cum[-1] + km(p, q))
    L = cum[-1]
    # where it reaches Mexico: the first point in a Mexican cell (nearest cell)
    def mexican(p):
        i = int(np.argmin((lat - p[0]) ** 2 + ((lon - p[1]) * 0.85) ** 2))
        return bool(is_mx[i])
    k_mx = next((k for k, p in enumerate(route) if mexican(p)), len(route) - 1)
    s_bridge = cum[k_mx]
    stations, along = [], []
    s = s_bridge
    while s <= L + 1e-6:
        k = min(range(len(cum)), key=lambda j: abs(cum[j] - s))
        stations.append(route[k])
        along.append(s - s_bridge)
        s += STATION_KM
    out = {}
    for mode in ("streetcar", "brt"):
        t1 = line_minutes(lat, lon, stations, along, mode)
        # walkers and bus riders: same pedestrian wait either way
        p_ped = logit(t0 - t1)
        gain_ped = np.maximum(t0 - t1, 0)
        riders_ped = ped * float((w * p_ped).sum())
        benefit_ped_min = ped * float((w * p_ped * gain_ped).sum())
        # car passengers: drive and the vehicle queue, against the line and the pedestrian lane
        t_car = d_br * CIRCUITY / CAR_KMH * 60 + VEHICLE_WAIT_MIN + CAR_BIAS_MIN
        t_line = t1 + PED_WAIT_MIN
        p_car = logit(t_car - t_line) * reach
        riders_car = car * float((w * p_car).sum())
        benefit_car_min = car * float((w * p_car * np.maximum(t_car - t_line, 0) / 2).sum())   # rule of a half
        riders = riders_ped + riders_car            # people a day, each crossing north and back
        trips = 2 * riders
        ben = 2 * (benefit_ped_min + benefit_car_min) / 60 * VOT * DAYS / 1e6        # $M a year
        import timing
        wider = 2 * riders_car * timing.URBAN_WIDER_PER_TRIP * DAYS / 1e6
        fares = trips * LINE_FARE * DAYS / 1e6
        stops = [(0.0, None, None)] + [(s_bridge + x, None, None) for x in along]
        opex = candidates.opex_musd(cfg, mode, stops, HEADWAY[mode])
        per_km = cfg["cost_musd_per_km"][mode]
        bridge_km = 0.6
        cap_us = s_bridge * per_km["surface"] + bridge_km * (per_km["elevated"] - per_km["surface"]) / 2
        cap_mx = (L - s_bridge) * per_km["surface"] + bridge_km * (per_km["elevated"] - per_km["surface"]) / 2
        n_st = len(stations) + 2
        st = cfg["station_cost_musd"][mode]
        cap_us += 2 * st
        cap_mx += len(stations) * st
        cap_us += inspection
        net = ben + wider + fares - opex
        texas_cost = cap_us + max(opex - fares, 0) * PV * (s_bridge / L if L else 1)
        out[mode] = {"km": L, "km_mexico": L - s_bridge, "stations": n_st, "riders_day": riders, "trips_day": trips,
                     "from_walk_bus": riders_ped, "from_cars": riders_car,
                     "benefit": ben, "wider": wider, "fares": fares, "opex": opex,
                     "capital": cap_us + cap_mx, "capital_texas": cap_us, "capital_mexico": cap_mx,
                     "ratio": (ben + wider + max(fares - opex, 0)) * PV / (cap_us + cap_mx + max(opex - fares, 0) * PV),
                     "ratio_texas": (ben + wider + max(fares - opex, 0)) * PV / texas_cost if texas_cost else None,
                     "new_trips_day": 2 * riders_car,
                     "trips_per_musd": 2 * riders_car / (cap_us + cap_mx + 20 * opex),
                     "net_year": net}
    return out


def jobs_reach(m):
    """The share of El Paso's jobs within 800 m of a station of the plan's network (generated and today's)."""
    st = []
    for f in (os.path.join(ROOT, "urban", "generated", "el-paso", "stations.csv"),
              os.path.join(ROOT, "urban", "data", "metros", "el-paso", "existing", "stations.csv")):
        if os.path.exists(f):
            st += [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open(f, encoding="utf-8"))]
    near = np.zeros(len(m.lat), bool)
    for a, b in st:
        near |= np.hypot((m.lat - a) * 110.57, (m.lon - b) * 111.32 * math.cos(math.radians(a))) <= 0.8
    return float(m.jobs[near].sum() / max(m.jobs.sum(), 1.0))


def main():
    from dfwt import config as dconfig
    from metro import inputs, routing
    lat, lon, pop, is_mx = cells()
    w, d_br = origins(lat, lon, pop, is_mx)
    ped, car, year = crossers()
    t0 = today_minutes(d_br)
    cfg = dconfig.load()
    m = inputs.load("el-paso")
    reach = jobs_reach(m)
    R = routing.Router(m)
    res = []
    for ang, r, end in ends(lat, lon, pop, is_mx):
        P = R.route_multi("brt", [DOWNTOWN_EP, BRIDGE_MX, end])
        if not P:
            print(f"  no route to the end at {ang} degrees, {r:.0f} km")
            continue
        ev = evaluate(P, lat, lon, pop, is_mx, w, d_br, t0, ped, car, reach, cfg, INSPECTION_MUSD[1])
        res.append({"bearing": ang, "ring_km": r, "end": end, "route": P, "modes": ev})
        e = ev["streetcar"]
        print(f"  {ang:3d} deg {r:4.0f} km: {e['km']:.1f} km, {e['riders_day']:,.0f} riders a day, ratio {e['ratio']:.2f}")
    res.sort(key=lambda x: -max(v["ratio"] for v in x["modes"].values()))
    best = res[0]
    mode = max(best["modes"], key=lambda k: best["modes"][k]["ratio"])
    sens = {}
    for lab, insp in zip(("low", "central", "high"), INSPECTION_MUSD):
        sens[f"inspection {lab}"] = evaluate(best["route"], lat, lon, pop, is_mx, w, d_br, t0, ped, car, reach, cfg, insp)[mode]
    global VEHICLE_WAIT_MIN, VOT
    for vw in (25.0, 70.0):
        old, VEHICLE_WAIT_MIN = VEHICLE_WAIT_MIN, vw
        sens[f"vehicle queue {vw:.0f} min"] = evaluate(best["route"], lat, lon, pop, is_mx, w, d_br, t0, ped, car, reach, cfg,
                                                       INSPECTION_MUSD[1])[mode]
        VEHICLE_WAIT_MIN = old
    old, VOT = VOT, VOT / 2
    sens["value of time halved"] = evaluate(best["route"], lat, lon, pop, is_mx, w, d_br, t0, ped, car, reach, cfg,
                                            INSPECTION_MUSD[1])[mode]
    VOT = old
    origin_km = float((w * d_br).sum())
    json.dump({"crossers": {"walk_bus": ped, "cars": car, "year": year}, "juarez_pop": JUAREZ_POP,
               "origin_mean_km": origin_km, "options": [{k: v for k, v in x.items() if k != "route"} for x in res],
               "best": {"bearing": best["bearing"], "ring_km": best["ring_km"], "mode": mode, "route": best["route"]},
               "sensitivity": sens},
              open(os.path.join(ROOT, "study", "cross_border.json"), "w", encoding="utf-8"), indent=1)
    write(res, best, mode, sens, ped, car, year, origin_km, reach)


def write(res, best, mode, sens, ped, car, year, origin_km, reach):
    import timing
    B = lambda v: f"${v / 1e3:,.2f}B" if v >= 1000 else f"${v:,.0f}M"  # noqa: E731
    e = best["modes"][mode]
    DIR = {0: "east", 45: "northeast", 90: "north", 135: "northwest", 180: "west", 225: "southwest", 270: "south", 315: "southeast"}
    urban = [p for p in timing.urban_projects() if p["metro"] == "el-paso"]
    for p in urban:
        timing.ratio(p)
    L = ["# A cross-border line: El Paso - Ciudad Juárez", "",
         "Generated by `python study/cross_border.py` (Juárez: `python tools/fetch_juarez.py`). Item 19 of "
         "`study/second_session.md`. The method, its sources and its assumptions are in the script's docstring; in "
         f"short: Juárez's {JUAREZ_POP:,} people (INEGI 2020) placed by building footprints (Overture Maps), the downtown "
         f"port's {ped:,} daily crossers on foot or by bus and {car:,} in cars (BTS {year}) starting where people live "
         f"near the downtown bridges (on average {origin_km:.1f} km from the bridge), and a logit on generalized minutes "
         "against how they reach the bridge today.", "",
         "## The options", "",
         "From San Jacinto Plaza over the Paso del Norte bridge into Juárez, routed on the streets, to the busiest place "
         "in each direction at about 5, 9 and 13 km; the benefit-cost ratio over 50 years at 3% (all costs, both sides):", "",
         "| Toward | Ring | Km (in Mexico) | Streetcar: riders a day, ratio | BRT: riders a day, ratio |",
         "|---|---|---|---|---|"]
    for x in res:
        s_, b_ = x["modes"]["streetcar"], x["modes"]["brt"]
        L.append(f"| {DIR[x['bearing']]} | {x['ring_km']:.0f} km | {s_['km']:.1f} ({s_['km_mexico']:.1f}) | "
                 f"{s_['riders_day']:,.0f}, {s_['ratio']:.2f} | {b_['riders_day']:,.0f}, {b_['ratio']:.2f} |")
    L += ["", f"## The best: {mode} toward the {DIR[best['bearing']]}, {e['km']:.1f} km", "",
          f"- **Riders:** {e['riders_day']:,.0f} people a day ({2 * e['riders_day']:,.0f} trips): {e['from_walk_bus']:,.0f} who "
          f"walk or take a bus to the bridge today, {e['from_cars']:,.0f} out of cars.",
          f"- **Capital:** {B(e['capital'])}: Texas {B(e['capital_texas'])} (its {e['km'] - e['km_mexico']:.1f} km, half the bridge "
          f"and a ${INSPECTION_MUSD[1]:.0f}M inspection station), Mexico {B(e['capital_mexico'])}.",
          f"- **A year:** travellers' gain {B(e['benefit'])}, wider benefits {B(e['wider'])}, fares {B(e['fares'])}, "
          f"operating cost {B(e['opex'])}.",
          f"- **Ratio:** {e['ratio']:.2f} on all costs; {e['ratio_texas']:.2f} on what Texas pays (every crosser's gain counted, "
          "most of them Juárez residents). "
          f"{e['new_trips_day']:,.0f} new transit trips a day (out of cars), {e['trips_per_musd']:.1f} per $M of capital and 20 "
          "years' operating, against the metro plan's floor of 2.5.",
          f"- El Paso's own lines in the plan: ratios {min(p['bcr'] for p in urban):.2f} to {max(p['bcr'] for p in urban):.2f}.", "",
          "**How much rests on the assumptions** (the best option):", "",
          "| Case | Riders a day | Ratio | Ratio, Texas's cost |", "|---|---|---|---|"]
    for k, v in sens.items():
        L.append(f"| {k} | {v['riders_day']:,.0f} | {v['ratio']:.2f} | {v['ratio_texas']:.2f} |")
    L += ["", "**What it leaves out.** Juárez residents' trips within Juárez (Mexico's benefit, not counted); trips south "
          "by El Paso residents; growth; the line feeding El Paso's network beyond downtown (the metro model carries "
          "crossers from the bridge on); and the inspection itself, whose cost and hours set whether a transit lane can "
          "move people faster than the pedestrian queue. The vehicle and pedestrian waits are assumptions, not averages "
          f"of CBP's published waits. The share of El Paso's jobs a car passenger can reach by transit ({reach:.0%}, "
          "within 800 m of a station in the plan) caps how many leave their cars.", ""]
    with open(os.path.join(ROOT, "study", "cross_border.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
