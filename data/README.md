# Data

Inputs for the statewide model: county zones, and today's travel between them to calibrate
against. Every file here is rebuilt by a script in `tools/`; raw downloads go to `data/raw/`
(git-ignored).

| File | What it is | Source | Script |
|---|---|---|---|
| `zones/counties.csv` | 254 Texas counties: 2020 population and its centre, land area, jobs (2022), metro or micro area | Census CenPop 2020 block groups, 2020 Gazetteer, LODES 8 WAC 2022, OMB delineation 2023 | `tools/build_zones.py` |
| `zones/nextgen_zones.csv` | The 583 NextGen OD zones (metro areas, non-metro rest of each state) with 2020 population and centre | NextGen OD zone shapefile + Census CenPop 2020 county centres | `tools/build_nextgen_zones.py` |
| `zones/county_zones.csv` | Each US county's NextGen zone, population and centre (how a zone's people are spread, for station access) | same | `tools/build_nextgen_zones.py` |
| `zones/county_growth.csv` | Each US county's population by year to 2100, from its 2010-2020 trend fading by half every 40 years (Texas 43M in 2050, 64M in 2100); a trend, not an official projection | Census CenPop 2010 and 2020 county files | `tools/build_growth.py` |
| `flows/lodes_county_commutes_2022.csv` | Home county × work county, all jobs, 2022 | LODES 8 OD (both ends in Texas) | `tools/build_zones.py` |
| `flows/air_city_pairs.csv` | Air origin-destination passengers a day by city-pair market, every market with a Texas end, average of four quarters | DOT / BTS Consumer Airfare Report, Table 6 (DB1B 10% ticket sample) | `tools/fetch_air.py` |
| `flows/road_screenlines.csv` | Two-way daily traffic at a rural point on each intercity corridor | TxDOT AADT (open data) | `tools/fetch_counts.py` |
| `flows/nhts_od_2022_texas.csv` | Annual long-distance person trips between NextGen zones (metro areas, rest of state) with a Texas end, by mode and purpose | FHWA / ORNL NextGen NHTS national OD data, 2022 | `tools/fetch_nhts_od.py` |

Hosts these need: `www2.census.gov`, `lehd.ces.census.gov`, `data.transportation.gov`,
`services.arcgis.com`, `nhts.ornl.gov` (the `transit-planning` cloud environment allows them).

## Today's intercity travel, at a glance

Between the big metros, person-trips a day in both directions, from NextGen NHTS (2022):

| Pair | Trips a day | By car | By air |
|---|---|---|---|
| Austin - San Antonio | 151,800 | 99% | 0% |
| Austin - Houston | 38,200 | 96% | 3% |
| Dallas - Houston | 33,100 | 81% | 18% |
| Houston - San Antonio | 30,000 | 93% | 7% |
| Austin - Dallas | 27,500 | 89% | 11% |
| Dallas - Oklahoma City | 17,200 | 91% | 8% |
| Dallas - San Antonio | 12,800 | 70% | 29% |
| Houston - New Orleans | 5,500 | 55% | 44% |
| Dallas - El Paso | 4,300 | 37% | 62% |

Air, from the airline ticket sample (passengers a day each way, Q2 2025 - Q1 2026):
- **Within Texas:** 53 markets, about 9,900 a day each way. The largest are Dallas/Fort Worth -
  Houston 1,737, Dallas/Fort Worth - San Antonio 949, Dallas/Fort Worth - El Paso 775,
  Houston - Midland/Odessa 700 and Austin - Dallas/Fort Worth 608.
- **Texas and other states:** 1,049 markets, about 214,000 a day each way. Neighbours that
  conventional rail could serve include Dallas/Fort Worth - New Orleans 1,198, Houston - New
  Orleans 1,047, Dallas/Fort Worth - Kansas City 1,041, Houston - Oklahoma City 519 and
  Dallas/Fort Worth - Memphis 506.

Road, two-way vehicles a day (TxDOT AADT, all vehicles, trucks and local trips included):

| Corridor | Road, place | AADT |
|---|---|---|
| Austin - San Antonio | I-35 between Kyle and San Marcos | 133,600 |
| Dallas - Austin | I-35 at West | 75,600 |
| Houston to Louisiana | I-10 at Orange | 57,400 |
| Dallas-Fort Worth to Oklahoma | I-35 at Gainesville | 51,100 |
| Dallas - Houston | I-45 at Centerville | 43,400 |
| Houston - San Antonio | I-10 at Weimar | 37,000 |
| Dallas-Fort Worth to Shreveport | I-20 at Marshall | 37,000 |
| Dallas-Fort Worth to West Texas | I-20 at Cisco | 29,200 |
| Dallas-Fort Worth to Arkansas | I-30 at Mount Pleasant | 28,900 |
| Houston - Victoria / Corpus Christi / Rio Grande Valley | US 59 at Wharton | 23,000 |
| Houston - Austin | US 290 at Carmine | 18,600 |
| San Antonio - El Paso | I-10 at Ozona | 11,000 |

## Caveats

- **LODES long-distance pairs are not daily commutes.** LODES places a job at the employer's
  reported address, so headquarters staff, state employees counted in Austin and remote workers
  show up as, for example, 123,000 Houston residents "working in" Dallas. Use the county flows
  for short links and as a measure of economic ties, not as intercity trips.
- **NextGen NHTS and the airline sample count air differently.** Dallas - Houston air is about
  6,000 trips a day in NHTS against about 3,500 (both ways) in the ticket sample. The ticket
  sample is the authority for air; NHTS gives the split between modes and the travel by car.
- **NHTS rail looks unreliable for intercity pairs.** It shows a few hundred rail trips a day
  between metros with no practical passenger train (for example, about 300 Dallas - Houston),
  probably from location data misread as rail. The model shouldn't calibrate to it.
- **AADT bounds intercity car travel; it doesn't measure it.** Each count includes trucks and
  trips that start or end along the corridor.
- **NHTS zones are metro areas and the rest of each state**, coarser than counties. The
  model's county zones are distributed within them by population and jobs.
