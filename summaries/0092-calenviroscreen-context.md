# PR #92: The area around each landfill, from the state's CalEnviroScreen

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/92)

## In one sentence

A landfill's page can now show how the state scores the census tracts around it, as plainly
labelled context that is never attributed to the landfill.

## Why it was needed

The methane estimate says how much a landfill seems to leak. It says nothing about who is
nearby. California already scores every census tract for this, in a tool called CalEnviroScreen:
it combines measures of pollution with measures of the people living in the tract, and says
where the tract stands among all the state's tracts. A regulator or a neighbour deciding where
to look first will want that beside the estimate.

It is also the kind of figure most easily misread. A tract's score reflects traffic, industry,
farming and much else, so the page must not let it read as the landfill's doing. The project set
wording rules for this earlier (decision record 0020). This is the first source to use them.

## What it adds

- **A new pull, `mw ingest calenviroscreen`.** It downloads the state's file of census tracts
  for CalEnviroScreen 5.0, the final version released on July 1, 2026. It stops if the state's
  data portal lists two such files, none, or one whose layout has changed.
- **Eight figures per landfill, as published:**
  - the census tract that holds most of the landfill's outline, and how many people live in it;
  - that tract's overall percentile and its two parts, Pollution Burden and Population
    Characteristics;
  - how many tracts come within 1 km of the outline, and the lowest and highest overall
    percentile among them.
- **A new section on each landfill's page, "The area around this landfill".** It opens with one
  fixed sentence: the figures describe the area and are not attributed to the landfill.
- **A check that enforces the sentence.** The build now fails any page that shows such a section
  without it.
- **Decision record 0026.**

Four rules keep the section honest:

- Nothing is averaged. The lowest and highest are the state's own figures for those tracts.
- A tract the state gives no score reads "no score". It is never shown as zero.
- No landfill is ranked, coloured or compared with a threshold by these figures.
- Where a landfill's outline is still a placeholder circle, the page says the tract may change.

## What we learned

- **Version 5.0 is final.** An earlier note had left open whether 4.0 or 5.0 was current.
- **Every one of the 52 landfills sits in a tract with a score.** The 52 landfills sit in 44
  different tracts, because some neighbours share one.
- **One tract is often not the whole story.** For 21 landfills the outline crosses more than one
  tract. For 24, the tracts within 1 km differ by 25 percentile points or more. This is why the
  page gives the lowest and highest, and not a single number.
- **A landfill is often part of its own tract's score.** One of the state's pollution measures
  counts solid waste sites near homes. The page says so beside the overall percentile.
- **The state does not say how the data may be reused.** Its data portal reads "License not
  specified", and the agency's conditions of use do not cover reuse. The data are a public
  download, but the project's rule is that terms are confirmed, not assumed.

## Still to do

- **Ask the agency about reuse.** Until the Office of Environmental Health Hazard Assessment
  confirms the scores may be republished with credit, these figures appear in review copies
  only. The public site shows no figure and no section. One line in the source terms opens it.
- **The public list of sources gains one line** for this source, marked "to confirm", and the
  footer gains its credit, the next time a copy is loaded. That list is shared by every copy.
- **23 landfills have a placeholder outline.** Their tract may change when the outline is drawn.
- **The pull is run by hand,** and must be rerun after an outline changes. It is not part of the
  twice-weekly run; the file changes only with a new version of the tool.
- **The state's "disadvantaged community" list** is a separate decision with its own date and
  is not in this change.
