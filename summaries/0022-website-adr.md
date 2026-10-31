# PR #22: ADR 0009, public website and publishing database

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/22)

## In one sentence

A decision record sets down how the public website will be built, hosted, protected during the
December review and fed from a database, and why each alternative lost.

## Why it was needed

The private review with operators and the Air District runs Dec 9 to 23, 2026, and the public launch
is Jan 6 to 8, 2027. Several choices had to be made together before any code: where the site runs and
how reviewers get in without accounts, which framework keeps pages light on phones, how figures stay
tied to a named run, and how Carbon Mapper data stays private until its terms are confirmed. Writing
them down once keeps the later pull requests small and consistent.

## What it adds

- The hosting choice: Cloudflare Pages with Cloudflare Access. Reviewers enter an email and receive a
  one-time code; the owner keeps the list of allowed addresses; the public domain stays locked until
  launch day. Vercel's free plan was checked and rejected because it offers no password gate and only
  one shareable link per account; its paid plan would cost about $40 a month.
- The framework: Astro with a few interactive islands (the map, the checks table, carousels), hand-built
  charts, and a short list of libraries.
- The data path: a Supabase database holds one complete snapshot per published run, each with a
  visibility of draft, review or public. Rows from sources whose publication terms are unconfirmed are
  flagged restricted and hidden from the public key. The website reads the database only when it is
  built, so the browser never holds a key and the site keeps working if the free database pauses.
- Three safeguards against Carbon Mapper data reaching the public site: the database rules, a build
  that refuses to run with a secret key in a public environment, and a scan of the finished pages.
- The result labels for the checks page: strength of evidence from the existing call rule, size of
  change on the log scale with cutoffs at 1.33x and 2x (marked unconfirmed until the owner confirms
  them), and the colour rule with its two gaps settled: insufficient data is grey, a strongly supported
  slight increase is yellow.
- Five check types (Air District inspection, Air District notice, operator repair, CARB plume notice,
  other), map symbols where shape means record type and colour means result only, and a shared wording
  list for Python and the web.
- A list of the tasks only the owner can do: accounts, keys, the domain, approving migrations, and the
  question to Carbon Mapper.

## What we learned

The review gate drove the hosting choice more than anything else. Free hosting is easy to find; a free
way to let a dozen named outsiders in, and nobody else, is not, and Cloudflare Access was the only
option that did it without a shared password.

## Still to do

Everything the record describes: the database schema (PR #21), the shared wording list, the checks
registry, the publishing command, and the website itself.
