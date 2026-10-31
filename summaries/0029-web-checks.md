# PR #29: Checks page as a sortable table with phone cards

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/29)

## In one sentence

The past-checks page now sorts, filters and expands on a desktop, and turns into colour-edged
cards on a phone, showing the same facts either way.

## Why it was needed

The checks page is the one regulators and operators will read most closely during the December
review. A plain table could not be sorted by result or narrowed to one landfill, and on a phone
its nine columns were unreadable. The brief asked for both views, with the same data, and for
colour that never carries meaning alone.

## What it adds

- On wide screens: a table that sorts on any column (date, landfill, record, result, change,
  evidence, passes, smallest detectable drop) and filters by landfill, record type and result.
  A button on each row expands it to the plain one-line reading, the change in percent and in
  tonnes a year with their 90% ranges, the evidence and probability of a decrease, the passes
  before and after, the smallest drop the test could have seen, the record's description and
  its source document.
- On phones: the same rows as cards titled "date · landfill · record", edged in the result
  colour and expanding to the same detail.
- Every result shows an icon and a text label beside its colour; the official title of a source
  document is quoted inside its marked element, so the wording check still covers everything
  else on the page.
- A count of rows shown that updates as filters change, read out to screen readers.

## What we learned

Nothing new about the data; the sample rows made clear that a result the public site holds
back (because it used Carbon Mapper passes) needs its own label, "Result held back", rather
than looking like a missing test.

## Still to do

The landfill pages with their pass timelines and estimate charts, and the downloads page.
