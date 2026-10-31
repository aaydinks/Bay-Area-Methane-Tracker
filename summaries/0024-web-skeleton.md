# PR #24: Website skeleton with build-time data and checks

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/24)

## In one sentence

The public website now exists as a working shell: every page is in place with its framing and an
empty state, it is built from one published snapshot, and two checks stop a build that uses the
wrong words or lets restricted data through.

## Why it was needed

The review with operators and the Air District starts Dec 9, 2026 and the public launch is Jan 6
to 8, 2027. Before any page can be designed in earnest, the plumbing has to be right: where data
comes from, how a private review build differs from the public one, how Carbon Mapper data is kept
out of the public site, and how the project's wording rules are enforced on every page. Doing that
first means every later page inherits it.

## What it adds

- A static site in a `web/` folder. A build pulls one published snapshot from the database (or sample
  rows from a committed fixture, so tests need no keys) and writes it as files; the pages never
  query anything while a visitor reads them, and the browser never receives a key.
- Two build modes. A review build includes rows from sources whose terms are unconfirmed and needs
  the secret key. A public build shows only public, unrestricted rows and refuses to run if a secret
  key is present at all.
- A wording check that reads the shared word list and scans the visible text of every page, alt text
  and labels included, skipping only an official document title marked as such. A public-output
  check that fails if any restricted row, restricted source or instrument, simulated-data banner or
  key reached the finished files. Both were tried against planted failures and caught them.
- Nine pages with real wiring: home, a map table (the interactive map comes next), the update feed,
  past checks, the landfills and one page per landfill, methods with the real gate results, how to
  read this site, data and credits, and a not-found page. Every view says what is missing and when it
  is expected. Dark mode, a skip link and keyboard-reachable tables are in the shared layout.
- A continuous-integration job that lints, type checks, builds in both modes, runs both checks and
  runs an automated accessibility scan on every page kind. Eleven accessibility tests pass.
- The hosting settings the owner enters in Cloudflare Pages, in the folder's README.

## What we learned

Keeping the data step separate from the page step makes the safety argument short: a public build
is safe if its snapshot is safe, and a scan of that snapshot plus the finished files can say so. The
first commit tripped the project's own attribution check on an innocent phrase, which the check
reads too broadly; the phrase was reworded rather than the check overridden.

## Still to do

Create the Cloudflare Pages project and its access policy (owner). Then the real pages, each in its
own pull request: the home page with its animation and carousels, the interactive map, the sortable
checks table, the landfill pages with charts, downloads, and the update feed.
