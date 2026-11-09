# MEMORANDUM

**To:** The Governor
**From:** Secretary of Finance
**Re:** Paying for the full high-speed network by 2100
**Date:** 9 November 2026

## The bill, stated honestly

| Item | $B (2025 $) |
|---|---|
| Five unbuilt corridors (OKC 32.2, RGV 46.3, LRD 24.3, LBB 44.1, WEST 89.3) | 236 |
| Amarillo (Lubbock–Amarillo, 202 km; my run of `texas/hsr.py`) | 19 |
| **Capital gap** | **255** |
| Crowd-out if the new money joins the best-ratio queue: unbuilt urban lines (ratios 0.07–0.18) get in ahead of LRD, LBB and WEST | up to 40 |
| **Operating tail** (fares minus opex, `timeline.json`): OKC −0.26, RGV −0.41, LRD −0.27, LBB −0.56, WEST −0.99, Amarillo about −0.23 | **−2.7/yr** |

Two points first. **The money must be ring-fenced.** These lines return 5–15 cents of benefit per dollar. Building them is a policy choice for connectivity, the border and statewide fairness, not an investment. **The operating tail is half the problem.** On my staging below it runs to about $45B before 2100.

The good news is the Triangle. I-35S, US-290 and I-35N together earn +$1.06B a year above operating cost. In the current plan the high-speed network nets **+$42B of cash from 2025 to 2100**, and no one has claimed it.

## Levers ($B by 2100, 2025 $, no double counting)

| # | Lever | Low | Central | High | Effect on order | Feasibility in Texas | Source |
|---|---|---|---|---|---|---|---|
| 1 | **Cost discipline:** DFW Transit's own learning curve applied statewide (0.95, 0.85 or 0.75 of today's cost) | 23 | 70 | 117 | Every line opens earlier | Medium. DFW's plan already assumes it, but US real costs keep rising. Needs standard designs and a permanent delivery office. | `hsr.py`; DFW plan |
| 2 | **Dedicated revenue:** 1/8 cent of sales tax (about $0.98B/yr) from 2030 into the **existing, never-funded Rail Relocation & Improvement Fund** (Art. III §49-o). Low 1/16 cent; high 1/4 cent. | 32 | 70 | 130 | Ring-fenced, so OKC and RGV can start in the 2050s. Also carries the operating tail. | Medium-low. A statute can do it by simple majority, and §49-o already allows bonds. It competes with property-tax relief in a Legislature hostile to high-speed rail (2025 bills). | Comptroller FY25; §49-o; LRL |
| 3 | **Federal match** (FSP/CRISI and successors). Low ≈ $0.2B/yr; central 10% of all high-speed capital; high an IIJA-scale programme at 20%. | 15 | 45 | 100 | Lumpy. Favours multistate corridors (OKC, GULF). | Low now. In 2025 the FRA cut Texas's $63.9M grant and California's $4B. House BUILD America 250: $3.5–3.9B/yr nationally, subject to appropriation, and FY26 FSP was $65M. Brightline West got $3B of $12.4B. | Tribune; USDOT; Railway Age; APTA |
| 4 | **Interstate partners.** The model charges Texas for other states' track: Louisiana's share of GULF $38.7B and of SHV $3.3B, Oklahoma's share of OKC $20.5B. Partners pay 25/50/80% of it. | 16 | 31 | 50 | Frees money in the 2050s–80s. OKC's Texas share falls to about $12B. | Medium. Compacts and the Louisiana and Oklahoma legislatures; federal rules favour multistate. | my `levers.py` |
| 5 | **Completion bonds:** issued 2088–2100 against the 2100–2130 stream, debt service capped at 15/30/40% | 15 | 30 | 45 | WEST and LBB finish by 2100 | Medium. Needs voter-approved debt (§49-o allows obligations). | my `borrow.py` |
| 6 | **Triangle surplus recycled:** revenue bonds of about $18B at 1.25× coverage from 2036, net of the later lines' deficits | 10 | 25 | 45 | SHV, FW and TC come forward 5–10 years, freeing later decades | High legally. Must beat the urban operating deficits (−$4.8B/yr) for priority. | `timeline.json` |
| 7 | **Flex highway money:** STBG/CMAQ and the Texas Mobility Fund (§49-k allows "public transportation projects"). High = a rail share in the **2042 renewal of Prop 1 and Prop 7**. | 5 | 15 | 50 | Small and steady | Low. Prop 1, Prop 7 and the fuel tax (Art. VIII §7-a) are limited to non-tolled roads (AG KP-0197). Changing that needs an amendment: two-thirds of each chamber plus the voters. UTP: $146B over 10 years. | TxDOT; LBB; AG |
| 8 | **Station value capture:** TIRZ+PID at about 20 high-speed stations, plus joint development | 3 | 7 | 15 | At opening | Medium. Cities form TIRZs one at a time and school tax is excluded. Spain's edge-of-town stations captured little. Brightline's roughly $1B of real estate is a business model, not capital at this scale. | `benefits.json`; Brightline; JR East |
| 9 | **P3 / concessions**, beyond #6 | 0 | 5 | 15 | No change | Low-medium. **Transp. Code §199.003 bars state money for privately operated high-speed rail.** Availability payments are borrowing at 7%+. | §199.003 |
| 10 | **Carbon and climate funds** | 0 | 2 | 10 | No change | Low. No Texas carbon price, and federal grants rescinded. | |
| | **Total** | **119** | **300** | **577** | | | |

**On borrowing early to go faster: I advise against it.** At a 30% debt-service cap from 2030, issuing $133–153B nets between −$16B and +$3B by 2100. Each $1 costs $1.39 real ($1.84 at 4.5% nominal). The Triangle is already limited by construction time, so debt on low-ratio lines buys mostly interest.

## Net position

In the central case, $300B less about $45B of operating tail leaves **about $255B, which just closes the gap**, provided the money is ring-fenced. The low case ($119B) builds OKC, RGV and perhaps LRD, and leaves West Texas unbuilt. The high case funds everything including Amarillo. Levers #1, #2 and #4 have to start this decade.

## Realistic order of construction

1. **OKC, about 2058.** Best ratio of the five (0.15). Oklahoma pays about $20B, and federal money is likeliest here.
2. **RGV, about 2068.** Most trips (2.4M a year) and 1.4M Valley residents.
3. **LRD, about 2078.** Pair it with Mexico's Monterrey rail plans. Cross-border traffic is its only upside on 0.8M trips.
4. **LBB with Amarillo, about 2085**, built as one Panhandle spine.
5. **WEST in stages:** Fort Worth–Midland/Odessa about 2092, El Paso by 2100 on completion bonds.

## Recommendation package

1. **2027 session:** fund §49-o with 1/8 cent as a ring-fenced Texas Rail Fund, with operating support as its first claim.
2. **Now, by executive action:** adopt the learning curve statewide and set up a permanent delivery office. It is the largest lever, and we control it.
3. **Interstate:** sign cost-share compacts with Louisiana and Oklahoma, and apply jointly for federal money.
4. **From 2036:** pledge the Triangle's fares to rail revenue bonds.
5. **2041 session:** make a rail share the price of renewing Prop 1 and Prop 7. Seek authority for completion bonds and a §199.003 carve-out for publicly owned, privately operated service.

*Scripts: `cabinet/finance/levers.py` and `borrow.py`. They import the repo's numbers and write nothing to the repo.*

**Sources:** [TxDOT UTP 2026](https://www.txdot.gov/about/newsroom/stories/2025/gov-abbott-announces-over-146-billion-texas-transportation-investment.html) · [Comptroller FY25](https://comptroller.texas.gov/about/media-center/news/20250903-acting-texas-comptroller-kelly-hancock-announces-state-revenue-for-fiscal-2025-august-state-sales-tax-collections-1756843079560) · [Art. III §49-o](https://law.counselstack.com/constitution/tx/III/49-o) · [LRL: fund "never funded"](https://www.lrl.texas.gov/scanned/srcBillAnalyses/81-0/SB1923INT.PDF) · [LBB funding overview](https://www.lbb.texas.gov/Documents/Publications/Presentation/3287_Overview_Transportation_Funding.pdf) · [AG KP-0197](https://www.oag.state.tx.us/sites/default/files/opinion-files/opinion/2018/kp0197.pdf) · [Prop 7 to 2042](https://www.txdot.gov/about/financial-management/funding-needs-sources/proposition-7-funding.html) · [TMF §49-k](https://www.txdot.gov/inside-txdot/division/debt/investors/tmf-reports.html) · [§199.003](https://codes.findlaw.com/tx/transportation-code/transp-sect-199-003/) · [Tribune grant cut](https://www.texastribune.org/2025/04/14/texas-high-speed-rail-planning-grant-cut) · [USDOT CAHSR](https://www.transportation.gov/briefing-room/trumps-transportation-secretary-sean-p-duffy-pulls-plug-4b-california-high-speed) · [Brightline West](https://www.bondbuyer.com/news/brightline-west-eyes-3-5-billion-tax-exempt-bond-financing) · [Railway Age BA250](https://www.railwayage.com/news/analysis-build-america-250-act-amtrak-rail-transit-implications/) · [APTA BA250](https://www.apta.com/wp-content/uploads/2026/06/HR-8870-BUILD-America-250-Draft-Funding-Table-Passenger-Rail-05222026.pdf) · [NARP FY26](https://www.railpassengers.org/happening-now/news/blog/analysis-of-fy-2026-thud-rail-funding-and-provisions/) · [2025 TX bills](https://www.trains.com/?p=225280) · [Brightline real estate](https://warrington.ufl.edu/due-diligence/2023/07/17/now-boarding) · [JR East](https://www.railjournal.com/in_depth/jr-easts-10-year-strategy-set-to-transform-business-model)
