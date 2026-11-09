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
  FEDERAL_SHARE    federal match on every high-speed line's capital (FRA Federal-State Partnership and
                   successors; 10% of capital, central; the 2025 cuts show it can vanish).
  PARTNER_SHARE    Oklahoma and Louisiana pay this share of the track in their states (interstate
                   compacts); the model otherwise charges Texas for it.
"""

RAIL_FUND = {"start": 2030, "musd_per_year": 980.0}
TRIANGLE_SURPLUS = True
FEDERAL_SHARE = 0.10
PARTNER_SHARE = 0.50
CONNECTIVITY = ["hsr:OKC", "hsr:LRD", "hsr:VALLEY", "hsr:MFE", "hsr:BIGC", "hsr:PANH", "hsr:WEST"]


def rail_fund(year, pop=None, base_year=2025):
    """$M the Rail Fund raises in `year` (0 before it starts), growing with Texas's population."""
    if year < RAIL_FUND["start"]:
        return 0.0
    g = pop[year] / pop[base_year] if pop else 1.0
    return RAIL_FUND["musd_per_year"] * g


def in_oklahoma(lat, lon):
    return lat > 33.75 and lon > -100.0


def in_louisiana(lat, lon):
    """East of the Sabine River (south of 32 N) or of the 94th meridian line (north of it)."""
    return lon > (-94.04 if lat >= 32.0 else -93.72)


def out_of_state_share(chain_points):
    """Share of a polyline's length (list of (lat, lon)) in Oklahoma or Louisiana, by sampling."""
    from texas.intercity import km
    total = out = 0.0
    for (a, b) in zip(chain_points, chain_points[1:]):
        d = km(a, b)
        n = max(1, int(d // 5))
        for k in range(n):
            t = (k + 0.5) / n
            la, lo = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            total += d / n
            if in_oklahoma(la, lo) or in_louisiana(la, lo):
                out += d / n
    return out / total if total else 0.0


def corridor_out_of_state(cid):
    """Share of a high-speed corridor's track outside Texas, along its drawn alignment."""
    from texas import hsr
    chain = hsr.CORRIDORS[cid][1]
    pts = [hsr.point(chain[0])]
    for a, b in zip(chain, chain[1:]):
        pts += [tuple(p) for p in hsr._alignments().get((a, b), [])] + [hsr.point(b)]
    return out_of_state_share(pts)
