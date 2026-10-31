# PR #42: Keep Carbon Mapper's figures off open passes and list NASA's own EMIT plumes

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/42)

## In one sentence

A published snapshot no longer lets Carbon Mapper's restricted plumes mark an open satellite pass as
having seen a plume, and it now lists NASA's own EMIT plume complexes as open data.

## Why it was needed

Carbon Mapper's data may not be passed on, so its rows are marked restricted and the public website
never shows them. But Carbon Mapper also republishes plumes that NASA's EMIT instrument saw. Those
copies were counted when the pipeline decided whether an EMIT pass saw a plume, and EMIT passes are
open. A check of the first real snapshot found three EMIT passes over Newby Island (Aug 3 and Aug 7,
2024, and Aug 18, 2025) showing a plume and a rate of about 1,631, 5,318 and 1,180 kg/hr, all taken
from Carbon Mapper's copies. A public build would have shown them, and the monthly pass counts on the
website would have included them. At the same time, every plume in the snapshot was Carbon Mapper's,
so the public website would have had no plumes at all, although NASA publishes its own.

## What it adds

- For a pass by an open instrument (EMIT, Sentinel-2), whether a plume was seen, its rate and the
  number of plumes are now worked out again from open sources only, using the same rule as the rest of
  the pipeline. Passes by Carbon Mapper's own aircraft and satellite are unchanged; they are
  restricted anyway.
- NASA's EMIT plume complexes are added to the snapshot's plume list as open rows. Each is placed at
  the centre of its outline, matched to a landfill with the project's usual rule (inside the outline
  or within 500 m), and linked to the pass it was seen on when that pass exists. The rate is left
  empty because NASA's catalogue entry does not give one.
- The model's inputs are not changed: these complexes are only listed in the snapshot.
- Two tests: a Carbon Mapper plume can never mark an open pass, and a NASA complex appears as open
  data linked to its pass.

## What we learned

On the real data exactly three passes changed, the three above: each now shows no plume. All 25
detections on restricted passes and all 614 Carbon Mapper plumes are unchanged. Seven NASA complexes
were added. Only one lies at a pilot landfill: the Aug 7, 2024 complex at Newby Island, 0.2 m outside
the site outline, linked to that day's pass. NASA lists no complex at Newby Island on Aug 3, 2024
(its only complex that day is about 17 km from the nearest pilot site) or on Aug 18, 2025. Because NASA's complex has no rate, the Aug 7 pass shows the complex in the plume list but is not
counted as a pass that saw a plume. That follows the model's rule that a detection needs a rate.

## Still to do

- Decide whether NASA's complexes should feed the model. That needs a rate for each complex (NASA's
  files behind an Earthdata login, or our own estimate) and a rule for Carbon Mapper's 20 copies of
  EMIT plumes, so the same plume is not counted twice.
- The review build now shows both Carbon Mapper's copy and NASA's complex for the Aug 7, 2024 plume;
  only NASA's appears on the public website.
