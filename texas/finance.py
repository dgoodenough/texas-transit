"""Money beyond the statewide $9.0B a year, for the "whole map" scenario (study/hsr_buildout.md,
Phase 2; study/cabinet/finance.md). Central values from the Finance Secretary's memo; each is a
policy the Legislature, Congress or a neighbouring state would have to adopt.

  RAIL_FUND        1/8 cent of sales tax into the Rail Relocation and Improvement Fund (Texas
                   Constitution Art. III §49-o, created 2005, never funded) from 2030: about $0.98B a
                   year at FY2025 collections, growing with Texas's population. Ring-fenced for the
                   Connectivity Program (CONNECTIVITY): the branch corridors and, first, their
                   operating deficits.
  TRIANGLE_SURPLUS the high-speed lines outside the program run an operating surplus once built;
                   pledged to the program (rail revenue bonds), net of any deficit among them.
  FEDERAL_SHARE    federal match on the capital of every high-speed line's track in Texas (FRA
                   Federal-State Partnership and successors; 10%, central; the 2025 cuts show it can
                   vanish). The whole map only.
  OUT_FEDERAL_SHARE  federal share of the track outside Texas, granted to the state it runs in: a
                   line into Oklahoma or Louisiana is that state's project as much as Texas's, and the
                   federal money for its part goes there (the Federal-State Partnership pays up to 80%;
                   half, central). In every scenario.
  PARTNER_SHARE    the other state pays this share of the track in it (interstate compacts); with the
                   federal share, all of it, so none of it comes out of Texas's budget. In every
                   scenario; Mexico pays for its side of the border (the Monterrey line) whole.
"""
import functools
import json
import os

RAIL_FUND = {"start": 2030, "musd_per_year": 980.0}
TRIANGLE_SURPLUS = True
FEDERAL_SHARE = 0.10
OUT_FEDERAL_SHARE = 0.50
PARTNER_SHARE = 0.50
# The Connectivity Program's corridors; Houston - Victoria - Corpus Christi joined in the third session (item 9: the
# Gulf spine early, so the Valley's branches don't wait on a trunk low in the queue)
CONNECTIVITY = ["hsr:OKC", "hsr:LRD", "hsr:VALLEY", "hsr:MFE", "hsr:BIGC", "hsr:PANH", "hsr:WEST", "hsr:CC"]


def rail_fund(year, pop=None, base_year=2025):
    """$M the Rail Fund raises in `year` (0 before it starts), growing with Texas's population."""
    if year < RAIL_FUND["start"]:
        return 0.0
    g = pop[year] / pop[base_year] if pop else 1.0
    return RAIL_FUND["musd_per_year"] * g


@functools.lru_cache(maxsize=1)
def _texas():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "texas_outline.json")
    return json.load(open(path, encoding="utf-8"))["rings_lonlat"]


def in_texas(lat, lon):
    """Inside Texas's outline (texas/texas_outline.json, from the Census cartographic boundary)."""
    inside = False
    for ring in _texas():
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def in_mexico(lat, lon):
    """Well into Mexico: south of Laredo (the Monterrey line). The outline is coarse along the Rio Grande,
    so a point just across it farther north (I-10 into El Paso) is border noise, counted as Texas."""
    return lat < 27.3 and lon < -97.1 and not in_texas(lat, lon)


def _border_noise(lat, lon):
    return lat < 31.9 and lon < -97.1 and not in_mexico(lat, lon)


def route_shares(points):
    """(share in another US state, share in Mexico) of a polyline's length (list of (lat, lon))."""
    from texas.intercity import km
    total = us = mx = 0.0
    for (a, b) in zip(points, points[1:]):
        d = km(a, b)
        n = max(1, int(d // 5))
        for k in range(n):
            t = (k + 0.5) / n
            la, lo = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            total += d / n
            if not in_texas(la, lo) and not _border_noise(la, lo):
                if in_mexico(la, lo):
                    mx += d / n
                else:
                    us += d / n
    return (us / total, mx / total) if total else (0.0, 0.0)


def out_of_state_share(chain_points):
    """Share of a polyline's length outside Texas (another state or Mexico)."""
    return sum(route_shares(chain_points))


def paid_by_others(capital, shares, federal_in=0.0, federal_out=None, partner=None):
    """$M of `capital` that doesn't come out of Texas's budget. shares: (other US state, Mexico) of the
    route. The track outside Texas: the federal share granted to the state it runs in plus that state's
    own share (all of it, central); Mexico's side, all of it; the track in Texas: `federal_in`."""
    us, mx = shares
    federal_out = OUT_FEDERAL_SHARE if federal_out is None else federal_out
    partner = PARTNER_SHARE if partner is None else partner
    return capital * ((1.0 - us - mx) * federal_in + us * min(1.0, federal_out + partner) + mx)


@functools.lru_cache(maxsize=None)
def corridor_shares(cid):
    """(other US state, Mexico) shares of a high-speed corridor's track, along its drawn alignment."""
    from texas import hsr
    chain = hsr.CORRIDORS[cid][1]
    pts = [hsr.point(chain[0])]
    for a, b in zip(chain, chain[1:]):
        pts += [tuple(p) for p in hsr._alignments().get((a, b), [])] + [hsr.point(b)]
    return route_shares(pts)


@functools.lru_cache(maxsize=None)
def conventional_shares(cid):
    """(other US state, Mexico) shares of a conventional corridor, along its stations."""
    from texas import conventional as cv
    return route_shares([cv.point(s) for s in cv.CORRIDORS[cid][1]])


def corridor_out_of_state(cid):
    """Share of a high-speed corridor's track outside Texas, along its drawn alignment."""
    return sum(corridor_shares(cid))
