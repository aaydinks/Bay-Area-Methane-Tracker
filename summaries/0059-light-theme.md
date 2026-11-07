# PR #59: One light theme in white, black, red and light green

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/59)

## In one sentence

The website now has a single light look built from four colours (white, black, red and a calm
light green), with bold type kept for titles only.

## Why it was needed

The site followed the computer's dark setting, so on a Mac in dark mode it opened almost black,
and its teal, blue, purple, orange and yellow accents made it look generic. The owner asked for
the whole site to use white, black, red and light green, and for bold to be used only on titles.

## What it adds

- **Colours.** White pages, black text, red for link underlines, highlights and marks, and light
  green for backgrounds and fills. Light green is never used for text, so everything stays
  readable (the accessibility scan passes on every page).
- **No dark mode.** The theme switch is gone, and the site stays light even when the computer asks
  for dark. A test checks this.
- **Results without orange or yellow.** The five result levels keep their icons and labels and are
  told apart by fill: solid red (severe increase), a red tint (moderate), a dashed red outline
  (small or uncertain), light green (no increase) and grey (not enough data). The decision record
  for the website (ADR 0009) notes the change.
- **Map and charts.** Plume marks are red, pass circles black, site outlines green, and the heat
  map runs from light green to dark red. Chart dots are red on black lines; pass bars are green.
  The map always uses its light base map.
- **Bold for titles only.** Headings and the short titles that open a paragraph stay bold; table
  headers, badges, figures and labels are now regular weight.
- The preview images for shared links and the browser tab icon use the same colours.

## What we learned

Nothing new about the data.

## Still to do

The home page itself is reworked next: fewer words, satellite and aerial pictures, and carousels
that move on their own.
