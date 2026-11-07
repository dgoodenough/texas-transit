# Texas Transit

A hypothetical statewide transit plan for Texas: high-speed rail across the Texas Triangle,
urban systems in every metro, conventional rail to neighbouring states, and air travel
modelled alongside. Speculative, not an official plan.

It is the statewide sibling of [DFW Transit](https://github.com/dgoodenough/dfw-transit),
which stays its own site. This repo reuses that project's model code: the demand model
(`dfwt/`) and the from-scratch network generator for any US metro (`metro/`).

## Budget

The same spending rate as DFW Transit, per resident: $2.3B a year for 7.47M people, or about
$308 per resident per year (2025 dollars). For Texas's 29.15M residents (2020) that is about
**$9.0B a year, roughly $670B over 2025-2100**. Every project, urban or intercity, competes on
riders per dollar under that flat budget, as DFW Transit's 2 million plan does; how much goes to
high-speed rail versus metro systems is an output, not an input.

## Texas at a glance (2020 Census, 2023 OMB metro definitions)

- 26 metropolitan areas. The big four hold 67% of the state: Dallas-Fort Worth 7.64M,
  Houston 7.15M, San Antonio 2.56M, Austin 2.28M. Next: McAllen 0.87M, El Paso 0.87M,
  Killeen-Temple 0.48M, Corpus Christi 0.45M, Brownsville 0.42M, Beaumont 0.40M.
- 2.9M people live outside metro areas.
- Straight-line distances between the big four are high-speed rail distances: Dallas-Houston
  370 km, Dallas-Austin 290, Austin-San Antonio 120, Houston-San Antonio 300, Houston-Austin 230.
  El Paso is 800-1,100 km from all of them and stays an air market.

`python study/size_texas.py` reproduces these numbers from Census files.

## The model: three layers

1. **Urban.** DFW keeps its hand-built plan. The other 25 metros use DFW Transit's network
   generator (`python -m metro generate <id>`), driven from this repo (`urban/`). Each metro's
   ridership constant comes from its own transit use: Houston's is fitted to NTD rail and BRT
   riders, and the rest are set from their ACS transit commute share (table B08301). Construction
   costs are still DFW's.
2. **Intercity (new, the core).** Counties (254) as zones. Long-distance trips by purpose
   (business, personal), with a mode choice among car, air, high-speed rail, conventional rail
   and intercity bus on door-to-door time, cost and frequency. Calibrated to today's travel:
   - long-distance person trips: FHWA NextGen NHTS origin-destination data;
   - air: BTS airline ticket sample (DB1B) and segment data (T-100), e.g. Dallas-Houston;
   - road: TxDOT traffic counts on I-45, I-35, I-10.
   Flights come out of the same choice: the model reports the air trips high-speed rail
   replaces and what that does to flights between Texas airports.
3. **Interstate (new, high level).** Conventional rail corridors with simple service patterns to
   Oklahoma City (and on to Kansas City), Shreveport and Little Rock/Memphis, New Orleans,
   Albuquerque, and Monterrey via Laredo.

## Plan of work

1. **Inputs and today's travel.** County zones with population and jobs; reproduce today's
   intercity flows (air, road) closely enough to trust comparisons. The inputs are gathered
   (`data/README.md`): county zones, LODES county commutes, airline city-pair passengers, TxDOT
   corridor counts and NextGen NHTS long-distance trips.
2. **Intercity demand model** (`texas/intercity.py`, parameters in `texas/intercity.json`): today's
   trips between NextGen zones as the base, a pivot-point nested logit (air and rail in one nest)
   for new rail; each county uses its own nearest station. First results in
   `study/hsr_first_look.md`: with today's travel, Texas Central carries about 4.9M trips a year
   (Dallas - Houston 1.6M of them) and a Texas Triangle about 22M.
3. **High-speed rail options** (`texas/hsr.py`, `study/hsr_options.md`): 14 corridors ranked by new
   riders per dollar in 2050, with trend growth (`tools/build_growth.py`) and induced trips. The
   first three form the Triangle's west and south sides: Austin - San Antonio ($14B, about 15M
   trips a year), Houston - Austin ($24B) and Dallas - Austin ($31B): 41M trips a year for $68B.
   Next: operating costs and revenue, then timing under the budget alongside the urban layer.
4. **Urban systems** (`study/urban_metros.py`, `study/urban_metros.md`): a generated rail and BRT
   network for each of the other 25 metros at DFW's rate per resident. $105B of the $172B budget
   buys 93 lines, mostly BRT: about 444,000 daily transit trips against 59,000 today. Houston
   alone is $61B and 219,000 trips. Ten metros get no line, because nothing there is dense enough
   for rail or BRT. One check is a warning: at its constant the model puts 16,000 riders a day on
   Austin's Red Line, and NTD counts 1,600, so infrequent rail is overrated.
5. **Interstate rail** (`texas/conventional.py`, `study/interstate_rail.md`): conventional trains,
   two or four a day at up to 79 mph on upgraded freight track, on seven corridors. Calibrated to
   the Heartland Flyer's 80,000 riders a year (Amtrak FY2024). At four trains a day, I-20 (Dallas -
   Shreveport - Jackson, 0.86M new trips a year for $2.6B) and the Sunset route (Houston - New
   Orleans, 0.58M for $2.1B) lead. Monterrey (a gravity estimate past the border) gets 0.13M.
   Kansas City, Memphis and Albuquerque add little, because the data only has trips with a Texas
   end. All seven together are $14B of capital and run about $330M a year more than fares bring
   in. On the same routes, high-speed rail carries seven to eleven times the riders, at 40-60% of
   the riders per dollar of capital.
6. **Timing and the site** (`study/timing.py`, `study/timing.md`, `docs/`): one statewide plan
   under one budget. Dallas-Fort Worth runs DFW Transit's 2 million riders plan on its own
   timetable (`tools/build_dfw.py`); what it doesn't spend goes to the rest of the state. Every
   other project is valued the same way: travellers' gain from the same logit models, plus wider
   benefits (`texas/benefits.json`: congestion, crashes and emissions for each car-km off the road
   and air passenger-km out of the sky, and agglomeration), plus fares minus operating cost, over
   capital plus the operating deficit, across 50 years at 3%. Land tax near new urban stations (a
   Tax Increment Reinvestment Zone plus a Public Improvement District, borrowed against when a line
   opens) pays about an eighth of the urban lines' capital. Projects go best ratio first and the
   budget is spent whether or not a ratio reaches 1. By 2100: 13 high-speed corridors, 91 of 93
   metro lines, all seven conventional routes and DFW's plan; about 2.5M new daily metro transit
   trips (1.7M in DFW), 111M intercity rail trips a year and about 180 fewer flights a day. Six
   projects pay for themselves (two on travellers' gain alone). The high-speed stations meet DFW's
   network on foot: Dallas beside Union Station, Fort Worth at Fort Worth Central, Denton at its
   transit center. A second scenario, **metros first**, gives each metro its own 30-year stream:
   500,000 new daily trips outside DFW by 2050 instead of 166,000, the Triangle's high-speed lines
   10-15 years later, $18B less in present value. The site (`docs/index.html`, data from
   `tools/build_site.py`) shows both scenarios by year, with a zoomable map of every metro's
   network (`tools/build_metro_maps.py`: full alignments, stations and the main roads).
7. **Toward DFW's transit share in the other metros** (`study/metro_potential.py`,
   `study/metro_potential.md`): a first look at how much of DFW's share each metro's layout
   allows, and what the generator, DFW's spending and DFW's policies get there. Build-out mode
   (DFW Transit's generator, `--buildout`) lets Austin and San Antonio grow networks their layout
   can carry: with DFW's policies, 5.2% and 4.2% of commutes on today's land use, against DFW's
   3.2% under the same treatment. The plan uses it for those two metros, at DFW's 75-year rate.

## Reusing DFW Transit's code

For now `dfw-transit` is a git submodule at `vendor/dfw-transit`
(`git submodule update --init`); scripts put it on the Python path. The urban layer runs DFW
Transit's `metro` package with `METRO_HOME=urban`, so the registry (`urban/metros.json`), inputs
(`urban/data/metros/<id>/`) and networks (`urban/generated/<id>/`) live here:

```
python tools/build_metro_registry.py
python tools/fetch_transit_use.py
(cd vendor/dfw-transit && for id in houston austin ...; do METRO_HOME=../../urban python -m metro fetch $id; done)
python study/urban_metros.py calibrate && python study/urban_metros.py generate && python study/urban_metros.py summary
``` Packaging it
(`pip install git+https://github.com/dgoodenough/dfw-transit`) would replace the submodule.
