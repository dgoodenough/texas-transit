# Memo: Demand levers for the unbuilt HSR corridors

**From:** Secretary of Housing and Land Use · **To:** Governor, HSR cabinet · **Re:** What land use and pricing can do for LRD, RGV, LBB, WEST, OKC

## Bottom line

On its own, zoning reform won't get the five orphan corridors built. A statewide YIMBY package raises their ratios by about **1.05–1.15x**. It lifts the Triangle and the metro lines at least as much, so the orphans stay at the back of the queue. The levers that are specific to HSR and carry real weight are **pricing the competing modes** (x1.4–1.8), **cross-border demand** (x1.2–1.5 on LRD/RGV, and up to x2.7 on LRD if Mexico builds Laredo–Monterrey), and one **model fix**: trips grow with population far too weakly in our model (x1.2–1.3). Stacked, a central package gets OKC and RGV to about 0.25 and LRD to 0.14 (0.55 with Monterrey). That is enough to compete with the marginal urban BRTs (0.15–0.2). WEST and LBB stay under 0.15 and still need cost or money levers.

## Method

I re-ran `hsr_projects` and `ratio` from `study/timing.py` in scratch copies (`landuse/` (scratch script, not in the repo)). The baseline matches exactly: OKC 0.150, RGV 0.101, LRD 0.057, LBB 0.051, WEST 0.055. Each lever then changes inputs (zone growth, base trips, station access, car cost, air utility), and the corridor is valued incrementally in the plan's order at 2050 travel.

**Ratios respond to riders non-linearly.** Capital and opex are fixed, since a 30-minute headway runs whatever the load, while benefits and fares scale with riders. Riders needed to reach the ~0.18 cut-off: OKC x1.2, RGV x1.7, LRD x2.8, WEST x2.9, LBB x3.3. To reach 1.0: x4 to x13.

## Lever by lever (multiplier on each corridor's ratio)

| Lever | Low | Central | High | Notes |
|---|---|---|---|---|
| Statewide YIMBY: TX metros +5/10/20% pop by 2050 | 1.03–1.05 | 1.05–1.10 | 1.11–1.21 | OKC lowest (Oklahoma end not grown) |
| …same, but only the big four metros grow | | 1.04–1.05 | | Most likely incidence (see below) |
| HSR station TOD: 2/5/10% of zone pop at the station, 10–15 min better access | 1.01–1.02 | 1.04–1.06 | 1.08–1.12 | "20% of growth to station areas" ≈ x1.04–1.06 |
| Air surcharge $15/30/60 a one-way trip | 1.04–1.07 | 1.07–1.14 | 1.14–1.28 | WEST gains most (it competes with air) |
| France-style ban (no flight where HSR < 2.5 h / 3.5 h) | 1.03–1.22 | 1.17–1.31 | | Air travellers' loss netted out |
| Car cost +$0.03/0.06/0.10 per veh-km (tolls, VMT fee) | 1.15–1.26 | 1.31–1.59 | 1.56–2.16 | Strongest lever; LBB/WEST x2 at high |
| Mexican twin cities as catchment (border factor 0.15/0.3/0.6) | LRD 1.26, RGV 1.14 | LRD 1.52, RGV 1.28, WEST 1.17 | LRD 2.07, RGV 1.58 | Juárez 1.5M, Reynosa 0.7M, Matamoros 0.54M, N. Laredo 0.43M |
| Laredo–Monterrey extension (244 km, $22.6B) | | LRD 1.29 if Texas pays | LRD 2.73 (0.155) if Mexico pays | Monterrey 5.3M people |
| Amarillo added to LBB (202 km) | | LBB 1.07 | | Cost rises almost as fast as riders |
| *Model fix:* trips ∝ pop^0.8 per end (now 0.5) | | 1.16–1.28 | 1.39–1.67 at 1.15 | Triangle gains more (x1.45) |

**Packages** (compounding; elasticity left at 0.5 unless noted):
- **Low** (YIMBY +5%, TOD 2%, car +$0.03, air +$15, border factor 0.15): OKC 0.19, RGV 0.16, LRD 0.09, WEST 0.09, LBB 0.07.
- **Central** (+10%, 5%, +$0.06, +$30, 0.3): OKC 0.25, RGV 0.25, LRD 0.14 (0.55 with Monterrey paid by Mexico), WEST 0.14, LBB 0.10.
- **High** (+20%, 10%, +$0.10, +$60, 0.6): OKC 0.38, RGV 0.61, LRD 0.38 (1.17 with Monterrey), WEST 0.37, LBB 0.15.
- With the elasticity fix on top, the central package gives OKC 0.45, RGV 0.50, WEST 0.24.

Within the central package, land use alone is x1.13–1.16; pricing alone x1.4–1.8.

## What YIMBY does to the HSR-versus-metro contest

1. **Where would the extra people go?** Hsieh & Moretti (2019) find that the national cost of housing constraints sits in high-productivity, supply-constrained cities. In Texas that means Austin and the inner parts of Dallas and Houston, not El Paso, Lubbock, Laredo or the Valley. Those cities already build freely and cheaply, and their growth depends on jobs, not permits. So SB 15 (no lot-size minimum above 3,000 sq ft in cities over 150k) and SB 840 (homes by right on commercial land, up to 36 units/acre) mostly add people at the Triangle end.
2. **Why the far end matters most:** our model scales a pair's trips by √(g_a·g_b). Growth at the DFW or San Antonio end alone moves the orphans only about half as much (x1.04–1.05 for +10%).
3. **The metros gain at least proportionally.** Their models carry both growth and station-area land use, and YIMBY growth that lands near transit adds density as well as headcount. (Ewing & Cervero 2010: small but positive density elasticities.) So the marginal Houston and San Antonio BRTs gain about 1.1–1.2x, against about 1.05–1.10x for the orphans. **YIMBY is roughly neutral to slightly negative for the orphans' place in the queue.** It strongly helps the Triangle, which is built anyway.
4. **The fix is to aim land policy at HSR station districts in the far-end cities.** Downtown El Paso, Midland, Lubbock, Laredo and McAllen stations should get by-right density, no parking minimums, single-stair mid-rises and TIRZ/PID capture, as the metros already have.

TOD adds a few percent of riders; its larger value is capture: Brightline saw station premiums of about 9–13% (UF Warrington) and 2,000+ units approved beside MiamiCentral, and Ahlfeldt & Feddersen find GDP effects at small stations on Germany's Cologne–Frankfurt line. At $90k–$110k of value per person or job, 30k–50k people and jobs per district at a 10% uplift could bond about $0.3–0.5B per major station. Small next to $24–89B corridors.

## Border, tourism, military

- **Border:** the 2024 northbound crossings were 12.7M passenger vehicles and 6.5M pedestrians at El Paso alone, and 9.8M vehicles at Laredo. Today's NHTS base cannot see Mexican residents' trips. Adding the twin cities at the repo's own Monterrey border factor (0.3) is the single best land-use-adjacent lever for LRD and RGV.
- **Tourism:** Big Bend has no station; South Padre needs shuttles from Harlingen/Brownsville. At most +5–10% on RGV and WEST.
- **Fort Bliss** (about 47,600 employees) is already in the base data.
- **Permian:** Midland and Odessa already carry the highest trend growth (x1.55–1.66 by 2050). That extrapolates an oil boom: a downside risk. HSR carries no freight.

## Honesty caveats

- **Pricing levers change the do-nothing world.** Road pricing is defensible as policy in its own right: Texas's gas tax has been frozen at 20¢ since 1991, NTTA charges about 21–22¢ a mile, and electrification will make driving cheaper unless a VMT fee replaces the gas tax. Our model's $0.12/km marginal car cost will otherwise drift down, which is a real downside for HSR. A ban conditional on HSR costs air travellers welfare (netted out above).
- **The pivot logit cannot shift car travellers to air** when car costs rise, and **it has no income growth.** Long-distance trips rise with real income, which is a separate upside the model leaves out.
- **The elasticity is uncertain.** The repo's own cross-sectional gravity fit (`study/interstate_rail.md`) gives 1.15 per end. HSR sketch models use about 0.8. The growth model uses 0.5.

## Model changes I'm asking the team to make

1. **`growth_elasticity`** in `intercity.json`: replace √(g_a·g_b) in `ic.run` with (g_a·g_b)^e, default 0.8, tested at 0.5 and 1.15.
2. **A YIMBY growth scenario:** have `tools/build_growth.py` write an alternative `county_growth_yimby.csv` that re-weights growth toward metro counties, with a constrained-city premium for Austin, Dallas and Harris. Feed it to both the urban and intercity layers so the queue comparison stays fair.
3. **HSR station districts:** reuse `districts()`/`land_tax()` for HSR stations, and add a station-area part to each zone's `_ends` (its share is the station-area capture of growth, with walk access).
4. **Pricing knobs:** `car.toll_per_vkm` by corridor or year, an `air.surcharge`, and an `air.ban_rail_minutes` flag applied in `nested_split` and `logsum_gain` against a same-policy baseline.
5. **Border catchment:** twin-city populations × border factor on the Laredo, McAllen, Brownsville and El Paso zones, plus a Monterrey option on LRD with Mexico's cost share as an input.
6. **Income growth:** a trip-rate multiplier per year.

**Sources:** [Hsieh & Moretti 2019](https://www.aeaweb.org/doi/10.1257/mac.20170388); [Auckland upzoning, JUE 2023](https://eprints.soton.ac.uk/476826/); [Pew on Minneapolis](https://www.pew.org/en/research-and-analysis/articles/2024/01/04/minneapolis-land-use-reforms-offer-a-blueprint-for-housing-affordability) and [Minneapolis Fed caveat](https://www.minneapolisfed.org/article/2026/minneapolis-2040-plan-indicators-point-to-stable-rents-stalled-development); [Mercatus on Houston lot reform](https://www.mercatus.org/research/policy-briefs/liberalizing-land-use-regulations-case-houston); [SB 15 text](https://capitol.texas.gov/tlodocs/89R/billtext/html/SB00015F.htm); [SB 840 summary](https://www.squirepattonboggs.com/insights/publications/key-takeaways-for-real-estate-developers-from-the-89th-texas-legislative-session-2025-sb-840-commercial-to-residential-by-right); [France ban](https://aviationweek.com/air-transport/airports-networks/french-domestic-flight-ban-takes-effect-push-toward-rail-use); [HSR gravity sketch, pop^0.8](https://pedestrianobservations.com/2025/08/31/high-speed-rail-ridership-estimator-applet/); [Ahlfeldt & Feddersen](https://eprints.lse.ac.uk/29430); [Brightline premiums](https://warrington.ufl.edu/due-diligence/2023/07/17/now-boarding/); [Ewing & Cervero 2010](https://ideas.repec.org/a/taf/rjpaxx/v76y2010i3p265-294.html); [TxDOT El Paso border sheet](https://www.txdot.gov/content/dam/docs/division/tpp/international-trade/border-sheets-el-paso.pdf), [Laredo](https://www.txdot.gov/content/dam/docs/tpp/international-trade/border-sheets-laredo.pdf); [Mexican municipalities, 2020](https://en.wikipedia.org/wiki/List_of_municipalities_in_Mexico_by_population); [NTTA rates](https://ntta.org/sites/default/files/2023-06/06.2023_TollTag%20Rates%20Increases%20One%20Penny%20Per%20Mile%20on%20July%201%20Article_ntta.org_.pdf); [Texas EV fee / gas tax](https://roadsbridges.com/law/news/33005242/new-electric-vehicle-tax-signed-into-law-in-texas); [Fort Bliss, HUD](https://www.huduser.gov/portal/publications/pdf/ElPasoTX-CHMA-25.pdf).
