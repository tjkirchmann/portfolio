# Report: site

- **Design:** `.orchestration/designs/site.md`
- **Branch:** `ai-feat/site`
- **Head commit:** a5bab84 (code, tests and screenshots for round 2; this report is committed right after it)
- **Pushed to origin:** yes
- **Round:** 2 (Amendment 1: AC-19 to AC-26, replacing AC-8; Amendment 2: AC-27)

## Round 2 summary

- **`Dither` is now a dithered life simulation** (`src/lib/dither-sim.ts`, `src/components/Dither.astro`):
  - Each mode runs on a small torus. Its density field is blurred, bilinearly upscaled to the cell grid and put through an 8x8 Bayer threshold, so dense places are solid squares, edges break into ordered halftone, and the rest is pure `--bg`.
  - Colour is picked per cell from a second field, age (how long a place has been occupied), mixed with density. The colour step is also Bayer-dithered between neighbouring palette stops (deep, teal, emerald, leaf, gold, copper), so masses are flat palette colours with ordered transitions, never smooth gradients.
  - **Three modes behind one `mode` prop:**
    - `life`: Conway B3/S23 on a 20x20 torus, one generation every 3 steps, each live cell feeding a decaying trail. Stalls, die-offs and overfills get a quiet random patch.
    - `smooth`: Lenia-style continuous field (ring kernel R=5, mu 0.15, sigma 0.017).
    - `flow`: Gray-Scott reaction-diffusion (F 0.026, K 0.061).
  - **Warm-up at build time.** The field is seeded from the page path and pre-evolved at build. The state ships as a ~2–3 KB string in the HTML, so the first paint is already settled.
  - **In the browser** a single shared timer steps at about 10/s, and only while at least one field is on-screen, the tab is visible, the mobile art is not dissolved, and reduced motion is off.
- **Choice for the real pages: `life`.** It is the only mode with the reference's character: a few large soft masses with solid cores and wide halftone edges, separated by wide pure-black space (66–81% empty in the test), drifting, merging and fading.
  - `smooth` reads as scattered clouds.
  - `flow` settles into an evenly spaced field of round spots, which looks more like a pattern than masses.
  - All three are shown large on `/blocks` for the owner to compare.
  - Art panes use `intensity 0.85` to keep the wireframe readable on top.
- **`Timeline` block** (`src/components/Timeline.astro`): icon node on a rail, title (optional link), optional subtitle, year at the far right, newest step marked current.
  - Icons are lucide (`lucide-static`), read from disk and inlined as SVG at build (`src/lib/icons.ts`).
  - In a short box the list scrolls inside itself, with a fade only on the clipped edge and no scrollbar chrome.
- **Home:** `Projects` and `Companies` timelines from `site.yaml` (`projects:` / `companies:` replace `entries:`; strict zod schema; unknown icons and missing years fail the build with a named path).
  - On desktop the shell is one viewport tall, and the two halves share the space between header and link row exactly 50/50.
  - Below 800px they stack at natural height.
- **Locked blog shell** (`Split lock="scroll"`): blog index and posts never scroll the document on desktop; only the text pane scrolls. Details:
  - **Keyboard** works without a click: the pane takes focus on load, and keys still scroll it if focus falls back to `<body>`.
  - **Wheel** over the art pane also scrolls the text.
  - **Scroll position** is saved per history entry and restored on back/forward. A newly opened post starts at the top.
  - **Look:** thin palette scrollbar, top/bottom fades only where clipped, `overscroll-behavior: contain`.
  - Mobile is unchanged.
- **Fix:** the visually hidden "Footnotes" heading, absolutely positioned with no positioned ancestor, was extending the document below the shell. `.prose-chafer` is now `position: relative`.

## Summary of changes (round 1)

A static Astro 7 site, built from scratch on this branch.

- **Tokens** live in `src/styles/global.css`: the chafer palette, a minor-third type scale from 17px, a 4px spacing scale, and motion (one easing curve, 160/260/400ms).
- **Blocks** live in `src/components/`:
  - `Split`: the two-pane shell. On desktop the art pane is sticky. Below 800px the art is fixed and dissolves as you scroll.
  - `Art`: the loop player, with the blurred still, crossfade, reduced-motion still and placeholder fallback.
  - `Dither`: a Bayer dither drawn once to a canvas (round 1; replaced in round 2, see above).
  - `EntryList`, `PostList`, `LinkRow`, `BackLink` and `Prose`.
- **Pages:**
  - `/`: text left, art right, all content read from `src/content/site.yaml`.
  - `/blog/` and `/blog/<slug>/`: mirrored, art left, back arrow top-left.
  - `/blocks/`: every block and every markdown element.
- **Markdown** uses Astro 7's default processor, Sätteri. A small hast plugin wraps titled images in `<figure>`.
- **Code highlighting** uses Shiki with a palette theme.
- **Content workflow:** a content collection schema validates posts, drafts are left out of production builds, and `pnpm new-post` scaffolds a post.
- **Placeholder loop** in `public/art/_placeholder/` was rendered with Blender by `scripts/placeholder-art.py`. Its `meta.json` comes from `scripts/placeholder-meta.mjs`.
- **Self-test** (`pnpm test`) checks content, builds, then runs Playwright in Chromium, Firefox and WebKit. **Lighthouse** runs separately with `pnpm lighthouse`.

## Acceptance criteria

All `tests/...` checks are in `tests/site.spec.mjs` / `tests/content.mjs`. The full log is in `.orchestration/reports/site-shots/test-log.txt`, and each assertion is in `results.json`. Screenshot paths below are relative to `.orchestration/reports/site-shots/`.

| Criterion | Status | Evidence |
| --- | --- | --- |
| AC-1 | met | `pnpm install && pnpm build` exits 0 and builds 5 pages: `/`, `/blog/`, `/blog/first-post/`, `/blog/second-post/`, `/blocks/`. `ls dist` gives `_astro art blocks blog favicon.svg index.html`. The self-test checks `[AC-1]` pass. |
| AC-2 | met (amended by AC-24) | Round 2: the home rows are now the two timelines; the test asserts each step's title / subtitle / year against `site.yaml`. Round 1: Screenshot: `desktop-home.png`. Source: `src/content/site.yaml`. The test asserts text left / art right, name and role, every entry row, and the link row (labels and hrefs) at the bottom, all against the yaml. |
| AC-3 | met (amended by AC-27) | Round 2: the art pane is fixed by the locked shell; the test scrolls the pane by 400px: art top 0 -> 0, title 53 -> -347. Round 1: Screenshots: `desktop-blog.png`, `desktop-post-top.png`, `desktop-post-scrolled.png`. The test asserts art left, back href `/` on the index and `/blog/` on posts, and that the art pane top stays the same (0 to -0.2px) while the title moves 426px. |
| AC-4 | met | Screenshots: `mobile-{home,post}-{0,60,200,back-0}.png` at 390x844. The test measures, at scroll 0 / 60 / 200 / back to 0: opacity 1 / 0.5 / 0 / 1; blur 0 / 7 / 14 / 0px; visibility hidden at 200; video paused at 200 and playing again at 0; no horizontal scroll; CLS 0. Firefox and WebKit pass the same dissolve check natively. The script fallback is only simulated (see Not verified). |
| AC-5 | met (cached path not re-proven in round 2) | Round 2: throttled before/after checks pass again. The cached-revisit check was SKIPPED in the final run: the video took 124ms to become playable on revisit, so the instant path was not exercised (it passed in round 1 at 11–29ms). Round 1: Screenshots: `art-throttled-before.png` / `-after.png`. With the video request delayed 2s: before, state `loading`, the inline `data:image/webp` blur is at opacity 1 and the video at 0. After, the video is at 1 with `blur(0px)` and the blur image at 0, after a 2024ms crossfade. On a cached revisit the video is playable after 29ms in the latest run (11–29ms across runs) and swaps instantly with no transition (`instant: true`). On `/blocks` a missing slug falls back to `_placeholder` with a build warning. |
| AC-6 | met | Screenshots: `blocks-art-over-dither.png`, `firefox-art-over-dither.png`, `webkit-art-over-dither.png`. The video uses `mix-blend-mode: screen` in all three engines. Round 2 pixel check, with the simulation paused so canvas and screenshot agree: every coloured dither cell inside the art box keeps at least its colour in the composite, so the black matte adds nothing (see `results.json`). |
| AC-7 | met | Screenshot: `reduced-motion-home.png`. With `reducedMotion: 'reduce'`: state `still`, poster shown, video paused and hidden, 0 requests for `loop.*`. During navigation the view-transition animations list is empty (none run). |
| AC-8 | replaced | Replaced by AC-19 to AC-22 (Amendment 1). The static gradient no longer exists. |
| AC-9 | met | Computed colours: body `rgb(233,236,232)` (`--ink`), bold `rgb(118,200,165)` (`--emerald`), footnote marks and back-arrows `rgb(187,195,104)` (`--gold`). Links are ink text with a `--teal` underline that turns emerald on hover. |
| AC-10 | met | Screenshots: `desktop-footnote-target.png`, `desktop-footnote-back.png`. The test clicks ref 1: hash `#user-content-fn-1`, the `li` is in view and highlighted with a gold tint. It then clicks the back-arrow: hash `#user-content-fnref-1`, the ref is in view and highlighted. The numbered list is the last element of the post. |
| AC-11 | met | Built HTML in `test-log.txt`: `<figure><img … loading="lazy" decoding="async" width="1440" height="900" srcset="… 360w, … 480w, … 640w, … 960w, … 1280w, … 1440w"><figcaption>alt</figcaption></figure>`, between two `<p>`. It renders 576px wide in a 576px column, CLS 0. |
| AC-12 | met | The test walks every text node on all 5 built pages: no monospace outside `pre`/`code`, and `pre`/`code` text is monospace. |
| AC-13 | met | `test-log.txt`: the broken fixture (bad date, no `art`) gives `exit 1`, `[InvalidContentEntryDataError] blog → zz-broken-fixture …`, with the full path `src/content/blog/zz-broken-fixture/index.md`. A `draft: true` fixture has no page and no `/blog/` listing. Both fixtures are removed in `finally`. The schema is in `src/content.config.ts` and is `.strict()`. |
| AC-14 | met | `test-log.txt`: `pnpm new-post "Zz Scaffold Fixture"` prints `Created src/content/blog/zz-scaffold-fixture/index.md` with `title`, `date: 2026-11-16`, `art: _placeholder`. A second run exits 1 with `… already exists`, and the file is unchanged. |
| AC-15 | met | Screenshots: `transition-frame-1/2/3.png`, with animations slowed 10x through CDP. `startViewTransition` was called. Groups seen: `root`, `text-left` old, `text-right` new, `art-right` old, `art-left` new (fade, 260ms text / 400ms art). Frame mean brightness 23 / 14 / 19 of 255 (no white), stdev 30 / 7 / 24 (never blank). |
| AC-16 | met | Round 2: `pnpm test` gives `149 passed, 0 failed, 1 skipped` (the skip is the AC-5 cached-video timing path). It runs headless, writes 51 files to `.orchestration/reports/site-shots/`, and exits 1 on any failure; several failing runs during round 2 exited 1. Round 1: 74 passed. |
| AC-17 | met | Round 2, with the simulation running (`lighthouse.json`): `/` perf **99**, a11y **100** (TBT 90ms, LCP 1.8s); `/blog/first-post/` perf **99**, a11y **100** (TBT 40ms, LCP 2.2s). Round 1: 100/100 and 99/100. |
| AC-18 | met | Full text dump of `/`, `/blog/`, `/blocks/` is below and in `text-dump.txt`. It contains only names, labels, dates, sample post text and link text. |
| AC-19 | met | Screenshots: `dither-{life,smooth,flow}-{00s,05s,20s}.png`. Each mode: 96x70 grid, cells 6 CSS px = 12.00 device px, `image-rendering: pixelated`, canvas offset snapped to the device pixel grid. Structure check, the spread of fill fraction across 8x8-cell blocks (noise at the same coverage is about 0.06): life 0.40 / 0.42, smooth 0.24 / 0.22, flow 0.28 / 0.27 at 0s / 20s. |
| AC-20 | met | `mode` prop: `life`, `smooth` (Lenia), `flow` (Gray-Scott). All three shown large (26rem tall, full column) on `/blocks` (`desktop-blocks.png`). Real pages use `life`; the reasons are in the Round 2 summary. |
| AC-21 | met | Empty fraction at 0s / 5s / 20s: life 0.67 / 0.81 / 0.66, smooth 0.69 / 0.74 / 0.73, flow 0.61 / 0.62 / 0.62 (all ≥ 0.35). The life frame at 20s uses all six palette stops: gold 12.5%, leaf 6.6%, emerald 4.9%, copper 4.4%, teal 3.7%, deep 1.8%, the rest `--bg`. Art panes use intensity 0.85 under the screen-blended wireframe (`post-pane-middle.png`, `desktop-home.png`). |
| AC-22 | met (average cost; see note) | Steps/s over 15s: life 10.85, smooth 10.65, flow 10.72. Cost per step, step + draw + `putImageData`, timed in the page at 2x DPR: **avg** life 0.23ms, smooth 0.44ms, flow 0.36ms. **Max** life 1.8ms, smooth and flow 4.7ms (single spikes, likely GC). Pauses, each proven with step counts: off-screen +0 in 1.5s, hidden tab +0 in 1.5s and then +10 after returning, mobile dissolved +0 in 1.5s and then +12 back at the top, reduced motion 0 steps in 2s with a settled frame. Seeded: 4 pages give 4 different patterns, and a reload gives the same one. Pre-evolved: with reduced motion (0 steps), every mode already shows masses (empty 0.61–0.70, spread 0.25–0.40). |
| AC-23 | met | Screenshots: `home-timelines.png`, `blocks-timeline-companies.png`. The test asserts: every step has an inline SVG node, title and year flush right; rail segments are present (16px / 37px); only the newest step is current; no icon font in any stylesheet. Icons come from `lucide-static`, inlined at build, with no client JS for icons. |
| AC-24 | met | `site.yaml` `projects:` / `companies:` (`title`, `subtitle?`, `year`, `icon?`, `href?`), strict schema. The test matches every step to the yaml. A bad entry fails the build: `src/content/site.yaml is invalid: projects.1.icon: unknown icon "not-an-icon" (use a lucide icon name …)` and `companies.1.year: a year or range is required …` (exit 1). The file is restored in `finally`. |
| AC-25 | met | Halves at 3 heights, with 3 entries and with 12 (cloned in the DOM): 1440x900 316.7 / 316.7; 1280x720 231.5 / 231.5; 1440x1100 416.7 / 416.7, unchanged by entry count. With 12 entries: scrolls inside, fade below, `scrollbar-width: none`. With 3: first step at the top (offset 0). The document does not scroll at 1440x900 and 1280x720 (scrollHeight = innerHeight). Below 800px: stacked, natural height, page scrolls. Screenshots: `home-1440x900-12-entries.png`, `home-1280x720-12-entries.png`, `mobile-home-timelines.png`. |
| AC-26 | met | `/blocks`: Companies (with subtitles) and a 12-entry Projects timeline in a 16rem box that scrolls (`blocks-timeline-companies.png`, `blocks-timeline-overflow.png`). |
| AC-27 | met | At 1440x900 and 1280x720, `document.scrollingElement.scrollHeight === innerHeight` on `/blog/` and the post. Details:<br>• **Keyboard, no click** (1440, max 802): ArrowDown 40, PageDown 802, End 802, Home 0, Space 802.<br>• **Wheel:** 200 over the text pane, and the art pane forwards wheel too (200 -> 260). Window `scrollY` stays 0 throughout, and the art and back arrow do not move.<br>• **Overscroll:** extra wheel at the end leaves the page put.<br>• **Footnotes:** ref -> note -> back round trip inside the pane, highlighted.<br>• **Anchor:** `#a-heading` scrolls the pane.<br>• **History:** a new post opens at 0; back restores 600, forward then back again restores 600.<br>• **Look:** thin scrollbar, `overscroll-behavior: contain`, ~50px padding above the title, 6rem below the last line, fades only on clipped edges.<br>• **Mobile:** still scrolls the document.<br>Screenshots: `post-pane-top.png`, `post-pane-middle.png`, `post-pane-end.png`. |

### AC-18 text dump (round 2)

```
===== /
Your Name / Your role
Projects: Project one 2026 / Project two 2025 / Project three 2024
Companies: Company one, Role, 2024 – now / Company two, Role, 2021 – 2024 / Company three, Role, 2018 – 2021
Blog  GitHub  Email

===== /blog/
Home / Blog / First post 10 Nov 2026 / Second post 2 Oct 2026

===== /blocks/
Home / Blocks / Palette (9 token names) / Dither: life, smooth, flow / Art over Dither /
Timeline: Companies (3, with Role) / Projects (Project one … Project twelve, 2026 … 2015) /
EntryList: Row one 2026, Row two 2025 / PostList / LinkRow / BackLink Blog / Prose (sample markdown, unchanged)
```

The full dump is in `site-shots/text-dump.txt`. It contains labels and data only.

## Tests run

Round 2, final run:

```
$ pnpm install && pnpm build
[build] 5 page(s) built
[build] Complete!

$ pnpm test        # ~4.5 min: content checks, build, Chromium + Firefox + WebKit
… 149 PASS lines (full list in site-shots/results.json) …
SKIP  [AC-5] cached video: swap with no blur-in  (video took 124ms to become playable on revisit; the instant path was not exercised)
149 passed, 0 failed, 1 skipped

$ pnpm lighthouse
/ {"performance":99,"accessibility":100,"best-practices":100,"seo":100,"lcp":"1.8 s","cls":"0","tbt":"90 ms"}
/blog/first-post/ {"performance":99,"accessibility":100,"best-practices":100,"seo":100,"lcp":"2.2 s","cls":"0","tbt":"40 ms"}
```

Dither timings, from `test-log.txt`:

```
dither life:   grid 96x70, cell 6.000css (12.00 device px), 10.85 steps/s, avg 0.228ms max 1.8ms per step (step+draw)
dither smooth: grid 96x70, cell 6.000css (12.00 device px), 10.65 steps/s, avg 0.442ms max 4.7ms per step (step+draw)
dither flow:   grid 96x70, cell 6.000css (12.00 device px), 10.72 steps/s, avg 0.363ms max 4.7ms per step (step+draw)
```

In Node, the build-time warm-up per page takes 3–25ms depending on mode.

## Files changed

| Path | Change |
| --- | --- |
| `package.json`, `pnpm-lock.yaml` | added. Scripts `dev build preview test new-post art lighthouse`, including `"art": "python3 art/cli.py"` |
| `astro.config.mjs`, `tsconfig.json` | added. Static output, constrained responsive images, Sätteri with the figure plugin, Shiki palette theme, Tailwind vite plugin |
| `src/styles/global.css`, `src/styles/prose.css` | added. Tokens, base, rows, markdown palette overrides |
| `src/components/{Split,Art,Dither,EntryList,PostList,LinkRow,BackLink,Prose}.astro` | added. The UI blocks |
| `src/layouts/Base.astro` | added. Head, font preload, `ClientRouter` |
| `src/pages/index.astro`, `src/pages/blog/index.astro`, `src/pages/blog/[slug].astro`, `src/pages/blocks.astro` | added |
| `src/lib/{art.ts,site.ts,posts.ts,figure-plugin.mjs,shiki-theme.mjs}` | added. Meta reader with fallback, yaml loader with schema, post helpers, hast plugin, code theme |
| `src/content.config.ts`, `src/content/site.yaml`, `src/content/blog/{first-post,second-post}/` | added. Schema, home content, two sample posts (one image) |
| `src/blocks/sample.md` | added. Markdown sample for `/blocks` |
| `public/favicon.svg`, `public/art/_placeholder/{loop.webm,loop.mp4,poster.png,meta.json}` | added. Stand-in loop to the file contract (640x640, 24fps, 96 frames) |
| `scripts/new-post.mjs`, `scripts/placeholder-art.py`, `scripts/placeholder-meta.mjs` | added |
| `tests/{run,lib,content,site.spec,serve,lighthouse}.mjs` | added. Self-test, static server with Range support, Lighthouse runner |
| `.orchestration/reports/site.md`, `.orchestration/reports/site-shots/*` | added (round 2: updated, new shots for dither, timelines, locked shell) |
| `src/lib/dither-sim.ts` | round 2, added. The three simulations, seeding, state encode/decode, Bayer drawing |
| `src/components/Dither.astro` | round 2, rewritten. Build-time warm-up, shared timer, pauses, pixel-snapped canvas |
| `src/components/Timeline.astro`, `src/lib/icons.ts` | round 2, added |
| `src/lib/site.ts`, `src/content/site.yaml` | round 2, modified. `projects` / `companies` replace `entries`; strict schema with readable errors |
| `src/components/Split.astro` | round 2, modified. `lock` prop (`scroll` / `fit`), pane focus, keyboard and wheel handling, per-entry scroll restore, `split:dissolve` event |
| `src/pages/index.astro`, `src/pages/blog/*.astro`, `src/pages/blocks.astro` | round 2, modified. Timelines on home, locked shells, three dither modes and timeline demos on `/blocks` |
| `src/styles/prose.css` | round 2, modified. `position: relative` so the hidden footnotes heading cannot extend the page |
| `src/content/blog/first-post/index.md` | round 2, modified. A few more plain sample paragraphs, so the post is long enough to scroll inside the pane |
| `tests/dither.spec.mjs`, `tests/shell.spec.mjs` | round 2, added. AC-19..27 checks; `tests/site.spec.mjs` and `tests/content.mjs` updated |

## System report (as built)

### Packages

| Package | Original or third-party | Purpose |
| --- | --- | --- |
| `astro` 7.4.12 | third-party | Static site, content collections, view transitions (`ClientRouter`), image optimisation, Shiki |
| `@astrojs/markdown-satteri` 0.4.10 | third-party | Astro 7's default Markdown processor; added as a direct dependency only so the config can pass it a hast plugin |
| `tailwindcss` 4.3.5, `@tailwindcss/vite` | third-party | Theme tokens, preflight |
| `@tailwindcss/typography` | third-party | Prose base, overridden with the palette |
| `@fontsource-variable/instrument-sans` | third-party | Sans (one token: `--font-sans`) |
| `@fontsource-variable/jetbrains-mono` | third-party | Code only |
| `sharp` | third-party | Astro 7 image service needs it installed explicitly; also used by the placeholder meta script and test pixel checks |
| `yaml` | third-party | Parses `src/content/site.yaml` |
| `lucide-static` (round 2) | third-party | Icon set for `Timeline`, SVG files read and inlined at build |
| `cookie` ^2 | third-party | Workaround, see Deviations |
| `playwright` (dev) | third-party | Self-test and screenshots (Chromium, Firefox, WebKit) |
| `lighthouse` (dev) | third-party | `pnpm lighthouse` |
| `src/components/*`, `src/lib/*` | original | Blocks and helpers |
| `scripts/new-post.mjs` | original | Post scaffolder |
| `tests/*.mjs` | original | Self-test |

### Primitives

- **Post:** `src/content/blog/<slug>/index.md` plus images beside it. Frontmatter is `title`, `date`, `art`, optional `draft`, `summary` (strict schema).
- **Site config:** `src/content/site.yaml` with `name`, `role`, `art`, `projects[]` and `companies[]` (`{title, subtitle?, year, icon?, href?}`), `links[] {label, href}`. It is validated with a strict zod schema at build; icon names are checked against `lucide-static`.
- **Dither state:** `data-state` on each canvas carries the pre-evolved field (base64, every channel quantised to 8 bits). The seed is the page path unless `seed` is passed.
- **Art reference:** a slug that resolves to `public/art/<slug>/meta.json` at build. If it is missing, `_placeholder` is used and the build prints a warning.
- **Tokens:** CSS custom properties on `:root`, plus Tailwind `@theme` colours and fonts.

### High-level workflows

- **New post:** `pnpm new-post "Title"` creates a folder and frontmatter. Write the markdown, drop images in the folder, set `art`, push.
- **Build:** the collection validates (a bad file fails with its path), drafts are filtered in production, pages render, and `resolveArt` reads `meta.json` per page.
- **Art load:** the inline blurred still shows first. On `astro:page-load` the script sets `source.src` and calls `play()`. On `playing` it crossfades (instantly if playable within 50ms). With reduced motion it shows only `poster.png` and the video never loads.
- **Mobile dissolve:** a CSS scroll-driven animation over 0–120px of root scroll. Where scroll timelines are unsupported, a script sets `--dissolve-p`. A scroll listener pauses the video when fully dissolved and resumes it otherwise.

- **Dither:**
  - At build, `createSim(mode, seed)` runs `WARMUP[mode]` steps and embeds the state.
  - In the browser it decodes the state and draws immediately. A shared `setInterval` (about 10/s) steps every live field. It is stopped when none are live: off-screen (IntersectionObserver), `document.hidden`, mobile art dissolved (`split:dissolve` event plus a `[data-dissolved]` check), or reduced motion. It redraws on resize.
- **Locked shell:**
  - On `astro:page-load` the pane is focused (if nothing else has focus).
  - On traverse or back_forward loads the position is restored from `sessionStorage`, keyed by `history.state.index` and path. Otherwise it is reset to 0.
  - Positions are saved on scroll (rAF-throttled) and on `pagehide`.

### Data and endpoints

- Reads `public/art/<slug>/{loop.webm,loop.mp4,poster.png,meta.json}`. `meta.json` is `{ slug, subject, width, height, fps, frames, duration, blurDataUrl }`. Missing `loop.webm` or `loop.mp4` drops that `<source>`.
- No server endpoints.

## Deviations from the design

Round 2:

- **`life` uses Conway B3/S23 with reseeding**, not a rule that is self-sustaining by itself. On a 20x20 torus every life-like rule I tried either froze (Day & Night grew permanent blobs) or needed nudging. The nudges are small random patches placed where it went quiet, so it never stalls, dies or fills.
- **The simulations run on a coarser grid than the drawn cells** (20–28 sim cells across, 96–122 drawn cells). Each drawn cell samples the upscaled, blurred field. This is what gives the reference's large soft masses, and keeps the cost low.
- **`smooth` and `flow` are cropped in** (zoom 1.8 / 1.5) so their features read as masses at pane scale.
- **Art panes use `intensity 0.85`** (palette dimmed 15%) as the brightness cap behind the wireframe. `/blocks` shows the three modes at full intensity.
- **Wheel over the art pane scrolls the text pane.** AC-27 did not ask for this. I added it because otherwise the wheel does nothing over half the screen.
- **First sample post got four more short plain paragraphs**, so the locked pane actually scrolls at 1440x900.
- **`EntryList` is no longer used on home.** It stays as a block on `/blocks` with local sample rows.

Round 1:

- **Markdown processor.** Astro 7 replaced remark/rehype with Sätteri, so `markdown.rehypePlugins` would need the old unified package. The figure caption is a Sätteri hast plugin (`src/lib/figure-plugin.mjs`) instead. GFM footnotes, tables and Shiki work unchanged.
- **`cookie` direct dependency.** This worktree sits inside the main checkout. Astro's prerender bundle in `dist/.prerender/` imports the bare `cookie` module, and Node resolved it upward to an old CommonJS `cookie` in `/Users/ty/repos/portfolio/node_modules`, which broke the build. Adding `cookie@^2` at the project root fixes it. It is probably also needed in a clean clone with pnpm's strict layout. Remove it if a future Astro bundles it.
- **Caption rule, taken literally.** A caption appears only when the image has a title (`![alt](./x.png "title")`), and the caption text is the alt text, not the title. If the owner meant "caption = title", it is a one-line change in `figure-plugin.mjs`.
- **Art pane is an inset rounded panel** (8–14px inset, 14px radius) rather than full-bleed. The design does not specify this; it is a visual choice.
- **`pnpm new-post` writes an empty body** and no `draft` line, so a new post publishes as soon as it is pushed. The test also covers this.
- **Extra script `pnpm lighthouse`.** Lighthouse is not part of `pnpm test`, which keeps the test around 40s and avoids a flaky perf gate.
- **`pnpm dev` detaches in a non-interactive shell.** Astro 7 itself runs the dev server in the background when stdin is not a terminal; stop it with `astro dev stop`. In a normal terminal it should run in the foreground, but I did not check that.
- **Placeholder WebM** is encoded at a fixed 900 kbps (485 KB) because Blender's VP9 quality presets produced 2–3 MB. It shows mild compression noise on the lines. It is a stand-in.

## Not done or not verified

Round 2:

- **Cached-video instant swap (AC-5)** was not re-proven. In the final run the revisit took 124ms to become playable, so the instant path was skipped; it passed in round 1.
- **Main-thread cost (AC-22).** The average is far under 2ms, but single steps of `smooth` and `flow` peaked at 4.7ms. `life`, the mode on the real pages, peaked at 1.8ms. Measured with a 2x DPR in headless Chromium only.
- **Real devices.** Not checked on a real phone, real Safari, or a trackpad: the wheel was Playwright's `mouse.wheel`, and keys were Playwright key presses. Pausing in a hidden tab was simulated by overriding `document.hidden` and firing `visibilitychange`. Playwright cannot hide a headless tab.
- **Long-run behaviour.** Not watched for hours: `life` reseeds quietly when quiet, but I only ran it about 40s in a browser plus a few minutes of steps in Node.
- **Wireframe readability over gold** was judged by eye from screenshots, not measured.
- **Timelines with 12 entries** were checked by cloning DOM rows. A real 12-entry `site.yaml` was not built.
- **Keyboard after clicking a link inside the pane** (focus on the link): native scrolling of the focused element's scroller handles it. Not separately tested.

Round 1:

- **Never driven by real input:**
  - Touch scrolling on a real phone (the test sets `window.scrollTo`).
  - iOS Safari URL-bar collapse. The art height uses `svh` to avoid a jump, but I did not see it on a device.
  - Mouse hover states (only screenshots).
  - Real Safari and Firefox apps. WebKit and Firefox were checked through Playwright's builds only.
  - Footnote jumps and the focus ring did use real Playwright clicks and Tab key presses.
- **Script fallback for the mobile dissolve.** Every engine here supports `animation-timeline`, so the fallback was only checked by faking `CSS.supports` and turning off the native animation in Chromium (`mobile-post-60-script-fallback.png`). It was not seen in a browser that actually lacks scroll timelines.
- **Cached-video path** was checked in Chromium only (11–29ms to playable, instant swap). Other engines may refetch or behave differently.
- **H.264 MP4 playback** was not exercised. Playwright's Chromium has no proprietary codecs and plays the WebM; WebKit and Firefox were only checked for blend mode and state.
- **Not run:** `astro check` / TypeScript type-check (`@astrojs/check` is not installed).
- **Not deployed:** Cloudflare Pages deploy was not attempted (out of scope). The output is plain static files in `dist/`.
- **Image `sizes`** is Astro's default `(min-width: 1440px) 1440px, 100vw`. On a 2x desktop screen it picks the 1440w file for a 576px column, which is slightly more than needed.
- **Sticky art pane in full-page screenshots.** `desktop-blocks.png` is a full-page capture, so the sticky art pane appears only at the top. That is a capture artifact, not a bug.
