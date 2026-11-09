# Network memo: why the hand-drawn lines read better, a router that draws like a rider, and the 2100 HSR network

*Chief Network Planner. Scripts and outputs are in `network/` (scratch script, not in the repo). Nothing was written into either repo.*

## 1. Diagnosis

The cleanest test is DFW, because the generator has also been run there (`vendor/dfw-transit/generated/dfw`). That lets us compare hand-drawn and generated lines in the same city.

| Proposed lines | DFW hand-drawn | DFW generated | Houston | Austin | San Antonio |
|---|---|---|---|---|---|
| Metro lines that run through a downtown | **53%** | 15% | 25% | 40% | 67% |
| BRT lines that reach a downtown | 10% | 4% | **0 of 54** | 0 of 18 | 16% |
| Median BRT length | 18.7 km | 26 km | 30 km | 26 km | 30 km |
| Median share of a BRT line within 400 m of another line | **28%** | 47% | 72% | 76% | 84% |

**Houston**
- Of 12 rail lines, 5 end at Uptown (G09, G28, G47, G58, G68), 4 at Greenway or the Medical Center, 3 stub near downtown; none runs through.
- 13 BRT lines lie at least 95% on other lines (G04, G06, G10, G22, G54...). Nothing within 1 km of Hobby, Rice or NASA JSC. `preview.png` shows staircases.

**Austin**
- Nothing serves AUS airport or East Riverside.
- G07 (Wells Port – US-290 metro) is 41 km long. Its straightness is 0.67, it runs 95% on other lines, and it tries to reach seven destinations.

**San Antonio**
- `centers.py` labels the Medical Center as the downtown and the real downtown as a "major" center.
- Four rail lines (G22, G23, G30, G34) all end at St Mary's / Market instead of pairing into two through lines.
- Nothing reaches SAT airport, UTSA's main campus or Stone Oak.

**The hand-drawn plan instead** keeps each grid line on one arterial (straightness: Coit 0.99, Preston 0.98, Cooper 1.00), runs DNT West, Las Colinas–Mesquite and the Fort Worth metro lines through downtown, and ends lines at places people travel to.

**Root causes in the code**
1. **Termini can only be density peaks:** `candidates.paths` joins two centers on a Gabriel graph, so airports, campuses and hospitals count only if they are peaks.
2. **Line equals track:** every path is its own candidate, and the 5 km branch rule admits tangles.
3. **Nothing builds through-running:** downtown crossings happen by accident, and `rail_lines` starts radials at *every* major center (hence Uptown's five).
4. **Directness is checked end to end only** (1.5×) and turns only at centers, so staircases pass.
5. **The sketch scores lines alone,** with no transfers, so long sweeping lines win (BRT piles up near the 35 km cap).

## 2. Router spec: line planning, not path search

**A. Anchors.** Density centers, downtowns (by job density *and* being the transit hub), airports, universities of 10,000+ students, medical districts of 5,000+ health jobs (LODES CNS16), stadiums, and GTFS stations with 4+ routes. Sources: Overture places plus `metros.json` overrides. Each anchor has a weight and flags for "a line may end here" and "must be served".

**B. Corridor skeleton (track only).** Route between anchors with this cost:

time + α·(turns over 30°) + β·(changes of street name) + γ/density

Keep a corridor only if straight-line/route length is at least 0.8 in the core (0.7 in suburbs) and no 3 km window winds more than 1.3×.

**C. Line pool, built from templates**
- (a) **Diametral:** at each downtown, pair radials whose bearings differ by at least 135° and run one line through.
- (b) **Grid:** the longest single-arterial runs of at least 10 km at BRT density, cut at anchors where a line may end.
- (c) **Crosstown:** anchor to anchor between major non-downtown centers, staying more than 3 km from downtown (for example Uptown–Medical Center–UH).
- (d) **Rail:** on each rail line, through-running across downtown. No radial rail line starts at a non-downtown center.
- (e) **Branches:** a service pattern on an existing trunk, never a separate candidate.

Every line must also be 8–25 km for BRT or 10–40 km for metro, have directness of at least 0.75, end at anchors at both ends, and contain no hairpins.

**D. Choosing lines and frequencies.** This is the standard line-planning integer program from the literature (Borndörfer, Grötschel and Pfetsch; Schöbel).

Variables:
- *x₍l,f₎* ∈ {0,1}: line *l* runs at frequency *f*.
- *y_e* ∈ {0,1}: corridor edge *e* is built.

Objective:

max Σ_od w_od·LogsumGain_od(x) − μ·(Σ_e c_e·y_e + PV·Σ o₍l,f₎·x₍l,f₎)

Constraints: Σ_f x₍l,f₎ ≤ 1; x₍l,f₎ ≤ y_e for e on l; Σ c_e·y_e ≤ B; capacity Σ f·κ_l·x ≥ load_e; at most 2 BRT or 3 metro lines per edge; must-serve anchors within 600 m of a station (soft, heavy penalty); a radial reaching downtown runs through or ends at a named terminal.

Riders are assigned on a change-and-go graph. Generalized cost is in-vehicle time + 1.5×(walk + half the headway), plus 5 minutes and the second wait for each transfer.

Solve by greedy on the sketch (extended to this assignment), then local search (swap a line, snap a terminus to an anchor, merge two downtown stubs, split a meander, change a frequency), then the existing `modelselect` pruning, then a polish pass on the full model.

**Acceptance test on DFW:** at least 50% of metro lines through a downtown, median BRT overlap 30% or less, every must-serve anchor served.

## 3. HSR at full buildout

Today `hsr_options` credits each corridor with its incremental trips (Laredo–Dallas riders already count to Laredo), and `RailNetwork` runs **without `services`**: every pair gets a one-seat ride every 30 minutes, no transfer penalty.

Tested against all 14 corridors (2050 travel; 75.9M trips a year; $494B):

| Change | Trips a year | Capital | Operating cost a year |
|---|---|---|---|
| **Big Country Y:** branch Abilene–Lubbock instead of building Fort Worth–Lubbock | no change | **−$19.9B** | −$287M |
| **Y plus I-27 to Amarillo** (Abilene–Lubbock–Amarillo) | **+0.70M** | −$1.0B | −$23M |
| Keep Fort Worth–Lubbock, add a Lubbock–Amarillo spur | +0.70M | +$18.9B | +$264M |
| US-287: Fort Worth–Wichita Falls–Amarillo–Lubbock | +0.65M | +$26.6B | +$374M |
| Gulf spine: Corpus Christi–Kingsville–Harlingen–Brownsville plus McAllen, instead of San Antonio–McAllen | −0.40M | −$15.5B | −$227M |

**Recommended network:** the Triangle trunk (Texas Central, I-35, US-290, Fort Worth–Dallas); Laredo as an I-35 extension; Oklahoma City via Denton; Shreveport and the Gulf Coast line to New Orleans; a Gulf spine Houston–Corpus Christi–Valley; and the Big Country Y (an Abilene trunk branching to El Paso and to Lubbock–Amarillo). It carries 76.2M trips a year (**+0.3M**) for **$16.5B less** and $250M a year less operating cost, and it adds Amarillo.

**Thin legs as higher-speed rail.** I tested the thin legs at 175 km/h for $30M per km, which is an assumption. They keep 65–80% of their riders at about a third of the capital. The benefit per dollar roughly doubles: the West Texas leg goes from 2.7 to 5.0 ($M a year per $B) and Laredo from 2.0 to 4.5.

| Thin legs built as | Capital | Trips a year |
|---|---|---|
| HSR (today's plan) | $494B | 75.9M |
| Higher-speed rail, on HSR-ready trackbed | **$353B** | 74M (−2.6%) |

The trackbed can be laid out so these legs are upgraded to full HSR later.

**Service patterns:** Fort Worth–Dallas–Houston and Fort Worth–Dallas–Austin–San Antonio every 30 min; Oklahoma City–Dallas–Austin, Laredo–San Antonio–Houston and Valley–Houston hourly; El Paso–Dallas and Amarillo–Dallas every 2 h.

**Staging:** Triangle plus Fort Worth first (ratio about 0.7 alone, by my approximation of `timing.ratio`); then Shreveport (+7.9M trips a year for $31B); then Corpus Christi, Oklahoma City and Laredo; then the Gulf Coast and the Valley; the West legs last.

## 4. Network value: what's assumed and what's missing

**Assumed, not missing: one-seat rides.** If corridors ran as separate shuttles with a 15-minute penalty for changing trains, the network would lose **7.4M trips a year (−10%)** and **$476M a year** in travellers' gain. My through-running plan with 60–120 minute branches loses about as many riders but saves **$2.2B a year in operating cost**. That nets about +$1.1B a year, roughly $28B in present value. Service patterns should therefore be modelled explicitly.

**Missing:**
- **Travel is frozen at 2050**, yet the branches open in 2085–2100+. At 2100 travel, trips rise to **110M a year (+45%)** and travellers' gain rises from $4.4B to $6.4B a year. The network's ratio rises from 0.27 to 0.42 (0.44 for the recommended network).
- **Trips under 80 km and within a metro are excluded**, for example Dallas–Fort Worth, Denton and San Marcos.
- **Travel from across the Mexican border is not counted:** Juárez, Nuevo Laredo, Reynosa.
- **Trips to and from airports are not modelled.**

Together these lift the thin corridors from about 0.05 to roughly 0.1–0.15, still below 1: a strategic choice, so build them at minimum cost.

## 5. Implementation tasks

1. `metro/anchors.py` (Overture, LODES sectors, GTFS hubs; fix downtown choice).
2. `routing.py`: turn and street-name penalties, windowed winding check.
3. `candidates.py`: line-pool templates replace `paths()`.
4. `select.py`: transfer-aware sketch, greedy plus local search.
5. `modelselect.py`: polish pass; validate warnings (straightness, downtown stubs, overlap over 60%, termini off anchors, missed anchors).
6. Benchmark on DFW against the 2M plan; rerun Houston, Austin, San Antonio.
7. `texas/hsr.py`: add Amarillo, Kingsville and Weatherford stations; add the ABI_Y, CC_RGV and HRL_MFE corridors; give each corridor a speed and cost class.
8. `intercity.py` and `timing.py`: pass `services` with a transfer penalty, cost operations by train-km on each pattern, value each corridor at travel in its opening decade, and add trips within a metro and from Mexico.
