# PR #41: Run the pipeline twice a week on the owner's Mac

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/41)

## In one sentence

The one-command run from fresh satellite data to the review website now has a schedule: the owner's
Mac runs it every Monday and Thursday morning.

## Why it was needed

The previous change made the whole chain one command, but nothing ran it. The owner chose the Mac
over GitHub's servers: the data keys, the full history of downloads and the site outlines are all
there already, nothing leaves the machine, and the repository is public, so a run log on GitHub
would be public too.

## What it adds

- A command that writes the macOS job description. The owner installs it with two commands listed
  in the README; it can be run at once or removed the same way.
- Twice a week, because the free database plan pauses after seven days without activity. A Mac that
  is asleep at the scheduled time runs the job when it wakes.
- The job runs only while the owner's copy of the code is on the main branch. If someone is trying
  out a change on another branch, the run stops and says so instead of publishing from unfinished
  code.
- If a run stops for any reason, a notification appears on the Mac with the step and the reason.
  Everything the job prints goes to a log file.

## What we learned

The owner's working copy was on an old branch, so it has to be switched to main and updated once
before the job is installed. Their unsaved edits to the site list come along unchanged.

## Still to do

- The owner installs the job (README, "Scheduled run").
- The database connection string and the website's keys, so the first run can load real data.
