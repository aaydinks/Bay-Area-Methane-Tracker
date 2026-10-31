# 0010: Dated checks as the unit of the before/after test

- **Status:** accepted
- **Date:** 2026-10-31

## Context

The before/after test (ADR 0006) ran only on operator repairs: `data/registry/repairs.csv` with a
`kind` of well-field, cover, leak-repair or other. The website's checks page (ADR 0009) lists every
dated record at a landfill and the measured change that followed it, and the records that exist in
public documents are mostly not repairs: Air District inspections and notices under Rule 8-34, and
CARB plume notices. The EPA does not inspect these landfills; its figures are annual self-reports and
belong in the operator comparison, not here.

## Options considered

1. Keep `repairs.csv` and add new `kind` values. Rejected: "kind" would mix what was done (a cover
   repair) with who recorded it (an inspection), and the file name would say less than it holds.
2. A second registry of non-repair events with its own runner. Rejected: two files, two loaders and
   two outcome tables for one test.
3. **One registry of dated checks, one test.** Chosen. The type of record rides along as a label.

## Decision

- `data/registry/checks.csv` replaces `repairs.csv`. Columns: `check_id`, `site_id`, `check_type`
  (air-district-inspection, air-district-notice, operator-repair, carb-plume-notice, other),
  `repair_kind` (well-field, cover, leak-repair, other; required for an operator repair, blank
  otherwise), `date_start`, `date_end`, `date_confidence` (exact, week, month), `description` in
  the project's own words, `source_doc`, `source_doc_title` (the official title, which may contain
  words the project itself never uses), `source_url`, `source_page`, `entered_on`.
- No row without a source document. The rule is unchanged.
- The test is unchanged for every type: windows of 12 months, a 14-day gap after the record, at
  least 5 usable passes per window, control sites for common shifts, a call at P = 0.975 and the
  smallest detectable drop from the site's own pass schedule. The outcome table gains `check_type`
  and keeps its other columns.
- The result reads "the change after this record", never a cause. An inspection or a notice is not
  expected to change emissions by itself; the test reports what followed it so the website can show
  it with the same ranges and the same labels as a repair.
- The placebo check still applies to every type: pseudo-dates with no record of any kind give the
  false-positive rate, so a change that follows a notice is judged against the same standard as one
  that follows a repair.

## Consequences

- `mw repair run` keeps its name and now reads `checks.csv`. Internal names (`Repair`, `repair_id`)
  stay, to keep the change small; the run manifest records the check types it covered.
- Existing documents still have to be entered by hand. Nothing is scraped.
- The publishing command will carry `check_type` and the official title through to the website,
  where the title is quoted inside a marked element and everything else is checked for wording.
