# Design: site

- **Branch:** `ai-feat/site`
- **Status:** implementing
- **Approved by user:** 2026-11-16

## Goal

The Astro site itself: design tokens, the UI building blocks, the home page, the blog with
markdown rendering, and the workflow for adding content. Simple and polished. It consumes
wireframe loops produced by the `art` design through a fixed file contract.

## Scope

**In:**

- Astro project, static output, deployable to Cloudflare Pages as-is.
- Tokens: the palette in `CLAUDE.md`, type scale, spacing, motion durations.
- UI blocks: `Split` (two-pane page shell), `Art` (loop player with blur-in), `Dither`
  (dithered beetle gradient), `EntryList` (the rows on the home page), `LinkRow`, `BackLink`,
  `Prose` (markdown wrapper), `PostList`.
- Home page: text pane left, art pane right, links along the bottom of the text pane.
- Blog index and blog posts: mirrored, art pane left, text pane right, back arrow at the top
  of the left pane.
- Markdown: bold, links, footnotes, images between paragraphs, code blocks, blockquotes,
  lists, headings, tables, horizontal rules.
- Content workflow: `pnpm new-post "Title"`, `src/content/site.yaml` for the home page.
- A `/blocks` page that shows every block and every markdown element, for review.
- Self-test with screenshots.

**Out:**

- Real content. Placeholder copy only: the owner's name as "Your Name", two sample posts.
- Rendering art (the `art` design). This design ships one placeholder loop only.
- Light theme, search, RSS, comments, analytics, CMS.
- Creating the Cloudflare project (needs the owner's account).

## Acceptance criteria

- **AC-1:** `pnpm install && pnpm build` exits 0 and writes `dist/` with `/`, `/blog/`, one
  page per sample post, and `/blocks/`. Evidence: command output and `ls dist`.
- **AC-2:** Home page uses `Split` with text left and art right; the text pane shows name,
  role, the entry rows and a bottom link row, all read from `src/content/site.yaml`.
  Evidence: screenshot at 1440x900 and the yaml.
- **AC-3:** Blog index and post pages use `Split` mirrored (art left, text right) with a back
  arrow at the top of the left pane: post goes to `/blog/`, index goes to `/`. The art pane
  stays fixed while the text pane scrolls. Evidence: screenshots at scroll top and scrolled.
- **AC-4:** Below 800px wide every page opens with the art filling the top of the screen and
  the text starting under it, no horizontal scroll. Scrolling down the first 120px or so
  dissolves the art (opacity and blur tied to scroll position, the art stays fixed behind)
  into the content; scrolling back to the top restores it. Scroll-linked, not a timed
  animation, with no jank and no layout shift; the video pauses while fully dissolved. Uses
  CSS scroll-driven animation where supported with a small script fallback. Evidence:
  screenshots at 390x844 of home and a post at scroll 0, 60, 200 and back at 0.
- **AC-5:** `Art` takes a `slug`, reads `public/art/<slug>/meta.json` at build, and renders
  the inline blurred still from `meta.blurDataUrl` immediately; when the video can play it
  crossfades and the blur animates to 0. If the video is already cached there is no flash of
  blur longer than one frame. Falls back to slug `_placeholder` when the folder is missing.
  Evidence: self-test that throttles the video request and captures before/after frames.
- **AC-6:** The video is composited so only its light lines show over whatever is behind it
  (`mix-blend-mode: screen` on a black-matte video, or an equivalent that works in Chrome,
  Safari and Firefox). Evidence: screenshot of `Art` over a `Dither` on `/blocks`.
- **AC-7:** `prefers-reduced-motion: reduce` shows the still poster and never plays the video;
  page transitions are disabled. Evidence: self-test with the media feature emulated.
- **AC-8:** `Dither` renders an ordered (Bayer) dither of a gradient between palette colours,
  drawn once to a canvas at device pixel ratio, with props for the colour stops, cell size,
  and direction. It is static: no animation loop runs. Used at least on the home art pane.
  Evidence: screenshot and a note of where it is used.
- **AC-9:** In rendered markdown, `**bold**` is `--emerald`; links, footnote reference marks
  and the footnote back-arrows use palette accents; body text is `--ink`. Evidence: computed
  styles asserted in the self-test.
- **AC-10:** GFM footnotes render as a numbered list at the end of the post, with working
  jumps both ways and a visible target highlight. Evidence: self-test clicks ref and back.
- **AC-11:** An image placed in a post folder and referenced as `![alt](./file.png)` renders
  between paragraphs at text-column width, optimised (responsive `srcset`, lazy, width and
  height set, no layout shift), with the alt text as an optional caption when a title is
  given. Evidence: built HTML of the sample post.
- **AC-12:** The only monospace text on the site is inside `pre` and inline `code`. Evidence:
  self-test walks every text node on every built page and asserts the computed font family.
- **AC-13:** Post frontmatter is `title`, `date`, `art`, optional `draft` and `summary`,
  validated by a content collection schema; a bad file fails the build with the file name.
  `draft: true` posts are left out of production builds. Evidence: build output of a
  deliberately broken fixture, then removed.
- **AC-14:** `pnpm new-post "Some Title"` creates `src/content/blog/some-title/index.md` with
  filled frontmatter (today's date, `art: _placeholder`) and refuses to overwrite. Evidence:
  command output.
- **AC-15:** Navigation between pages uses Astro view transitions: the text pane fades, the
  art pane crossfades, no full white or black flash. Evidence: self-test records the
  navigation and saves three frames.
- **AC-16:** `pnpm test` runs the self-test headless, saves screenshots to
  `.orchestration/reports/site-shots/`, and exits non-zero on any failed assertion.
  Evidence: command output and the files.
- **AC-17:** Lighthouse (mobile, production build, local) scores at least 95 for performance
  and 100 for accessibility on home and a post. Evidence: the scores.
- **AC-18:** No visible copy other than names, labels, dates, sample post text and link text:
  no taglines, no subtitles under headings, no "welcome" lines. Evidence: full text dump of
  home, blog index and `/blocks` in the report.

## System report (intended state)

### Packages

| Package | Original or third-party | Purpose |
| --- | --- | --- |
| `astro` | third-party | Static site, content collections, view transitions, image optimisation, Shiki |
| `tailwindcss` v4, `@tailwindcss/vite` | third-party | Styling utilities, tokens as theme variables |
| `@tailwindcss/typography` | third-party | Base for markdown prose, overridden with the palette |
| `@fontsource-variable/instrument-sans` | third-party | Self-hosted sans (one token to swap) |
| `@fontsource-variable/jetbrains-mono` | third-party | Code blocks only |
| `playwright` (dev) | third-party | Self-test and screenshots |
| `src/components/*` | original | The UI blocks |
| `scripts/new-post.mjs` | original | Post scaffolder |
| `tests/site.spec.mjs` | original | Self-test |

Adding another package is allowed when it replaces hand-written code; list it in the report.

### Primitives

- **Post:** a folder in `src/content/blog/` with `index.md` and its images.
- **Site config:** `src/content/site.yaml` (name, role, entries, links, home art slug).
- **Art reference:** a slug that resolves to `public/art/<slug>/`.
- **Tokens:** CSS custom properties for colour, type, space, motion.

### High-level workflows

- New post: `pnpm new-post` → write markdown, drop images in the folder → set `art` → push.
- Build: content collections validate → pages render → art `meta.json` read per page.
- Art load: inline blurred still → video `canplay` → crossfade.

### Data and endpoints

- Reads `public/art/<slug>/{loop.webm,loop.mp4,poster.png,meta.json}`.
- `meta.json`: `{ slug, subject, width, height, fps, frames, duration, blurDataUrl }`.
- No server endpoints.

## Constraints and notes

- **Owns:** `src/`, `public/` except `public/art/*` other than `public/art/_placeholder/`,
  `scripts/`, `tests/`, `package.json`, `pnpm-lock.yaml`, `astro.config.*`, `tsconfig.json`,
  `.orchestration/reports/site.md`, `.orchestration/reports/site-shots/`.
- **Must not touch:** `art/`, `public/art/<anything but _placeholder>`, `.claude/`,
  `CLAUDE.md`, `.gitignore`, other designs or reports.
- `package.json` must include `"art": "python3 art/cli.py"`; the file itself belongs to the
  `art` design and will not exist on this branch.
- `public/art/_placeholder/` must follow the contract above. Make it however is quickest
  (Blender is installed); it is a stand-in, not judged for quality.
- Follow the house rules in `CLAUDE.md`. Use the `frontend-design` skill if available.
- Polish means: consistent spacing rhythm, optical alignment of the two panes, restrained
  motion (150-400ms, one easing curve), visible focus states, no layout shift.

## How to test

```bash
pnpm install
pnpm build
pnpm test
```

Passing: all three exit 0, screenshots exist for home, blog index, post (top and scrolled),
`/blocks`, mobile home, mobile post, and the report lists any interaction not proven by the
self-test.
