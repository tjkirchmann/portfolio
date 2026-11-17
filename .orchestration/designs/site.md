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

## Amendment 1 (2026-11-16, from the owner after seeing the site)

Where this amendment conflicts with the text above, the amendment wins.

### Dithered life simulation (replaces AC-8)

Reference: `.orchestration/designs/ref/dither-reference.webp`, the owner's first inspiration
image. Open it. What matters in it: large soft organic masses, built entirely from square
pixels on a grid, solid in the middle and breaking into ordered halftone at the edges, with
wide areas of pure black between them. The owner wants that, alive, in the beetle palette,
in place of the static gradient.

- **AC-19:** `Dither` becomes a life-like simulation rendered through an ordered (Bayer)
  dither. A field evolves on a coarse grid; its value at each cell goes through the Bayer
  threshold, so dense regions are solid squares and edges break into halftone, as in the
  reference. Square cells, crisp (no smoothing, no blur), cell size a prop (default about
  6 CSS px), aligned to the device pixel grid.
- **AC-20 explore:** build three variants behind one `mode` prop and show all three, large,
  on `/blocks` for the owner to pick from:
  1. `life`: a Conway-family cellular automaton (pick a rule that neither dies nor fills,
     reseeding quietly if it stalls) where each cell leaves a decaying trail; the trail
     value is what gets dithered.
  2. `smooth`: a continuous life-like field (SmoothLife or Lenia style kernel) that grows
     soft drifting blobs; the field value is dithered. Closest to the reference.
  3. `flow`: a reaction-diffusion (Gray-Scott) field, dithered.
  Put whichever best matches the reference on the home, blog and post art panes, and say
  which and why in the report.
- **AC-21 colour:** the palette in `CLAUDE.md`, all of it, not only greens. Colour is mapped
  from the field (for example age or density: deep and teal in young or sparse areas,
  emerald in the body, gold and copper where it is oldest or densest) so the masses show
  the beetle's green-to-gold-to-copper shift. Pure `--bg` where the field is empty; at
  least 35% of the pane is empty at any time. The wireframe video still screen-blends on
  top and must stay clearly readable: cap the brightness behind it if needed.
- **AC-22 cost and manners:** the simulation steps slowly (about 8-15 steps per second,
  not every frame), draws to a canvas at grid resolution scaled up with
  `image-rendering: pixelated`, pauses when the pane is off-screen, the tab is hidden, or
  the mobile art is fully dissolved, and under `prefers-reduced-motion` shows one settled
  frame and never steps. Main-thread cost under 2ms per step on this machine. It is seeded
  per page (from the page slug) so each page has its own pattern, and it starts from a
  pre-evolved state, never from noise or blank. Evidence: timings, a test that counts steps
  per second and proves each pause, screenshots at 0s, 5s and 20s per mode.
- AC-17 (Lighthouse) still holds with the simulation running.

### Home page timelines (replaces `EntryList` on the home page, amends AC-2)

- **AC-23 `Timeline` block:** a vertical stepped timeline. Each step has an icon node on a
  rail, with a connecting line between nodes; to the right of the node, the title; at the
  far right, the year. Optional subtitle under the title. Optional link on the title. The
  icon is chosen per entry by name from one icon set (a third-party set, inlined as SVG at
  build, no icon font, no client JS), with a default icon when none is given. The rail,
  nodes and icons use palette accents sparingly; the newest step may be marked as current.
- **AC-24 two timelines on home:** `Projects` (icon, title, year) and `Companies` (icon,
  company name as title, the role as subtitle, year or year range on the right). Each has a
  short label (just the word). Both read from `src/content/site.yaml`, which gains
  `projects:` and `companies:` lists with `title`, `subtitle?`, `year`, `icon?`, `href?`.
  Schema-validated like posts: a bad entry fails the build with a clear message.
- **AC-25 the 50/50 split:** on desktop the area between the name/role header and the
  bottom link row is divided into two equal halves, Projects on top, Companies below, each
  exactly 50% of that space regardless of how many entries it has. A half with more
  entries than fit scrolls inside itself, with a soft fade at the clipped edge and no
  visible scrollbar chrome; a half with few entries aligns its content to the top. The
  page itself does not scroll on desktop at 1440x900 or 1280x720. Below 800px the two
  timelines stack at natural height and the page scrolls. Evidence: the test measures both
  halves equal within 1px at three viewport heights, with 3 entries and with 12.
- **AC-26:** `/blocks` shows `Timeline` in both forms, including the overflow case.
- AC-18 still applies: labels and data only.

Report as round 2 in `.orchestration/reports/site.md`: add rows AC-19 to AC-26, mark AC-8 as
replaced, keep the earlier rows, rerun `pnpm test` and Lighthouse, and replace the
screenshots that changed.

## Amendment 2 (2026-11-16, from the owner)

- **AC-27 locked shell on blog pages (amends AC-3):** on desktop (800px and wider) the blog
  index and post pages never scroll the document. The shell is exactly one viewport tall,
  the art pane and back arrow stay put, and only the text pane scrolls, inside itself. The
  owner's words: "lock the background of the site and have interior scroll only". The
  scrolling pane must: take wheel, trackpad, keyboard (Space, PageDown, arrows, Home, End)
  without a click first; keep footnote jumps and their highlight working inside it; keep
  heading anchors and in-page links working; restore its scroll position on back/forward;
  start at the top on a new post; have a thin unobtrusive scrollbar in palette tones and a
  soft fade at the top and bottom edges where content is clipped; and leave comfortable
  padding above the title and below the last line. No double scrollbars, no overscroll
  chaining that moves the page. Below 800px nothing changes: the document scrolls and the
  art dissolve from AC-4 stays as it is. Evidence: the test asserts
  `document.scrollingElement.scrollHeight === innerHeight` on the post at 1440x900 and
  1280x720, scrolls the pane with wheel and keyboard, repeats the footnote round trip, and
  checks back/forward restoration; screenshots at pane top, middle and end.

## Amendment 3 (2026-11-16, from the owner after seeing round 2)

The owner's words: "the game of life patch is too splotchy and i want you to remove the
orange and yellow as design elements."

- **AC-28 greens only, site-wide.** Gold, copper, bronze and the yellow-green `leaf` are
  removed as design elements everywhere: tokens, simulation, footnote marks and
  back-arrows, footnote target highlight, code theme, timeline accents, focus rings,
  anything else. The accent palette is `--emerald #76c8a5`, `--teal #579d87`,
  `--deep #326e54`, on `--bg` and `--ink`. Delete the unused tokens rather than leaving
  them. This overrides the palette table in `CLAUDE.md` (do not edit that file; the
  orchestrator will). Evidence: a test that walks every built page and every canvas frame
  and fails on any pixel or computed colour whose hue is outside the green-teal band
  (allowing neutrals), plus a grep of the source for the removed hex values.
- **AC-29 not splotchy (amends AC-19 to AC-21).** Round 2 ran the automaton on a 20-28 cell
  grid, then upscaled and blurred it into big soft blobs. Remove that. The automaton now
  runs at display-cell resolution, one automaton cell per drawn square, with no blur and no
  upscale, so what is on screen is the actual structure of the simulation: gliders, still
  lifes, oscillators, fronts, fine filigree. Live cells are solid emerald squares. A cell
  that dies leaves a trail that thins out through the Bayer dither over a second or two
  (teal, then deep, then gone), which is where the halftone texture comes from. Overall it
  should read as fine, crisp and sparse: a living texture, not coloured clouds. Keep at
  least 60% of the pane pure `--bg`, keep activity from clumping into filled regions, and
  keep it quiet enough that the wireframe is plainly the subject. Re-check the cost limit
  of AC-22 at the larger grid (use typed arrays; a worker is allowed if needed).
- **AC-30:** remove the `smooth` and `flow` modes and their code. One simulation.
- **AC-31:** no simulation cell may draw outside the art panel's rounded bounds (round 2
  had stray cells past the left and right edges on the home page).
- Leave everything else from round 2 as it is: timelines, the 50/50 split, the locked blog
  shell.

Report as round 3.

## Amendment 4 (2026-11-16, from the owner)

No test suite, Lighthouse, screenshots or evidence table for this round or later ones: make
the change, confirm `pnpm build` passes and the dev server serves, add two lines to the
report, commit, push.

- **AC-32:** the life simulation gains two colours from the beetle: a small amount of
  blue-leaning teal `--aqua #58b3b3` and a metallic blue `--blue #4a86c8`. Simulation only;
  the rest of the site stays emerald, teal and deep. Mostly green still: roughly one cell
  in ten aqua and one in ten blue, assigned so colour sits in coherent structures (for
  example by a cell's age or by the region it was seeded in), not as per-cell confetti.
  Trails keep fading through the dither in the cell's own hue.
- **AC-33:** one step more colour on screen: raise how often coloured cells appear by a
  single notch (pane about 85% black, from about 92%), through slightly longer trails or
  slightly more seeding. Not more than that.

## Amendment 5 (2026-11-16, from the owner)

The owner's words: "the colors look flat and non-metallic, can you add packages and edit as
needed to get that metallic look within pixel." Same light process as amendment 4: no test
suite, build and serve only.

- **AC-34 metallic cells.** The simulation's cells must read as beetle shell, not flat
  paint, while staying crisp square pixels on the same grid. The rose chafer's colour is
  structural: a dark base with a bright, narrow, coloured specular that shifts hue with
  angle (green toward gold-less teal and blue here). Get that with a fragment shader over
  the cell grid (WebGL; a small helper such as `ogl`, `twgl.js` or `regl` is welcome, or
  raw WebGL):
  - Within each cell: a tiny bevel, a bright edge or corner highlight and a darker
    opposite edge, so a single cell looks like a polished tile. Keep it readable at 6px:
    two or three tones per cell, hard steps, no soft blur.
  - Across cells: one shared light. A broad specular band that drifts slowly across the
    pane, so neighbouring cells catch it in sequence and a mass of cells looks like one
    curved lacquered surface. Outside the band cells are dark and saturated; inside it
    they go bright and slightly desaturated toward white-green.
  - Iridescence: hue shifts a few degrees with position relative to the light (emerald
    toward aqua toward blue), on top of the per-region colours from AC-32. Greens and
    blues only; no yellow, gold or orange even in highlights.
  - Trails keep thinning through the Bayer dither and get the same shading, dimmer.
  - Contrast is what sells metal: deep darks next to small hot highlights. Do not just
    add a gradient or raise brightness.
- Keep the manners from AC-22 (slow simulation steps, pauses when unseen, one still frame
  under reduced motion; the light may animate at frame rate only while visible), a canvas
  2D fallback to the current flat look if WebGL is unavailable, and the wireframe readable
  on top.
- Look at it at 100% and at 300% zoom next to a photo-like mental picture of the beetle
  before handing back, and say plainly whether it reads as metal.

## Amendment 6 (2026-11-16, from the owner)

The owner's words: "can you make the colored bits on the markdown rendering (bold / link
underline / footnote), can you make them metallic in the same way?" Light process: build
and serve only, no test suite.

- **AC-35 metallic markdown accents.** Bold text, link underlines, footnote reference
  marks and back-arrows, and the other coloured markdown accents (list bullets, the
  footnote target highlight, blockquote rule) get the same beetle-shell treatment as the
  simulation cells: a dark saturated green base, a narrow bright specular that drifts
  across slowly, and a slight hue slide from emerald through aqua to blue around the
  highlight. Greens and blues only, highlight toward white-green, nothing warm.
  - Do it in CSS where possible (gradient with `background-clip: text` for glyphs,
    gradient `background-image` for underlines and rules), with hard-stepped colour stops
    so it matches the pixel look rather than a soft chrome gradient.
  - The sheen is shared: accents on the same page catch the light in sequence by
    position (for example a fixed-attachment or position-offset gradient), not each
    element looping on its own in unison. Slow: one pass every 12-20s. If it can be kept
    in step with the simulation's specular band cheaply, do that; otherwise match its
    period.
  - Text must stay easy to read: the darkest stop of bold text keeps at least 4.5:1
    contrast on `--bg`, weight and letterforms unchanged, no glow, no shadow, no shimmer
    fast enough to notice while reading.
  - Text selection, copy, and forced-colors mode still work; under
    `prefers-reduced-motion` the gradient is static.
  - Apply inside `Prose` (posts and `/blocks`). The home page text and timelines stay as
    they are unless a timeline accent already uses the emerald token, in which case give
    the current-step node the same treatment.
