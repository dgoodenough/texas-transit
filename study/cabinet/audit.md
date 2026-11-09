# From the State Auditor: full HSR buildout by 2100

Governor, in short: the model undervalues Texas Central somewhat, but nothing in it is wrong enough to rescue the five branches. My runs are in `audit/audit.py` (scratch script, not in the repo), which imports the repo's own model; I changed nothing in the repo.

## 1. Is the model biased against HSR?

Partly. The errors point both ways.

**Biased low**

| Issue | Where | Effect (Texas Central built alone, 2050) |
|---|---|---|
| Rail's constant against car (−0.5) is **not calibrated** to anything; conventional rail's is fitted (−1.74, to the Heartland Flyer) | intercity.json `hsr.asc_vs_car`; `intercity.py:277` | The biggest unknown. A constant of 0 gives 12.5M trips and a ratio of 0.72; +0.3 gives 16.2M and **1.05**. Base: 7.9M and 0.37 |
| Station access counted twice: a fixed 25 + 20 minutes plus the county-to-station drive. Air gets a flat 75 minutes | `intercity.py:259,273` vs `:142` | Rail's out-of-vehicle time on Dallas–Houston is 124 minutes against air's 161. Cutting the fixed part to 15/15 gives 9.6M trips and 0.48 |
| **The 0.21 is an increment**, valued after I-35N and US 290 already carry Dallas–Houston riders through Austin, with no transfer penalty | `timing.py:243-261`; `intercity.py:166-171` | Built alone it is **0.37**. The build order decides who gets the credit |
| Benefits held at 2050 travel for 50 years, with no growth after and no residual value. Texas goes from 43M to 64M by 2100 | `timing.py:23-24, 54, 379-390` | Late lines undervalued by about 30–50% |
| The gain of induced trips is left out | `intercity.py:372-376` | About +5% |

**Biased high**

| Issue | Where | Effect |
|---|---|---|
| The car's road is 1.2× the straight line at 100 km/h: 4.5 h of driving, where I-45 downtown to downtown is about 3.75 h | intercity.json `car`; `intercity.py:131-134` | 1.08× gives 6.6M trips and 0.29 |
| Short metro-to-rural pairs (80–150 km) get a few percent share despite an hour of access; the repo's own caveat says so | `hsr_options.md` | About 30% of Texas Central's trips |
| No transfer penalty | `intercity.py:166-171` | Flatters networks |
| Cost of $90M/km sits below Texas Central's own figure: over $40B for 240 miles, about $104M/km ([USDOT 2025](https://www.masstransitmag.com/rail/press-release/55283486/federal-railroad-administration-fra-fra-terminates-cid-grant-awarded-to-amtrak-for-texas-high-speed-rail-corridor)) | `hsr.py:7-10,20` | Before any overrun |

Netting both sides gives Texas Central alone **0.34**; with a constant of 0, **0.64**. The constant is the whole argument.

**How the forecasts compare with real lines**

- **The model:** rail takes 16% of the Dallas–Houston market (2.8M a year in 2050 on that pair, 7.9M on the whole line).
- **Texas Central's backers:** LEK forecast 10M by 2050, which it called 30% of demand ([Progressive Railroading](https://progressiverailroading.com/high_speed_rail/news/Dallas-Houston-high-speed-trains-could-serve-5-million-riders-by-2026--49976)). I found no source for the 13M figure in the brief.
- **TxDOT (2013):** 0.7–2.7M by 2035 ([NBC DFW](https://www.nbcdfw.com/news/local/how-many-people-would-ride-high-speed-rail/115942/)). The model sits between the two.
- **Brightline West:** forecasts a 14% share of a 49M-trip market ([Review-Journal](https://www.reviewjournal.com/opinion/letters/letter-brightline-ridership-projection-seems-a-tad-high-3052356)), about the model's share.
- **Madrid–Barcelona:** 14.6M rail trips in 2024 and 82% of the rail-plus-air market ([FTN](https://ftnnews.com/travel-news/rail/spains-high-speed-rail-breaks-passenger-records-in-2024/)). The model gives rail 69% of the public-transport market, so it handles air competition reasonably. What it lacks is Spain's car-light baseline.
- **Tokaido (161M, [Statista](https://statista.com/statistics/1264961/japan-jr-high-speed-train-passengers-by-line)) and Acela plus Northeast Regional (14.1M, [Smart Cities Dive](https://www.smartcitiesdive.com/news/amtrak-ridership-record-northeast-corridor-long-distance-trains/734543/)):** ceilings, not comparables.
- **Brightline Florida, the cautionary case:** it forecast 7M long-distance riders for 2024, carried 2.8M trips on the whole system ([iHeart](https://wiod.iheart.com/alternate/amp/2025-05-05-brightline-doubles-ridership-in-2024-despite-losing-549-million-in-2024-despite)), and its parent companies filed for Chapter 11 in September 2026 ([Mass Transit](https://www.masstransitmag.com/management/article/55408388/brightline-brightline-florida-parent-companies-seek-to-restructure-25-billion-in-debt-through-chapter-11-bankruptcy)).

## 2. The levers

| Lever | Verdict |
|---|---|
| Densification / YIMBY | **Real for the metros, wishful for the branches.** Even 2100's population lifts thin-corridor ratios only 1.4–1.6× |
| Better router | **Marginal.** Track is already 1.12× the straight line (`hsr.py:19`): at most about 10% saved. Station siting is the real gain (+20–30% riders) |
| Learning curve | **Upside, not baseline.** US costs are rising (Texas Central: $30B to over $40B). Even at $40M/km, Laredo, Lubbock and West Texas stay below 0.5 |
| Federal match | **Real cash that changes who pays, not the ratio.** Politically volatile: FRA terminated the Texas Central grant in 2025 ([Texas Tribune](https://www.texastribune.org/2025/04/14/texas-high-speed-rail-planning-grant-cut/)). Chase it for the trunk |
| Borrowing | **Timing, not value.** Bonds at 4.5% against a 3% discount rate make ratios worse. Use it only to bring I-35S forward |
| Value capture | **A transfer**, and a rounding error next to $236B |
| Lower design standards | **The one real lever, but the result isn't HSR** (§4) |
| Network effects | **Already counted:** through trips are in each increment |

## 3. Honest best case for each corridor

I ran each corridor on top of the nine lines already built. The optimistic case stacks a constant of 0, 20% induced trips, the access fix, trains every 2 hours, $60M/km and 2100 travel.

| Corridor | Model | Optimistic | + $40M/km, half-cost stations | Cost per trip as modelled (capital + operating deficit) |
|---|---|---|---|---|
| OKC $32.2B | 0.15 | 0.78 | 1.18 | ~$600 |
| RGV $46.3B | 0.10 | 0.63 | 0.95 | ~$940 |
| LRD $24.3B | 0.06 | 0.25 | 0.37 | ~$1,470 |
| LBB $44.1B | 0.05 | 0.17 | 0.25 | ~$1,790 |
| WEST $89.3B | 0.06 | 0.27 | 0.41 | ~$1,770 |

Only OKC, perhaps RGV, reach 1, and only if everything goes right.

**Within $9B a year? No.** The plan already spends essentially everything by 2100 ($9.5B unspent).

- The five corridors cost $236B, which is 26 years of the entire statewide budget.
- Fitting them by 2100 means dropping the plan's lowest-ratio projects: Texas Central, Gulf Coast, Corpus Christi and I-10 HSR ($154B, ratios 0.15–0.22, every one better than any branch), plus 44 urban lines ($79B, $56B of it in Houston) carrying about 220,000 daily trips.
- That trades **$1.58B a year of travellers' gain for $0.58B**. The alternative is +$3.1B a year, +47% on the non-DFW budget.
- On top of either, the five run an operating deficit of $0.6–2.5B a year that no budget line covers.

## 4. Conventional or higher-speed instead

At 110–125 mph (trains every 2 hours, $10–20M/km, standalone), the ratio is 2–5× HSR's on every thin corridor:

| Corridor | HSR | Higher-speed |
|---|---|---|
| OKC | 0.10 | 0.32–0.54 |
| RGV | 0.05 | 0.12–0.19 |
| CC | 0.12 | 0.37–0.61 |
| Dallas–Shreveport | 0.31 | 1.1–2.0 |

Shreveport deserves a second look before $31B of HSR, though generous rural pairs drive much of it. TxDOT's own Texas-Oklahoma Passenger Rail Study chose up to 125 mph for San Antonio–RGV and 220 mph only for DFW–San Antonio ([TxDOT 2017](https://www.TxDOT.gov/about/newsroom/statewide/2017/025-2017.html)).

My recommendations:
- **Higher-speed:** OKC, RGV and Corpus Christi.
- **Conventional or coach:** Laredo (to Monterrey if Mexico partners), Lubbock and Abilene–Midland/Odessa.
- **El Paso stays an air market.**

## 5. Risks

- **Cost:** rail overruns average 45% in real terms ([Flyvbjerg, World Bank WP3781](https://ppp.worldbank.org/public-private-partnership/sites/default/files/2022-05/wps3781.pdf)). At +45% cost and a constant of −1, I-35S still clears **1.2**, but US 290 falls to 0.51 and I-35N to 0.35.
- **Ridership:** rail traffic averages 51% below forecast (same paper).
- **Short trips:** I-35S rests on Austin–San Antonio (118 km), the range the model may flatter.
- **Politics:** about 37 legislative sessions to 2100; federal money already withdrawn once. Half-built branches are the worst outcome.

## 6. Guardrails

1. **Calibrate first:** fit rail's constant to Brightline Florida and Acela now, then to I-35S's actual riders. No later contract on an uncalibrated constant.
2. **Ridership gates:** the next corridor starts only after the previous one runs 3 years at 80% or more of forecast.
3. **Reference-class approval:** ratio at least 0.8 at +45% cost and −30% ridership.
4. **Build the trunk, earn the branches:** branches open as higher-speed service and become HSR only above 3M trips a year.
5. **Protect the corridor:** preserve right-of-way on I-35 north, US 83/281 and I-20 west for about 1–2% of capital.
6. **Ring-fence the metros:** HSR never displaces a higher-ratio urban line, and takes at most about 40% of the non-DFW budget in any decade.
7. **Fund operations first:** no opening without a dedicated source for the deficit.
8. **Decade reviews:** the Auditor re-estimates each decade, a stop-or-proceed decision each time.

Be ambitious on the Triangle, honest about the branches: the 2100 map is an option to earn, not a promise to borrow against.
