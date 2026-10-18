# Running summary

One short file per pull request, in plain language. Read them in number order
for the story of the project: what each change was for, why it was needed at
that point, and what it found. No knowledge of the code is needed.

**The project in one paragraph.** Bay Area Landfill Methane Watch is an open,
retrospective tracker built from public satellite data. It estimates how
persistently each Bay Area landfill leaks methane, checks whether documented
repairs reduced emissions, and compares those estimates with what operators
report to the EPA. Results are screening indications for investigation, never
compliance findings. The full plan is in [`docs/PLAN.md`](../docs/PLAN.md).

## Adding a summary

Every pull request adds one file here. CI fails a pull request that doesn't.

- **Name:** `NNNN-short-title.md`, where `NNNN` is the pull request number
  padded to four digits, e.g. `0012-carbon-mapper-ingest.md`.
- **Audience:** someone who knows the project's goal but has never opened the
  code: a sponsor, a regulator, a new collaborator.
- **Length:** about one screen. Plain words; numbers with units; no file or
  function names unless a reader needs to find something.

Use these headings:

```markdown
# PR #N: <title>

**Status:** open | merged <date> · [pull request](<link>)

## In one sentence
## Why it was needed
## What it adds
## What we learned
## Still to do
```

"What we learned" can say "nothing new" for routine changes. Keep the earlier
files as they are; when a later change supersedes something, say so in the
new file.
