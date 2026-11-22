# PR #82: Four studied landfills get their real outlines

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/82)

## In one sentence

Newby Island, Acme Fill, Sonoma Central and Potrero Hills now use the outline CalRecycle drew from
permit maps instead of a placeholder circle, which changes one landfill's plume count and so calls
for a new model fit.

## Why it was needed

Since the first real results, each studied landfill was a 500 m circle around a single reference
point. That was always a stand-in. A plume counts for a landfill when it starts on its outline or
within 500 m, so a wrong outline can miss plumes or count the wrong ones. CalRecycle publishes
drawn outlines for four of the five, the same source already used for the screening sites.

## What it adds

- **Real outlines for four landfills.** They are larger than the circles: Newby Island 1.37 km²,
  Acme Fill 1.86, Sonoma Central 1.59 and Potrero Hills 1.29, against 0.79 km² for a circle.
- **Shoreline keeps its circle.** CalRecycle's layer has no outline for it, so it stays marked
  provisional.

Nothing on the public website changes with this step. The public copy was made earlier and keeps
its figures until the owner promotes a new one.

## What we learned

- **Only Potrero Hills gains plumes.** Four plumes that were between 500 m and 5 km from its circle
  are within 500 m of its real outline. That adds three passes with a detection there (28 to 31
  across the five landfills). The number of usable passes does not change anywhere.
- **Newby Island's count is the same.** All 269 of its plumes are now on the outline itself; 16 of
  them were in the 500 m band before.
- **Acme Fill still has none.** Its six nearby plumes are tagged oil and gas and stay outside the
  500 m band.
- **Sentinel-2 barely moves.** The cloud windows were read again around the new centres (1,677 of
  them). The clear-sky share changes by more than 0.05 on 6 of 2,019 passes, and one pass at Sonoma
  Central stops being usable.
- **A refit is ready.** Fitting the five landfills on the new outlines passes its diagnostics. Newby
  Island is about 14,500 tonnes a year (11,400 to 18,200), against 14,100 (11,300 to 17,700) before.
  Potrero Hills is about 1,440 (760 to 2,390), against 750 (310 to 1,470). Acme Fill, Shoreline and
  Sonoma Central still have too little data for an estimate. All figures stay provisional.

## Still to do

- **Name the new fit as the official one (owner's decision).** Until then the twice-weekly run
  loads draft copies and the review copy keeps the old outlines and figures.
- Draw or find an outline for Shoreline.
- The neighbouring sources at Newby Island (compost, energy, wastewater) still have no outlines.
