# The whole map by 2100: a cabinet plan for full high-speed buildout

*A working session, not a decision of record. The governor and cabinet are personas: five independent memos (`study/cabinet/`), each grounded in this repo's own model, convened and argued through. What comes out is a plan of work for the people who will build it: a UI/UX designer, a mathematician, a transport modeler, a cost engineer, a finance analyst, an urban planner and an auditor.*

## The question

Today's plan (`study/timing.md`, best ratio first, $9.0B a year statewide) builds nine of fourteen high-speed corridors by 2100. Five never start:

| Corridor | Capital (today's cost model) | Trips a year (2050) | Ratio |
|---|---|---|---|
| Dallas–Denton–Norman–Oklahoma City (OKC) | $32.2B | 2.5M | 0.15 |
| San Antonio–McAllen–Harlingen–Brownsville (RGV) | $46.3B | 2.4M | 0.10 |
| San Antonio–Laredo (LRD) | $24.3B | 0.8M | 0.06 |
| Fort Worth–Lubbock (LBB) | $44.1B | 1.3M | 0.05 |
| Fort Worth–Abilene–Midland–Odessa–El Paso (WEST) | $89.3B | 2.5M | 0.06 |
| **Together** | **$236B** | | |

Amarillo isn't in the network at all. The statewide pot outside DFW ($556.5B over 2025–2100) is already spent: $9.5B is left over. The governor wants Brownsville, Laredo, Lubbock and Amarillo, and El Paso on the map by 2100. The owner of this plan proposed three levers: statewide densification (single stair, upzoning, ADUs, missing middle), a better line router, and cheaper construction as expertise grows, and asked what else.

## The cabinet session

**Governor Marisol Vega** (presiding): "I'm not asking whether these lines pass a benefit-cost test today. I'm asking what it takes, and what it costs us honestly, to put El Paso and the Valley on the same network as Dallas. Tell me which levers are real."

**State Auditor** (invited because she's the skeptic) opened with the model, not the money. Three findings changed the conversation:

1. **Texas Central's 0.21 is an increment.** It is valued after I-35 north and US 290 already carry Dallas–Houston riders through Austin (`study/timing.py` `hsr_projects`); built alone it's 0.37. The build order decides who gets the credit.
2. **The model has thumbs on both sides of the scale.** Low: rail's constant against the car (−0.5) is a guess, never calibrated (`texas/intercity.json` hsr.asc_vs_car); station access is counted twice, a fixed 25 + 20 minutes on top of the county-to-station drive (`texas/intercity.py`); benefits are frozen at 2050 travel for 50 years with no growth after (`study/timing.py`), so lines opening in 2085 are valued on 2050 Texas. High: driving Dallas–Houston is modelled at 4.5 hours where I-45 does it in about 3.75; there's no transfer penalty; $90M/km is below Texas Central's own figure. Net, Texas Central alone is about 0.34, or 0.64 with a neutral rail constant: **the constant is the whole argument**, and it must be calibrated before anyone signs a contract.
3. **Even the honest best case doesn't make the branches investments.** Stacking every optimistic assumption, OKC reaches about 0.8–1.2 and RGV 0.6–0.95; Laredo, Lubbock and West Texas stay under 0.41. "These are connectivity lines. Call them that."

**Secretary of Infrastructure** brought the biggest single number. The plan prices every kilometre at $90M, viaduct through downtown Dallas or embankment across the Permian alike. Priced by context on the drawn alignments, with design fitted to demand and one continuous program:

- the five corridors cost **about $87B instead of $236B** (range $49–160B);
- the same method saves **about $83B on the nine corridors already built**, almost exactly what the five would cost;
- Amarillo via Lubbock adds about **$6B**.

The levers, in order: drawn alignment km instead of ×1.12 ($16B on the five), unit costs by context ($66B: rural flat beside a highway at $50M/km, big-metro approaches at $200M/km), design standard per corridor ($38B: 250 km/h single track with passing loops, graded for a second track, as Sweden's Bothnia Line), lean shared stations ($2B), and a learning curve earned by kilometres built, 10% per doubling to a floor of 0.75 ($28B). The catch: slower single-track lines carry about 21% fewer riders, so the ratios only double, to 0.10–0.24. "It makes them affordable, not winners."

**Chief Network Planner** redrew the network and agreed with the owner's instinct about the router. On the network:

- **The Big Country Y.** Branch to Lubbock at Abilene instead of building Fort Worth–Lubbock separately: the same riders for **$19.9B less**. Run it on up I-27 to **Amarillo** and the network gains 0.7M trips a year and still costs $1B less than today's plan.
- **The Gulf spine.** Reach the Valley from Corpus Christi instead of San Antonio: **$15.5B less** for 0.4M fewer trips.
- **Laredo as an I-35 extension** past San Antonio, with through trains to Houston.
- **Thin legs at higher speed first.** At 175 km/h on HSR-ready trackbed the network costs **$353B instead of $494B** for 2.6% fewer trips; upgrade a leg to full speed when it reaches 3M trips a year.
- Each corridor should be valued at travel in its opening decade: at 2100 travel the network carries 45% more trips and its ratio rises from 0.27 to 0.42.

On the router, the numbers bear the owner out. In DFW, where both exist, 53% of hand-drawn metro lines run through downtown against 15% of generated ones; generated BRT lines overlap other lines for a median 47% of their length against 28%. Houston's generator ends five rail lines at Uptown and none runs through downtown; no BRT line reaches downtown. Austin has nothing to the airport; San Antonio's generator calls the Medical Center the downtown. The causes are in the code: termini can only be density peaks, every path is its own line, nothing builds through-running, directness is only checked end to end, and the sketch scores each line alone with no transfers.

**Secretary of Housing and Land Use** delivered the uncomfortable result on YIMBY: **statewide zoning reform barely moves the branches** (ratios ×1.05–1.15). The extra people land where housing is constrained, Austin, Dallas and Houston, not El Paso or Lubbock, and the metro lines gain at least as much, so the branches don't move up the queue. "Do it anyway: it's the best thing we can do for the metros. But it isn't the HSR lever." What does help HSR specifically:

- **Pricing driving**, a VMT fee replacing a gas tax frozen at 20¢ since 1991 (+6¢ a km gives ×1.3–1.6; it's the strongest demand lever, and electrification will cut driving costs unless something replaces the gas tax);
- **air surcharges or a France-style ban** where rail is under 2.5 hours (×1.1–1.3);
- **the border**: counting Juárez, Nuevo Laredo, Reynosa and Matamoros at the model's own border factor (Laredo ×1.5, the Valley ×1.3), and a Laredo–Monterrey extension Mexico pays for (Laredo's ratio 0.06 → 0.16);
- **density at the far-end stations**: by-right mid-rise, single stair and no parking minimums in station districts in El Paso, Midland, Lubbock, Laredo and McAllen;
- and a model fix: trips grow with the square root of population at each end (elasticity 0.5), where the repo's own gravity fit says 1.15 and sketch models use 0.8.

**Secretary of Finance** costed the money. The central package, ring-fenced, nets about $255B by 2100:

| Lever | Central, $B by 2100 |
|---|---|
| The learning curve, statewide | 70 |
| 1/8 cent of sales tax into the existing, never-funded Rail Relocation and Improvement Fund (Texas Constitution Art. III §49-o) | 70 |
| Federal match | 45 |
| Oklahoma and Louisiana paying for track in their states (the model charges Texas $62.5B for it) | 31 |
| Completion bonds issued 2088–2100 against the next century's budget | 30 |
| The Triangle's operating surplus (+$1.06B a year) pledged to rail revenue bonds | 25 |
| Highway money, with the 2042 renewal of Prop 1 and Prop 7 as leverage | 15 |
| Value capture at HSR stations, concessions, climate funds | 14 |

Two warnings. **Borrowing early doesn't add money**: each dollar costs $1.39 real, and the Triangle is limited by construction time, not cash. And **the operating tail is half the problem**: the branches lose about $2.7B a year, roughly $45B before 2100, and no budget line pays it today.

## What the governor decided

**1. Fix the model first, and publish both answers.** No corridor decision rests on an uncalibrated constant. Calibrate rail's constant against real lines, fix the double-counted access, value each project at travel in its opening decade with growth after it, model service patterns with transfers, and make the growth elasticity a setting. These could move ratios down as well as up; the plan reports whatever comes out.

**2. Build it cheaper, deliberately.** Adopt the context cost model, drawn alignments, design standards per corridor and a learning curve earned by kilometres, in the model and as state policy: a permanent delivery office and standard designs, because learning is not automatic (rail overruns average 45% and haven't improved in 70 years). The **high** column is the default until the office exists.

**3. Redraw the network.** The Big Country Y with Amarillo, the Gulf spine to the Valley, Laredo on I-35 with Monterrey as Mexico's option, Oklahoma City via Denton. **Build the trunk, earn the branches**: thin legs open as higher-speed rail on HSR-ready trackbed and upgrade at 3M trips a year.

**4. A reserved Statewide Connectivity Program.** The branches are a policy choice for a connected state, not an investment, and the plan says so. They get their own budget line, funded by the Texas Rail Fund (1/8 cent, §49-o) and interstate cost shares, so they never displace a better metro line. The metros' share is protected: high-speed rail takes at most 40% of the non-DFW budget in any decade.

**5. Price the alternatives.** A VMT fee to replace the gas tax as cars electrify, an air surcharge on flights where rail is under 2.5 hours, and HSR station districts in the far-end cities. Statewide YIMBY goes ahead for the metros' sake.

**6. Guardrails** (the Auditor's, adopted whole): calibrate before committing; the next branch starts only after the previous one runs three years at 80% of forecast; approval needs a ratio of at least 0.8 at +45% cost and −30% riders, or an explicit connectivity designation; protect right-of-way on I-35 north, US 83/281 and I-20 west now (1–2% of capital); fund operations before opening; the Auditor re-estimates every decade with a stop-or-proceed decision.

**Can the whole map be built by 2100?** On the cabinet's central numbers, yes, just: the cost model frees about as much on the nine built corridors ($83B) as the five branches and Amarillo cost at their standards (about $93B), and the network redesign saves more. But that freed money would otherwise build metro lines with better ratios, cost overruns at the historical 45% would add about $40B, and the branches' operating losses add about $45B. The Rail Fund and interstate shares (about $100B central) are what make it real rather than a reshuffle. In the low case (no learning, half the new money) the map stops at Oklahoma City, the Valley and Laredo, with West Texas and the Panhandle as higher-speed rail.

**Order, if the gates are met:**

| Decade | Opens |
|---|---|
| 2030s | The Triangle: Austin–San Antonio, Houston–Austin, Dallas–Austin |
| 2040s | Fort Worth–Dallas; Dallas–Shreveport (or higher-speed first; the Auditor scores it 1.1–2.0 at 110–125 mph) |
| 2050s | Texas Central; Oklahoma City (higher-speed first, Oklahoma paying its share); right-of-way for every branch secured |
| 2060s | Houston–Corpus Christi, then the Gulf spine to Harlingen, Brownsville and McAllen |
| 2070s | Laredo on I-35 (Monterrey if Mexico builds its side); Gulf Coast to New Orleans with Louisiana |
| 2080s | The Big Country Y: Fort Worth–Abilene–Lubbock–Amarillo |
| 2090s | Abilene–Midland/Odessa–El Paso, the last leg, on completion bonds; Houston–San Antonio |

## The plan of work

Each role gets concrete tasks, files and an acceptance test. Phase 1 must finish before any later phase's numbers are trusted.

### Phase 1: a model you can argue with

**Mathematician** (calibration and estimation)
- Fit rail's constant against car (`texas/intercity.json` hsr.asc_vs_car) to observed comparables: Brightline Florida, Acela and the Northeast Regional, Madrid–Barcelona's car-plus-air market, with the model's own structure. Report the fitted value with an interval and which comparables pull it where. *Accept:* the model reproduces each comparable's rail share within ±25%, and the plan reports ratios at the fitted constant and at both ends of its interval.
- Fit the trip-growth elasticity (now 0.5 per end) to the repo's gravity data (`study/interstate_rail.md` finds 1.15) and literature; make it a setting, default the fitted value.
- A reference-class Monte Carlo on every corridor: cost overrun and ridership shortfall distributions from Flyvbjerg's data, giving P10/P50/P90 ratios. *Accept:* `study/timing.md` shows a range for every project.

**Transport modeler** (`texas/intercity.py`, `study/timing.py`)
- Remove the double-counted station access (a fixed 25 + 20 minutes on top of the drive to the station); correct the car's Dallas–Houston time (road factor 1.2 at 100 km/h gives 4.5 h; I-45 is about 3.75 h).
- Value each project at travel in its opening decade, with growth for 50 years after and a residual value, instead of 2050 travel held flat.
- Pass `services` to `RailNetwork` with a transfer penalty, and cost operations by train-km on each service pattern.
- Add trips under 80 km and within metros (Dallas–Fort Worth, Denton, San Marcos), cross-border catchment (twin cities × a border factor), airport access trips, and income growth.
- Pricing switches: `car.toll_per_vkm` by year, `air.surcharge`, `air.ban_rail_minutes`, applied to both the rail and no-rail cases.
- *Accept:* every change has a test, and `study/timing.md` lists what each changed, in the plan's own numbers.

### Phase 2: cheaper, redrawn, honest about speed

**Cost engineer** (`texas/hsr.py`, `texas/hsr_alignments.json`)
- Replace the flat $90M/km with context classes (urban approach, mid-city approach, town, rural rugged, rural flat) with low, central and high rates, the rugged share by corridor, and design standards S1–S4 (320 km/h double track to 200 km/h single track), as in `study/cabinet/infra.md`.
- Use the drawn alignment km; draw the new corridors (Abilene–Lubbock–Amarillo on US-84 and I-27; Corpus Christi–Kingsville–Harlingen–Brownsville on US-77; Laredo on I-35; Laredo–Monterrey).
- A learning curve on cumulative statewide km built, 10% per doubling with a floor of 0.75, switchable off (the default until a delivery office exists).
- Average speed and run time by standard, so slower legs carry fewer riders.
- *Accept:* the cost model reproduces today's numbers with every switch off; Texas Central falls between the central rate and the sponsor's $40B+ at the high rate.

**Network planner** (`texas/hsr.py` CORRIDORS)
- Add Amarillo, Kingsville and Weatherford stations and the Big Country Y, the Gulf spine and Laredo-on-I-35 corridors, with service patterns (Fort Worth–Dallas–Houston and Fort Worth–Dallas–Austin–San Antonio every 30 minutes; Oklahoma City–Dallas–Austin, Laredo–San Antonio–Houston and Valley–Houston hourly; El Paso–Dallas and Amarillo–Dallas every 2 hours).
- "Higher-speed first" as a corridor state: a leg opens at S4 on HSR-ready trackbed and upgrades to S2 or S1 when it reaches 3M trips a year (a later project with its own cost).

**Finance analyst** (new `texas/finance.py`, `study/timing.py`)
- Revenue streams as inputs by year: the Rail Fund (sales-tax share from 2030), federal match share, interstate shares (Oklahoma and Louisiana track), Triangle-surplus revenue bonds from 2036, completion bonds 2088–2100 at a capped debt service, station value capture.
- A **Connectivity Program** budget line in the scheduler: designated corridors draw only on it; it can't spend on metro lines, and no designated corridor can displace a higher-ratio project from the main budget.
- The operating deficit as a first claim on the Rail Fund before any opening.
- *Accept:* with every stream at zero the schedule matches today's; the plan reports capital and operating balances by decade per stream.

**Mathematician** (scheduling)
- Recast the schedule as an optimization: a multi-period knapsack with precedence (a branch after its trunk), budget lines and the metro ring-fence, gates (a branch can't start until its parent has run three years), and optional borrowing at a stated rate. Greedy best ratio first stays as the baseline; report the optimizer's gain over it.
- Solve the "full buildout" question directly: the minimum Connectivity Program budget (and which mix of streams) that opens every corridor by 2100 under each cost case, with P50 and P90 cost.

### Phase 3: the router (the urban lines, and why the owner was right)

**Mathematician** (line planning, DFW Transit `metro/`)
- Implement line planning as an integer program over a line pool (Borndörfer, Grötschel and Pfetsch; Schöbel): choose lines and frequencies to maximize riders' logsum gain on a transfer-aware assignment, subject to budget, capacity, at most 2 BRT or 3 metro lines per street segment, and must-serve anchors. Solve by greedy plus local search (swap a line, snap a terminus to an anchor, merge two downtown stubs into one through line, split a meander, change a frequency), then the existing full-model pruning (`metro/modelselect.py`).

**Urban planner** (DFW Transit `metro/`)
- `metro/anchors.py`: airports, universities over 10,000 students, medical districts over 5,000 health jobs, stadiums, transit centers with 4+ routes, and a corrected downtown (job density and transit hub, not the biggest density peak; San Antonio's Medical Center is not its downtown).
- `routing.py`: penalties for turns over 30° and changes of street, and a windowed winding check, so routes run along one arterial instead of staircasing.
- `candidates.py`: the line pool from templates: through-downtown lines (pairing radials across downtown), single-arterial grid lines, crosstown lines, rail through-running, and branches as service patterns on a shared trunk, never separate candidates.
- `validate`: warnings for straightness under 0.75, downtown stubs, more than 60% overlap with another line, termini off anchors and missed must-serve anchors.
- *Accept on DFW:* at least 50% of metro lines run through a downtown; median BRT overlap 30% or less; every must-serve anchor served; then rerun Houston, Austin and San Antonio and compare riders per dollar with today's generated networks.

### Phase 4: the site

**UI/UX designer** (`docs/index.html`, `docs/map.html`, `tools/build_site.py`, `tools/build_state_map.py`)
- **A third scenario, "The whole map"**: the Connectivity Program, the new cost model, the redesigned network, higher-speed first on thin legs, the gates. The scenario switch on both pages shows it beside "best ratio first" and "metros first".
- **"What it takes"**: a panel of levers (cost model low/central/high, learning on or off, Rail Fund, federal share, interstate shares, VMT fee, air surcharge, border catchment), each with what it adds, reading from a precomputed grid of scenario runs, so it stays a static site. Show the gap to "every corridor by 2100" closing as levers switch on, and what each costs or displaces.
- **Corridor cards** for the five branches and Amarillo: today's ratio, the calibrated range (P10–P90), the ratio needed, which levers close the gap, when it opens in each scenario, the gate it waits on.
- **The map**: corridors drawn by standard (full HSR solid; higher-speed first as a lighter line that upgrades in a later year), service patterns as a toggle, right-of-way protected but unbuilt as a hatched corridor, and the new stations (Amarillo, Kingsville, Weatherford).
- **Uncertainty shown, not hidden**: ranges on every headline number, and the operating balance by decade beside the capital.
- *Accept:* a reader who has never seen the plan can say, in one sentence, what it takes to get El Paso and the Valley on the network by 2100 and what it costs the metros. Test on phone width, both color schemes, keyboard only.

### Phase 5: the record

**Auditor**
- A decade-review script: re-estimate every corridor at current costs and riders, apply the gates, and report stop or proceed.
- Review every Phase 1–2 change before it reaches `study/timing.md`, so changes that raise HSR ratios aren't merged without the ones that lower them.
- *Accept:* `study/hsr_buildout.md` is regenerated from the model with every number traced to a run, replacing the cabinet's hand-assembled figures.

## What this plan doesn't promise

- That the branches pass a benefit-cost test. On every honest reading they don't; they're the price of one connected state, and the plan says so on every page that shows them.
- That costs fall. The learning curve is earned by a permanent delivery office and standard designs, or it doesn't happen.
- That the money arrives. The Rail Fund needs the Legislature; the federal match has already been withdrawn once (2025); Oklahoma and Louisiana have their own legislatures.
- That the model's riders are right. Rail forecasts miss by half on average; the gates exist for that reason.

## Sources

The five memos, each with its own sources: `study/cabinet/finance.md`, `study/cabinet/infra.md`, `study/cabinet/landuse.md`, `study/cabinet/network.md`, `study/cabinet/audit.md`. Their analysis scripts imported this repo's model in scratch copies and are not in the repo; Phase 1–2 rebuilds their numbers in the model itself.
