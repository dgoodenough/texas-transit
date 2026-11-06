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

1. **Urban (exists).** DFW keeps its hand-built plan. The other 25 metros use DFW Transit's
   network generator (`python -m metro generate <id>`), once it has:
   - each metro calibrated to its own Census transit commute share (ACS table B08301), not DFW's;
   - regional construction costs.
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
   intercity flows (air, road) closely enough to trust comparisons.
2. **High-speed rail options.** The Triangle (Dallas-Houston, Dallas/Fort Worth-Austin-San
   Antonio, Houston-San Antonio or Houston-Austin) and possible branches (Rio Grande Valley,
   Laredo, Waco/Killeen). Costs, ridership, air trips replaced.
3. **Urban systems** for the other metros, with per-metro calibration.
4. **Interstate rail.**
5. **The site:** a statewide map with the time slider, high-speed rail and flights, linking to
   DFW Transit for the DFW detail.

## Reusing DFW Transit's code

For now `dfw-transit` is a git submodule at `vendor/dfw-transit`
(`git submodule update --init`); scripts put it on the Python path. Packaging it
(`pip install git+https://github.com/dgoodenough/dfw-transit`) would replace the submodule.
