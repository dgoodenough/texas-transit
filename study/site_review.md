# The site, read by people who'd use it (November 2026)

The site had grown in four directions in a month: the story page, the plan dashboard, the statewide map and five metro
maps, each built in a different session. Nine readers went through all of it on a laptop and a phone: four who design
sites like this for a living and five Texans looking for their own city. The brief was usability only. **No line,
schedule or number in the plan changed**; what they found about the plan itself is at the end, for the governor.

## Who read it

| | Reader | What they came for |
|---|---|---|
| 1 | An information designer and cartographer | Does each map say what it shows, and do the maps agree with each other? |
| 2 | An accessibility specialist | Keyboard, screen reader, contrast, and plain language |
| 3 | A mobile UX researcher | A phone on a bus, one thumb, patchy signal |
| 4 | A plain-language editor for a state agency | Could a legislator's staffer read it in ten minutes? |
| 5 | A car-free commuter in Alief, Houston | When does a train reach my neighbourhood, and where does it go? |
| 6 | A renter in East Austin | Is the Austin plan real, and how do I get to San Antonio or Houston? |
| 7 | A nurse in Harlingen, in the Valley | When do we get anything? |
| 8 | A retiree in Lubbock | Can I take a train to see grandchildren in Austin? |
| 9 | A UTEP student in El Paso | El Paso's network, and the line into Juárez |

## What they found

**Getting around (1, 3, 4).** Each page had its own way out: the story linked to the map and the plan, the plan had two
paragraph links in its header, the map had four links that wrapped into two columns, and the metro pages only linked
back to the statewide map. Nobody could get from the plan to Houston's own map without finding a link in small type
at the bottom of the metro panel. *"I can see there are five metro maps, but only the story page tells me so."*

**Three pages, three starting years (1, 5, 9).** The plan opened in 2050, the statewide map in 2100 and the metro
pages in 2025, when most of them show only today's buses. The Alief commuter opened Houston's map and saw nothing new:
*"Is this the plan or what's there now?"*

**The plan page was a wall (2, 3, 4).** 6,600 pixels on a laptop and 11,000 on a phone, most of it two wide tables and
the caveats. The tables matter to analysts, but readers scrolled past them to find the metro map and then couldn't
find their way back up. No way to jump to a section.

**Legends that didn't match the map (1).** The plan's metro legend gave mode colours (blue metro, green BRT, purple
regional rail), but since the lines got names the map draws each in its own colour, so a red Houston line had no key.
The metro panel squeezed a 90-character policy description into the right-hand column of a two-column list, one word
per line.

**A stale paragraph (4).** "What it takes to build the whole map" said the branches "come last or not at all, and
all but the Valley fail a benefit-cost test". Under the optimized order adopted in the third session, every branch
fails one on its own (ratios 0.22 to 0.57), Oklahoma City opens in 2050, and every branch opens by 2100. The
sentence had been written by hand and had drifted from the data.

**A sum that didn't add up (1).** Under "By layer", the page said $578.8B had been spent out of $556.5B available,
leaving −$22.3B. The data was right; the note added up each line's full capital, including the track that Oklahoma,
Louisiana and the other neighbouring states pay for, and compared it with what Texas had. When every project is built
it also printed "doesn't fit before 2100" with nothing named.

**Too many digits (4, 6, 8).** "4,893,261 new daily trips" reads as more certain than any model is. *"Just say
about five million."*

**Jargon (4, 7, 8).** BRT, regional rail, present value, wider benefits, ratio and land tax are all used before
they're explained, or never explained. The Lubbock retiree didn't know what BRT was, and nobody outside the
profession knew what "present value at 3%" meant.

**Finding your own city (5, 7, 8).** The story page had cards for the five big metros and a list for the rest; there
was no way to ask "what about Waco?" and get an answer. The Harlingen nurse found the Valley card, which said "11,000
new daily trips in 2050; the first line opens 2093". That reads as a contradiction: the 11,000 is the line's value
once built, at 2050 levels, not trips in 2050.

**The statewide map at state zoom (1, 3).** At the first view, 24 metros' lines are a tangle of colour under the
intercity lines, and the panel opens with fourteen checkboxes before the map's own legend. On a phone the panel takes
half the screen. The trip planner was two empty dropdowns: no hint of what to try, and no way to reverse a trip.

**On the phone (3).** No page scrolled sideways. The story's trips table wrapped times onto two lines ("2 h / 55"),
and the schedules table wrapped "1.6 million" into a column too narrow for it.

**Accessibility (2).** Contrast, focus outlines and the year control's live label were fine. Section links were
missing, headings were in order, and the collapsed sections (below) use native `<details>`, which screen readers
announce. Legends that rely on colour alone now also say "each line in its own colour" in words.

## What changed

**Everywhere**
- One bar along the top of the story and the plan: Texas Transit, the story, the plan, the map, and each metro's own
  map (Houston, San Antonio, Austin, El Paso, the Valley, DFW). The map's links are tidied into one wrapping row.
- Every page opens in **2050**: the plan (as before), the statewide map, and the five metro pages
  (`tools/build_metro_pages.py` passes `start_year=2050`, a new option in dfw-transit's `metro/pages.py`).

**The plan (plan.html)**
- "On this page" links under the title to each section, including the governor's reviews.
- The intercity table, the by-layer table and the caveats are collapsed behind **Show**; a link or `#t1`-style address
  to one opens it. The page is now 4,200 px on a laptop and 7,900 on a phone.
- The metro panel puts **Open Houston's full map →** under the metro's name, as a button. The policy package reads
  "yes" in the list and is spelled out in the note below it. The legend says each line is drawn in its own colour, and
  shows open, being built and not yet open.
- "What it takes to build the whole map" is now written from the data: when each branch opens best ratio first, and the
  range of their ratios.
- The spending note uses what the schedule actually spent (net of land-tax bonds and of the neighbours' track):
  $511.4B of $556.5B, with every project built and $45.0B to spare.
- `plan.html?metro=waco` opens the plan on that metro.
- Big counts rounded: 1.58M new daily trips, not 1,579,597.

**The story (index.html)**
- **Find your metro**: a list of all 25. A metro with its own map goes there, DFW goes to DFW Transit's map, a
  smaller metro opens the plan on it, and a metro with no line says so.
- **The terms, in plain English**: high-speed rail, conventional trains, metro, BRT, regional rail, ratio, wider
  benefits, present value, land tax, schedule. Each says what the plan assumes (metro every 6 minutes, BRT every 8,
  regional rail every 20).
- Numbers rounded for reading (4.9 million, 597,000).
- The metro cards say "new daily trips once built (at 2050 levels)".
- The trips table's times don't wrap, and the schedules table shows 1.6M.

**The statewide map (map.html)**
- Opens in 2050.
- A four-line **legend** comes first; the fourteen layer checkboxes are folded under "Show or hide layers".
- Zoomed out to the state, metro lines are drawn at half weight and lines not yet open are hidden, so the intercity
  network reads first. Zoom in and they come back.
- The trip planner has a **⇄ swap** button and four example trips to tap (Dallas → Houston, Houston → Austin, San
  Antonio → Dallas, Houston → McAllen).

**The metro pages**
- Open in 2050.
- The diagram's "Waterways" legend row is hidden where the region has no rivers or lakes to draw.

## Not done, and why

- **Metros as dots at state zoom.** Drawing the metro networks thinner and hiding their later lines answers most of
  the tangle; a separate dot layer would add a fourth way of drawing a metro.
- **Full metro pages for the 19 smaller metros.** Most have one or two lines; the plan's metro panel shows them, and
  Find your metro sends readers there.
- **Inline definitions** (a tap on "BRT" anywhere) would mean touching every sentence; the glossary is one link away
  from the top bar.

## For the governor: what the readers found about the plan

The Harlingen nurse's question, "when do we get anything?", has an awkward answer, and the review is where it showed
up. Under the optimized build order adopted in the third session, **the Rio Grande Valley's first metro line opens in
2093**, against 2060 under the greedy order before it (study/third_session.md, item 3). The optimized order is worth
$202.4B against $194.9B, but this is what it costs one region of 1.3 million people. Nothing on the site was changed
to hide or soften it: the Valley card says 2093.

That's a decision, not a usability fix, so this review changed no line, no schedule and no opening year. The choices:
accept 2093; guarantee every metro a stream of its own (tested in the second session, it costs $10.4B of the plan's
value); or guarantee a first-line date to the Valley alone, or keep the greedy order for each metro's first line and
optimize the rest (neither tested yet; either is a run of study/timing.py with no change to any network).
