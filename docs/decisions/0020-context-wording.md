# 0020: How context measures and records are worded

- **Status:** accepted
- **Date:** 2026-11-19

## Context

0019 adds measures that describe a landfill's surroundings: readings from nearby air monitors, the
number of people living close by, and the state's CalEnviroScreen scores. It also widens the
regulatory records to several air districts.

These are the measures most easily misread. An air monitor two kilometres from a landfill also
measures traffic, farming, wildfire smoke and everything else upwind. Placing its reading on a
landfill's page invites the reader to blame the landfill, which this project cannot support. The
project's standing rule is that its outputs are screening indications, never compliance findings
and never health claims.

## Options considered

1. **Leave air and community measures out.** Safe, but the owner asked for them, and they help a
   reader see where a site sits.
2. **Show them like any other figure.** Rejected: it would read as cause and effect.
3. **Show them as labelled context, under fixed wording rules** (chosen).

## Decision

- **Kind `context`, shown in its own section.** Context never shares a chart, a table or a ranking
  with emissions figures.
- **Every context section carries one fixed sentence:** the figures describe the area around the
  site and are not attributed to the landfill. The existing population label ("residents nearby
  (context, not a health effect)") is the model.
- **Air monitors.** Show the nearest monitor per pollutant with its name, its distance from the
  site and the period. No monitor farther away than a limit set in config is shown. No comparison
  against a standard, no colour that implies good or bad, and no trend arrow.
- **No site is ranked or sorted by a context measure.**
- **The banned words stay banned** (`config/wording.json`), and the wording check gains the fixed
  sentence as a required phrase on any page that shows a context section.
- **Regulatory records use the regulator's own neutral terms for the kind of record** (inspection,
  notice, repair, plume notice). An official document title that contains a banned word may appear
  only as a quoted source title, as the wording rules already allow. The page never restates it in
  the project's own voice.
- **Labels name the regulator**, not "the Air District", because sites now fall under several.

## Consequences

- Context adds no claim. If a reader could take a sentence to mean the landfill caused a reading,
  the sentence is wrong and is rewritten.
- Wind-direction analysis that links a monitor to a site is out of scope. It would turn context
  into an attribution claim and would need its own validation.
- **Still to check:** whether EPA's air-monitor files can be read without an account (the server
  was unavailable on 2026-11-19), and which CalEnviroScreen version is final (services for 4.0 and
  5.0 both exist).
