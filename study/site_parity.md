# Bringing the statewide site to parity with DFW's

*The governor's request after the third session (`study/third_session.md`, item 12): what it takes for every metro, and
the state as a whole, to have what DFW Transit's site has. This is the review; nothing in it is built yet.*

## What DFW's site has

DFW Transit's map (`docs/map.html`, built by `dfwt/webmap.py` from `dfwt/templates/map.html`) and story page
(`docs/index.html`, `dfwt/story.py`):

| Feature | How DFW does it |
|---|---|
| **Named, coloured lines** | Hand-named and hand-coloured in `network/lines.csv` ("FW Green", "Orange Line"). Lines are grouped in the panel by mode and region (`webmap.REGIONS`), and shared track is drawn as side-by-side stripes (`webmap.shared_track`, `offsetPolyline`). |
| **Named stations** | `dfwt/naming.py`, in order of preference: a landmark within 250 m, a neighbourhood within 350 m, the cross streets at the nearest arterial, then a street. Landmarks and neighbourhoods come from OpenStreetMap (`data/dfw_gazetteer.json`, `dfw_hoods.json`), and hand fixes live in `network/station_renames.csv`. |
| **A year slider and scenarios** | Each scenario is a staged network (`network/stages.csv`: segments open by year). The page shows, hides or fades lines by year, with daily trips and a sparkline for each year. |
| **Line pages** | Tap a line for its stops, opening years by segment, headway, cost, value per $M, peak load and the lines that share its track. |
| **Station pages** | Its lines, boardings, people and jobs within 1 km, grade, and "trip from here / to here". |
| **Trip planner** | Door to door from any address (an external geocoder, limited to the metroplex box). It uses the model's own routing graph for each year (`dfwt/graph.YearGraph`), the access rules (walk, park & ride, feeder bus: `dfwt/tripplan.py`) and the drive time, so the page can't drift from the model. |
| **"What it means for you"** | For a home and a work address: the commute today against the plan, by year. |
| **Data layers** | Residents, jobs, and jobs within 45 minutes by transit, per area and year (`dfwt/layers.py`, loaded on demand). |
| **Diagram** | A schematic map (`dfwt/schematic.py`): octilinear, bundled corridors, Rail / BRT / All versions, laid out once over every scenario so it doesn't jump. |
| **Story page** | A scrollytelling case for the plan, its numbers read from the model (`dfwt/templates/story_facts.json`). |
| **Service detail** | Headways by year (`network/service.csv`), late-night service, and frequency upgrades on existing track. |

## What the statewide site has

`docs/index.html` (a brief: the year slider, the scenario chips, the state map, spending, the "what it takes" levers and
branch cards, one Leaflet map per metro, and the tables) and `docs/map.html` (every line statewide, with toggles by mode
and a year slider).

| | Statewide today |
|---|---|
| **Lines** | 85 generated and existing metro lines in 23 colours, named by the cross streets of their end centers ("Pellicano / George Dieter - Nonap / Mark Twain BRT"). **Three have no name** (El Paso G03, " BRT"). Today's lines carry their raw GTFS names ("800 METRORAIL GREEN LINE", "550-Metro Rail Red Line"). The high-speed and conventional lines are well named ("Texas Central: Dallas - Brazos Valley - Houston", "Heartland Flyer") but aren't in a colour system. |
| **Stations** | 1,147 generated stations; **936 (82%) named by the nearest cross streets** ("Mesa / San Antonio"), the rest by an anchor or center. High-speed stations are named by city. |
| **Year and scenario** | Yes, over the three schedules (best ratio first, metros first, the whole map), from `docs/data/timeline.json`. |
| **Line and station pages** | Tooltips only. |
| **Trip planner** | None. |
| **"What it means for you"** | None. |
| **Data layers** | None. |
| **Diagram** | None. |
| **Story** | The brief is a dashboard, not a story. |
| **Service detail** | One headway per line (`lines.csv`). No `service.csv` or stages: every metro line opens whole. |

## The key fact: the metros already speak DFW's format

Every generated metro (`urban/generated/<id>/`) is written in dfwt's own table schema: `lines.csv`, `stations.csv`,
`line_stops.csv`, `line_segments.csv` and `transfers.csv`. The generator loads them back as dfwt `Network` objects
(`metro/output.load_net`) and evaluates them with dfwt's model. So most of DFW's site can be **reused per metro** rather
than rebuilt. What stands in the way is a short list of DFW-only assumptions in the builder:

- `webmap.write` reads DFW's block groups (`demand.Zones(cfg)`) for the trip planner's feeder zones and garages, and
  `layers.write` reads them for the data layers. Both need the metro's zones (the generator's `ctx`).
- `webmap.REGIONS`, `stop_zone` (DFW's county lines) and `LABELS` (DFW's scenario names).
- `schematic.CITIES` (DFW's six reference cities) and `data/waterways.geojson` (DFW's rivers).
- In the template: the title and header text, `GEO_BOX` (the metroplex, for address search), and the "DFW area" messages.
- Scenarios are staged networks (`stages.csv`). The statewide schedules give each metro line an opening year, so each
  schedule becomes a scenario whose lines open in their schedule's year.

## What parity takes, in phases

Each phase is useful on its own, and the order puts first what the third session called the hearing problem.

### Phase 1: names (the hearing problem)

- **Station names by place**, for every metro.
  - Build each metro's gazetteer from Overture Maps, which is already the roads' source and reachable from here:
    landmarks are places in the hospital, university, college, stadium, airport, mall, museum, park, government and
    transit categories; neighbourhoods are divisions of subtype neighbourhood and microhood.
  - Run dfwt's `Namer` on each metro's stations with that gazetteer and the metro's roads.
  - Expected: most cross-street names become a landmark or neighbourhood, and the rest become proper arterial cross
    streets.
  - Hand fixes go in `urban/names/<id>/station_renames.csv`, in DFW's format.
- **Line names and colours**, for every metro.
  - **Rail lines** (metro, streetcar, commuter) get colour names in opening order within each metro, keeping today's
    agency names and colours where a line exists: METRORail Red, Green and Purple; CapMetro's Red Line; El Paso's
    streetcar. VIA's planned Green Line should match its corridor.
  - **BRT lines** are named by the corridor's main street: the road name covering most of the route, from the Overture
    segments' `names.primary`, weighted by length ("Westheimer BRT", "Mesa Street BRT"). Their colours come from one
    family per metro, as DFW's diagram review settled ("solid BRT").
  - Raw GTFS names get cleaned ("METRORail Green Line"), and every line gets a name.
  - Hand fixes go in `urban/names/<id>/line_names.csv`.
- **Intercity lines** get a colour system too: high-speed by corridor family (the Triangle, the branches) and
  conventional trains in one colour.
- *Where*: DFW Transit's generator (`metro/output.py` names, a new `metro/names.py` reusing `dfwt/naming.py`), and
  `tools/fetch_*` for the gazetteers. Regenerating isn't needed: names are applied to the tables after generation.
- *Size*: about two days of work.

### Phase 2: a DFW-style page for each metro

- **Generalize `dfwt/webmap.py`.**
  - Pass in the zones, the regions (or none), the scenario labels, the title, the address box and the reference cities.
  - DFW's build passes in today's values, so DFW's page doesn't change; that's the regression test.
- **Build `docs/metros/<id>.html`** for the five big metros first: Houston, San Antonio, Austin, El Paso and the Valley.
  - The scenarios are the three statewide schedules, as staged networks with each line opening in its schedule's year.
  - Each page gets the line and station pages, the in-metro trip planner, the data layers and the diagram.
- *Size*: DFW's page is 3.6 MB, so each page loads on its own, and the statewide index links to it from the metro's
  card.
- *Risk*: the schematic layout takes 15-40 s per version and was tuned on DFW. Houston's star network should suit it,
  but it may need its reference cities and some tuning.

### Phase 3: a statewide trip planner

- **City to city, door to door.**
  - The trip runs from an address in one metro, on that metro's lines to its high-speed station, then on the intercity
    service patterns (`texas/hsr.py` PATTERNS, with their headways and transfers), then on the other metro's lines to
    the destination.
  - It's the one feature DFW's site can't have, and the one that makes the statewide plan legible: "Houston Heights to
    UT Austin in 2060".
- **What it needs.**
  - The intercity graph by year, from the schedule's opening years.
  - Each metro's year graphs, exported as in Phase 2.
  - Station links (`study/session2_tests.py` `station_links`) where no metro station reaches a high-speed one.
- *Size*: the biggest phase. The in-page routing is DFW's, run on a larger graph, with the intercity legs added as runs
  of their own.

### Phase 4: the statewide map and story

- **Statewide map.** `docs/map.html` gets a line panel (high-speed, conventional, and each metro's lines grouped by
  metro), line and station pages (a high-speed station lists its metro connections), and a statewide diagram of the
  intercity network.
- **Story page.** `docs/index.html` becomes a story in DFW's style: the case, the three futures and what each metro
  gets. The current dashboard stays as `docs/plan.html`.
- **What it means for you**, statewide: your metro's lines near you, and your trips to the other cities, by year.

### Phase 5: hand the tables to the metros

- **Staging and service.**
  - Each metro gets `stages.csv` (lines opening in segments, as DFW's do) and `service.csv` (headways by year).
  - The generator writes first drafts of both: a long line opens in stages, and headways are its own.
- **Editing.**
  - The generated tables become editable inputs, as DFW's `network/` is, with dfwt's `validate` run on them: station
    spacing, curve radius and orphan termini.
  - A metro's planners could then edit their network the way DFW's hand plan was made, with the generator as the check
    it now is (`reports/generator_dfw_check.md`).

## What I'd do first

Phase 1, then Phase 2 for Houston. Names fix the problem the cabinet raised and feed every later page. A Houston page is
the proof that DFW's builder generalizes, because Houston is the metro most like DFW in size and network. Phase 3 is
where the statewide site would go beyond DFW's, and it rests on Phase 2's per-metro graphs.

## Open questions for the governor

1. **Whose names?**
   - Today's lines keep their agency names. For new lines, colour names (Houston's Red, Green and Purple extended) are
     the DFW convention.
   - Some metros may prefer corridor names, as VIA's are ("Green Line" on San Pedro). The default would be colours for
     rail and streets for BRT, with each metro able to override.
2. **How much per metro?** The five big metros warrant a full page. The 19 smaller ones have 0-2 lines each, so a card on
   the statewide page with named lines and stations may be enough.
3. **One page or many?** A single statewide page with every metro inside would be large: DFW's alone is 3.6 MB. Per-metro
   pages linked from the statewide map keep each one fast.

## What was built (November 2026)

All five phases, on the defaults above (colours for rail, streets for BRT, a page for each big metro, cards for the rest):

| Phase | What there is now | Where |
|---|---|---|
| 1. Names | Every metro's lines and stations renamed: agency names for today's lines, colour names for new rail (skipping today's colours), the outer town for regional rail, the main street for BRT; stations by landmark, neighbourhood or cross streets from each metro's own gazetteer (Overture). Every name and why in `urban/generated/<id>/names.csv`; hand fixes in `urban/names/<id>/` | DFW Transit `metro/names.py`, `metro/overture.fetch_gazetteer` |
| 2. Metro pages | DFW's map for Houston, San Antonio, Austin, El Paso and the Rio Grande Valley: the three schedules as scenarios, the year slider, line and station pages, the door-to-door trip planner, data layers and the diagram, on each metro's own model. Linked from each metro's panel on the plan page | `docs/metros/<id>.html`; DFW Transit `metro/pages.py`, `dfwt/webmap.write(site=...)`; `tools/build_metro_pages.py` |
| 3. Statewide trip planner | Any two high-speed stations, in the year and schedule shown, timed as the intercity model times a trip (the ride, the wait, changes), against the drive; at each end a hand-over to the metro's own map at the station nearest the high-speed one | `docs/map.html`, `docs/data/intercity.json`; `tools/build_trip_planner.py` |
| 4. Statewide map and story | The map's line panel (every line by group, its state in the year shown), station pages with "trip from / to here", high-speed lines coloured by family, metro lines in their own colours. A story page (`docs/index.html`); the dashboard is now `docs/plan.html` | `docs/map.html`, `docs/index.html`, `docs/plan.html` |
| 5. Editable tables | Each metro's `stages.csv` and `service.csv` as first drafts (every line one stage, opening in the main schedule's year; its headway), and `validation.md`: dfwt's validator on the result, as DFW's network is checked. Rows edited by hand survive a rerun | DFW Transit `metro/tables.py`; `tools/metro_tables.py` |

**Still short of DFW's:** the intercity planner covers high-speed rail only (the conventional trains run a few times a
day and aren't in it); the metro pages' years are a decade grid, not every year; the hand-over between the statewide
planner and a metro page is a link, not one continuous door-to-door trip; and the drafted stages are whole lines (the
validator flags the long ones, STAGE_TOO_BIG, for an editor to split as DFW's were).
