# 0022: Sector tags and which plumes count for a landfill

- **Status:** accepted
- **Date:** 2026-11-22

## Context

A plume counts for a landfill when it starts on the landfill's outline or within 500 m of it, unless
another known source is as close (PLAN section 5). The only "other known sources" are the ones
written by hand into the registry. That worked for five landfills. With 52 sites, and dairies and
other sources close to several North Valley landfills, nobody has listed the neighbours.

Carbon Mapper tags each plume with the sector it believes the plume came from. The project already
carries that tag (`ipcc_sector`) and did not use it. 0018 decided the rule in one sentence and left
the details to this record.

What the tags look like in the pull of 2026-11-22 (701 plumes in the project's box since August
2022):

| Tag | Plumes | On a site's outline or within 500 m |
|---|---|---|
| Solid Waste (6A) | 657 | 641 |
| Livestock (4B) | 17 | 0 |
| Other | 16 | 11, all on an outline (Kiefer 7, Altamont 4) |
| Oil & Gas (1B2) | 9 | 1 (Vasco Road, in the 500 m band) |
| no tag | 2 | 0 |

One further "Other" plume was already ambiguous under the distance rule.

## Decision

1. **A plume on or beside a landfill whose tag names a sector other than solid waste is marked
   `ambiguous`.** It keeps its tie to the nearest landfill, so it is listed beside that site. It
   never counts as a detection there and never enters a fit.
2. **A plume with no tag follows the distance rule alone.** So does a plume from a source that
   gives no tags, such as NASA's EMIT plume outlines. A missing tag is not evidence of another
   sector.
3. **"Other" counts as another sector.** Carbon Mapper has looked at the plume and not called it
   solid waste. That is enough to hold it back from a landfill's count, even when it starts on the
   landfill's outline.
4. **The waste tags are a setting**, `attribution.waste_sectors` in `config/project.yaml`, with the
   one value `Solid Waste (6A)`. The match is on the exact text.
5. **Plumes further out are unchanged.** `nearby` and `none` were never counted, so the tag does
   not touch them.

## Consequences

- Twelve plumes move from counted to ambiguous, all at screening sites: Kiefer 7, Altamont 4,
  Vasco Road 1. No plume at the five studied landfills changes, so the official fit and the public
  website are not affected.
- The eleven "Other" plumes on the Kiefer and Altamont outlines are the debatable case. A landfill
  can hold a compost pad or a gas-to-energy plant inside its outline, and Carbon Mapper may tag a
  plume from one of those as "Other". Holding them back is the cautious reading for a screening
  list: it can only lower a landfill's count. If the owner later prefers to count them, removing
  point 3 is a one-line change to the setting's meaning and should be recorded here.
- The rule trusts Carbon Mapper's tag. A landfill plume that Carbon Mapper tags wrongly is lost
  from the count; a plume from a neighbour that it tags as solid waste is still counted. The
  hand-listed neighbours in the registry stay as the second guard.
- If Carbon Mapper renames its solid-waste tag, every tagged plume would turn ambiguous. The
  twice-weekly run would then see the detections differ from the official fit and stop before
  making a review copy, which is the intended alarm.
- A published plume does not say why it is ambiguous. The sector tag stays in the working tables,
  not in the published ones.

## Still to check

- Whether Carbon Mapper documents how the "Other" tag is assigned.
