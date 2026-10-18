# PR #11: Running summary folder

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/11)

## In one sentence

Started this folder: a plain-language record of the project with one short
file per pull request.

## Why it was needed

The work so far is spread across ten pull requests written for reviewers
who read code. A faculty sponsor, an Air District contact or a new
collaborator needs to follow what was built, why, and what it found, without
reading any code. A running summary also records why decisions were made, so
later changes don't undo them by accident.

## What it adds

- **This folder and its rules** (see the README): one file per pull request,
  named after its number, with the same five headings.
- **Summaries for the two changes already merged:** the project setup (#1) and
  the emissions model with its first test (#2).
- **An automatic check** that fails any future pull request that doesn't add
  its own summary, so the record can't fall behind.
- **A reminder** in the template every new pull request starts from.

## What we learned

Nothing new about methane; this is about keeping the project readable.

## Still to do

The eight open pull requests (#3 to #10) each add their own summary on their
own branch, so every file arrives with the change it describes.
