# Report: <feature>

- **Design:** `.orchestration/designs/<feature>.md`
- **Branch:** `ai-feat/<branch-name>`
- **Head commit:** <sha>
- **Pushed to origin:** yes | no
- **Round:** 1 | 2 | 3

## Summary of changes

What was built, in plain words. A reader who has not seen the diff should understand it.

## Acceptance criteria

One row per criterion in the design. Evidence is a commit, file path, or command with output.

| Criterion | Status | Evidence |
| --- | --- | --- |
| AC-1 | met / not met / partial | ... |
| AC-2 | ... | ... |

## Tests run

Each command, and its actual output (trimmed to the relevant lines). Report failures as
failures.

```
<command>
<output>
```

## Files changed

| Path | Change |
| --- | --- |
| ... | added / modified / removed, and why |

## System report (as built)

Backend-only. No screens, layout or visual design. Same parts as the design, so the two can
be compared.

### Packages

| Package | Original or third-party | Purpose |
| --- | --- | --- |
| ... | ... | ... |

### Primitives

### High-level workflows

### Data and endpoints

## Deviations from the design

What differs from the design and why. Write "None" if nothing differs.

## Not done or not verified

Anything left unfinished, untested or uncertain. Write "None" if nothing.
