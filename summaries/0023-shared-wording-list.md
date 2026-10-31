# PR #23: Shared wording list for Python and the web

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/23)

## In one sentence

The words that generated pages may never use, and the phrases they must carry, now live in one
shared file that both the Python report check and the coming website build read.

## Why it was needed

Every page this project produces is a screening indication from a retrospective tracker. A wording
check enforces that: it fails a build that says "saved", "real-time", "violation", "non-compliant",
"illegal", "lives" or "health impact", and it requires "retrospective" in the home page header and
"screening indication" on every site page. The website will be built in a second language, and a
rule that lives in two places drifts. One file, read by both, cannot.

## What it adds

- `config/wording.json`: the seven banned patterns with a one-line reason each, the required
  phrases for every page kind (the existing report pages and the new website pages), and the one
  allowance: "saved" is permitted only on a page about a verified drop.
- One narrow exception. Official documents have formal names, and an Air District notice is called
  what it is called. Such a title may appear only inside an element marked as a source title, or in
  the title field of a record; the check skips exactly that and nothing else. The same word anywhere
  else on the page still fails the build.
- A check for plain text fields, so registry descriptions and database text can be tested before
  they are published, not only finished pages.
- A reworded population label, "residents nearby (context only)". The old one ended in "not a health
  effect", which the check itself bans.
- Tests for each pattern's spelling variants, for the exception, for the required phrases per page
  kind, and a guard that the patterns use only constructs JavaScript understands.

## What we learned

The project's own label for population context had quietly broken its own rule for weeks, because
nothing ever rendered it through the check. Running the check on text fields, not just pages, is what
caught it.

## Still to do

The website build reads the same file and fails on a hit (web skeleton pull request). The publishing
command runs the text check over every description and plain reading before loading them.
