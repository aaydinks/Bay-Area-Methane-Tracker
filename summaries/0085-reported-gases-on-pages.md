# PR #85: Each landfill's page shows the gases reported to EPA

**Status:** merged 2026-11-23 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/85)

## In one sentence

A landfill's page now has a section with the figures its operator reported to EPA, year by
year and gas by gas, and it says "not reported" where there is no figure.

## Why it was needed

PR 84 gave the project a place to keep measures that are not methane estimates, and filled it
with EPA's reported gases. Nothing showed them. The owner asked for CO2 and other gases beside
the methane estimate, and the reported figures are the part of that the public data can support.

## What it adds

- **A new section on every landfill page**, under Details: "Gases and other figures reported
  for this landfill". It holds one table per source. For EPA, each row is a year and each column
  a gas, in tonnes of CO2 equivalent as EPA publishes them.
- **Gaps are spelled out.** A year with no figure reads "not reported". A gas the landfill never
  reported is named under the table. A landfill with nothing on file gets one sentence saying
  so, and that its record may not have been matched yet.
- **Labels and caveats come from the catalogue** published with each copy, so the page and the
  data cannot drift apart.
- **A download, `site_measures.csv`**, with the same rows.
- **The same public rules as everything else.** A public build drops measures from sources whose
  terms do not allow publishing, and every row about a landfill still under review. The check
  that runs after each public build now covers the new download.
- **Up-to-date database types for the website.** The committed file was several migrations
  behind; it is now the generator's output for the live database.

## What we learned

- **The public site does not change with this step.** The public copy was made before the
  measures existed, so it carries no catalogue, and the section and the download are left out
  for it. A build of the public site from the live database confirmed this: the same 15 pages
  and the same seven downloads. The section will appear for the five studied landfills when the
  owner next promotes a copy.
- **On the review copy it works for all 52 landfills.** The four matched landfills show their
  figures (Sonoma Central: 107,440 t of landfill methane and 10,379 t of biogenic CO2 for 2023).
  The other 48 say nothing is on file.
- **The table fits a desktop page and scrolls sideways on a phone**, with no sideways scroll of
  the page itself.

## Still to do

- Rebuild the locked review website so reviewers see the section (owner's go-ahead).
- Match the 47 screening landfills to their EPA records by hand, so they show figures and not
  the "nothing on file" sentence.
- The section's wording gets another look with the many-landfill pages (step 13).
