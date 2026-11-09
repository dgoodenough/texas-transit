# Memo: Cutting the cost of the high-speed corridors we can't yet afford

**From:** Secretary of Infrastructure  **To:** The Governor  **Re:** HSR cost levers

Governor, the plan prices every kilometre of high-speed rail at $90M, whether it is a viaduct through downtown Dallas or an embankment across the Permian. Priced by context, on the drawn alignments, with design fitted to demand and one continuous program, the five orphan corridors cost **about $87B instead of $236B** (range $49–160B). The same method frees **about $83B** on the nine corridors we already build. The catch: slower, single-track lines carry about 21% fewer riders, and even after the cuts none of the five passes a benefit-cost test.

## The corridors (2025 $B)

| Corridor | Today | Low | Central | High (no learning) | Standard | Trips/yr, full spec → ours | Run time, full → ours |
|---|---|---|---|---|---|---|---|
| Dallas–OKC | 32.2 | 9.8 | 16.7 | 28.5 | S2 | 2.49M → 2.13M | 1h26 → 1h46 |
| San Antonio–RGV | 46.3 | 8.8 | 15.8 | 28.7 | S3 | 2.35M → 1.85M | 2h02 → 2h37 |
| San Antonio–Laredo | 24.3 | 5.2 | 9.1 | 16.9 | S3 | 0.83M → 0.71M | 1h01 → 1h19 |
| Fort Worth–Lubbock | 44.1 | 8.3 | 15.1 | 28.4 | S3 | 1.27M → 0.93M | 1h52 → 2h25 |
| West Texas to El Paso | 89.3 | 16.8 | 30.7 | 57.6 | S3 | 2.52M → 1.83M | 3h55 → 5h03 |
| **Five corridors** | **236.2** | **48.8** | **87.4** | **160.1** | | **9.46M → 7.45M** | |
| Lubbock–Amarillo (191 km, new) | 18.8* | 3.4 | 6.1 | 11.3 | S3 | 0.74M → 0.59M | 47m → 1h01 |
| *or* FW–Wichita Falls–Amarillo (538 km) | 51.9* | 9.7 | 17.8 | 33.3 | S3 | not modelled | |
| Nine built corridors | 258.1 | 116.6 | 175.2 | 249.8 | S1 | unchanged | |

\*Today's method on the new segments. Low: low unit costs, 15% learning. High: high unit costs, no learning. Trips: the repo's 2050 intercity model (`texas/intercity.py`), new corridors added in plan order at their standard's average speed; at full speed it reproduces study/hsr_options.md exactly. Run times use model km; drawn track would cut ~8% more.

## Lever breakdown: five corridors, central case, applied in this order

| Lever | Saves |
|---|---|
| 1. Drawn alignment km instead of straight line × 1.12 | $16.4B |
| 2. Unit costs by context (rural flat vs. approaches) | $65.6B |
| 3. Design standard per corridor (single track, 250 km/h) | $37.5B |
| 4. Lean, shared stations | $1.5B |
| 5. Learning curve (factor ~0.75 by the time these start) | $27.7B |
| **Total** | **$148.8B** |

On the nine built corridors: drawn km $21.4B, context $43.0B, learning $18.5B, **$82.9B in all**, nearly the five's $87B.

## The evidence

**Unit costs.** Spain averages about €14M/km; Madrid–Seville near €6–7M/km ([Next City/ADIF](https://nextcity.org/urbanist-news/spain-high-speed-train-toronto-commuter-new-york-elevators); [Rail Journal](https://www.railjournal.com/in_depth/spain-pushes-ahead-with-high-speed-plans/)). France's LGV Sud Europe Atlantique was about €26M/km ([LGV SEA](https://www.wikiwand.com/en/articles/LGV_SEA)). China builds 350 km/h lines at $17–21M/km against Europe's $25–39M/km ([World Bank](https://www.worldbank.org/en/news/press-release/2014/07/10/cost-of-high-speed-rail-in-china-one-third-lower-than-in-other-countries)). Morocco's Al Boraq cost under €9M/km ([SNCF](https://www.groupe-sncf.com/en/group/sncf-around-the-world/high-speed-rail-in-morocco)). Brightline West, in the I-15 median, is $21.5B for 351 km: about $61M/km all-in, Cajon Pass and trains included ([Railway Age](https://www.railwayage.com/passenger/high-performance/report-brightline-west-costs-balloon-to-21-5b/)). Texas Central is above $40B for 380 km ([Reason](https://reason.com/2025/04/17/in-12-years-this-40-billion-high-speed-rail-line-in-texas-has-not-laid-a-single-foot-of-track/)). California's Merced–Bakersfield is about $36.75B for 171 miles, roughly $134M/km ([CHSRA board](https://cpo.soar.com/articles/6012577/California/Board-adopts-updated-program-baseline-and-fiscal-year-2025-26-budget-board-accepts-adjusted-3675B-capital-estimate-for-MercedFresnoBakersfield-plan)). NYU's Transit Costs Project traces the US premium to procurement, thin agency capacity, no standardization and overdesign, not geology ([Marron](https://marroninstitute.nyu.edu/blog/transit-costs-project-releases-new-york-case-and-final-project-report)). My central rural-flat $50M/km is ~1.5× France and below Brightline West, not a European price.

**Calibration check.** Before learning, my central case prices Texas Central at ~$26B against the sponsor's $40B+ (which includes trains, financing and a viaduct-heavy design). Central is what a disciplined public builder achieves; "high" is business as usual.

**Learning.** Mixed. China's low costs came from a long pipeline and standard designs ([World Bank 2019](https://www.worldbank.org/en/news/press-release/2019/07/08/chinas-experience-with-high-speed-rail-offers-lessons-for-other-countries)). Spain's per-km costs rose as lines reached harder terrain; its documented learning is mostly in maintenance (halved per km) ([Vía Libre](https://www.vialibre.org/vldigital/VL617Special25HS/files/basic-html/page16.html)). Flyvbjerg finds rail cost overruns average 44.7% with no improvement over 70 years ([Flyvbjerg et al.](https://econpapers.repec.org/RePEc:taf:transr:v:23:y:2003:i:1:p:71-88)). So I propose **10% per doubling of cumulative statewide km, with a floor of 0.75**. That matches DFW's 25% at the end, but earned by kilometres built, not calendar years, and only with a permanent state delivery agency and standard designs. Otherwise use the high column.

**Design standard.** Sweden's Bothnia Line is single track, built for 250 km/h, with 22 passing loops in 190 km and its formation ready for a second track ([Bothnia Line](https://en.wikipedia.org/wiki/Bothnia_Line)). California weighed opening Merced–Bakersfield as single track to save about $1B up front ([Trains](https://www.trains.com/?p=98507); [GV Wire](https://gvwire.com/2021/03/26/high-speed-rail-explores-single-track-plan-for-2029-service-start-in-valley)). World Bank data put Chinese 250 km/h lines at RMB 87M/km vs 129M for 350 km/h, but terrain confounds that, so on flat Texas ground I credit only 10%. Loops every ~25 km still allow 30-minute service, but single-track delays spread both ways.

**Freight upgrades.** Amtrak's Lincoln Service reached 110 mph for about $1.95B over 284 miles, roughly $4.3M/km ([NPR Illinois](https://www.nprillinois.org/illinois/2023-05-04/feds-approve-amtrak-running-110-mph-along-chicago-to-st-louis-routes)). Brightline Florida's 170-mile, 125 mph extension cost about $5B, or about $18M/km ([Construction Dive](https://www.constructiondive.com/news/brightlines-5b-orlando-florida-extension-complete)). Interim stage only: UP's Laredo line and the T&P main line west of Fort Worth are heavy freight routes; sharing needs the railroad's consent and leaves run times near driving.

## Ridership

At the lower speeds the five carry **2.0M fewer trips a year (−21%)**, and travellers' gain falls 23%. Cost falls 63%, so ratios roughly double, from 0.05–0.15 to about 0.10–0.24 (ignoring operating deficits): still far below 1. The cuts make these corridors **affordable**, not **winners**: a best-ratio scheduler would spend the freed $83B on urban lines first. A full buildout needs your policy order (a reserved HSR program). At S4 (160 km/h average) the five lose a third of their riders, and Fort Worth–El Paso at 6h17 loses to flying, so S4 is not an endpoint.

## Recommended cost model (for the modelers)

- **Track km:** use the drawn alignment (`km_map`). For segments not yet drawn, use straight-line km × 1.06.
- **$M per double-track km by context, low / central / high:**
  - urban approach: 150 / 200 / 300, for the first 12 km from a big-metro terminal (DFW, Houston, Austin, San Antonio, OKC, El Paso, New Orleans)
  - mid-city approach: 90 / 120 / 160, for 6 km (Laredo, McAllen, Lubbock, Amarillo, Corpus Christi, Shreveport, Baton Rouge)
  - town or suburban: 70 / 90 / 110, next 10 km beyond a big-metro approach; 3 km each side of a minor station
  - rural rugged (escarpments, river bottoms, Arbuckles, Trans-Pecos): 50 / 75 / 95
  - rural flat beside highway or rail right-of-way: 32 / 50 / 62
  - rugged share of rural km by corridor: TC .40, I35N .30, I35S .50, I10 .25, US290 .30, CC .25, GULF .55, SHV .35, OKC .30, RGV .10, LRD .15, LBB .25, WEST .25, AMA .15
- **Design factor on rural km, with average speed (approaches stay double track):**
  - S1, 320 km/h double: 1.00, 260 km/h average
  - S2, 250 km/h double: 0.90, 210 km/h average
  - S3, 250 km/h single track with loops, graded for a second track: 0.66 (0.60–0.75), 200 km/h average
  - S4, 200 km/h single track, diesel first: 0.52, 160 km/h average
  - Assign S1 to the nine built corridors, S2 to OKC, S3 to RGV, LRD, LBB, WEST and AMA. Add the second track at 3M trips a year.
- **Stations:** $600M/$150M; $400M/$80M on thin corridors sharing existing terminals.
- **Learning:** factor = max(0.75, 0.9^log2(cumulative km / 500)). On today's schedule: 1.00 to 2040, 0.90 by 2078, 0.75 after 2100.
- **Amarillo:** go via Lubbock (+$6B, 0.6M trips). Wichita Falls costs three times as much.

Scripts: `infra/` (scratch script, not in the repo) (cost_model.py, waterfall.py, riders.py).
