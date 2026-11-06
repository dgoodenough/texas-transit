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
6. **Timing and the site** (`study/timing.py`, `study/timing.md`, `docs/`): every project from
   steps 3-5 valued the same way, by what travellers gain (the logsum of the same logit models,
   plus fares minus operating cost, over capital plus the operating deficit, 50 years at 3%).
   They're scheduled best ratio first under the $6.7B a year left after DFW's $2.3B, and built
   whether or not a ratio reaches 1, since the plan spends DFW's rate. By 2100 that's $481B of
   $507B: 12 high-speed corridors, 89 of 93 metro lines and all seven conventional routes.
   About 750,000 new daily metro transit trips, 109M intercity rail trips a year and about 170
   fewer flights a day. Only Austin - San Antonio and Houston - Austin high-speed rail pay for
   themselves in travellers' gains alone, and by 2100 the lines run $1.6B a year more than fares
   bring in. Because an urban trip is worth about $8 in the model and an intercity trip $40-80,
   most metro lines open after 2050. A second scenario, **metros first**, gives each metro its
   own 30-year stream (its step-4 budget) and intercity rail the rest. That triples new urban
   trips by 2050 (490,000 a day against 163,000), finishes every metro by 2058, and opens the
   Triangle's high-speed lines 10-15 years later, for $21B less present-value gain net of
   operating cost at those trip values. The site (`docs/index.html`, data from
   `tools/build_site.py`) shows both scenarios by year, linking to DFW Transit for DFW.

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
