# Report: site

- **Design:** `.orchestration/designs/site.md`
- **Branch:** `ai-feat/site`
- **Head commit:** the commit that adds this report (`git log -1 ai-feat/site`)
- **Pushed to origin:** yes
- **Round:** 1

## Summary of changes

A static Astro 7 site, built from scratch on this branch.

- **Tokens** live in `src/styles/global.css`: the chafer palette, a minor-third type scale from 17px, a 4px spacing scale, and motion (one easing curve, 160/260/400ms).
- **Blocks** live in `src/components/`:
  - `Split`: the two-pane shell. On desktop the art pane is sticky. Below 800px the art is fixed and dissolves as you scroll.
  - `Art`: the loop player, with the blurred still, crossfade, reduced-motion still and placeholder fallback.
  - `Dither`: a Bayer dither drawn once to a canvas.
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
| AC-2 | met | Screenshot: `desktop-home.png`. Source: `src/content/site.yaml`. The test asserts text left / art right, name and role, every entry row, and the link row (labels and hrefs) at the bottom, all against the yaml. |
| AC-3 | met | Screenshots: `desktop-blog.png`, `desktop-post-top.png`, `desktop-post-scrolled.png`. The test asserts art left, back href `/` on the index and `/blog/` on posts, and that the art pane top stays the same (0 to -0.2px) while the title moves 426px. |
| AC-4 | met | Screenshots: `mobile-{home,post}-{0,60,200,back-0}.png` at 390x844. The test measures, at scroll 0 / 60 / 200 / back to 0: opacity 1 / 0.5 / 0 / 1; blur 0 / 7 / 14 / 0px; visibility hidden at 200; video paused at 200 and playing again at 0; no horizontal scroll; CLS 0. Firefox and WebKit pass the same dissolve check natively. The script fallback is only simulated (see Not verified). |
| AC-5 | met | Screenshots: `art-throttled-before.png` / `-after.png`. With the video request delayed 2s: before, state `loading`, the inline `data:image/webp` blur is at opacity 1 and the video at 0. After, the video is at 1 with `blur(0px)` and the blur image at 0, after a 2024ms crossfade. On a cached revisit the video is playable after 29ms in the latest run (11–29ms across runs) and swaps instantly with no transition (`instant: true`). On `/blocks` a missing slug falls back to `_placeholder` with a build warning. |
| AC-6 | met | Screenshots: `blocks-art-over-dither.png`, `firefox-art-over-dither.png`, `webkit-art-over-dither.png`. The video uses `mix-blend-mode: screen` in all three engines. Pixel check: the mean green inside the art box's top band is 167, so the dither shows through the black matte. |
| AC-7 | met | Screenshot: `reduced-motion-home.png`. With `reducedMotion: 'reduce'`: state `still`, poster shown, video paused and hidden, 0 requests for `loop.*`. During navigation the view-transition animations list is empty (none run). |
| AC-8 | met | Screenshot: `desktop-home.png`. The canvas is 1466x1744 for a 732.8x872 box at 2x DPR, with 6 colours sampled. 0 `requestAnimationFrame` calls in 1.2s idle; it redraws only on resize (debounced `ResizeObserver`). Used on the home, blog index, post and `/blocks` art panes, and as 3 variants on `/blocks`. |
| AC-9 | met | Computed colours: body `rgb(233,236,232)` (`--ink`), bold `rgb(118,200,165)` (`--emerald`), footnote marks and back-arrows `rgb(187,195,104)` (`--gold`). Links are ink text with a `--teal` underline that turns emerald on hover. |
| AC-10 | met | Screenshots: `desktop-footnote-target.png`, `desktop-footnote-back.png`. The test clicks ref 1: hash `#user-content-fn-1`, the `li` is in view and highlighted with a gold tint. It then clicks the back-arrow: hash `#user-content-fnref-1`, the ref is in view and highlighted. The numbered list is the last element of the post. |
| AC-11 | met | Built HTML in `test-log.txt`: `<figure><img … loading="lazy" decoding="async" width="1440" height="900" srcset="… 360w, … 480w, … 640w, … 960w, … 1280w, … 1440w"><figcaption>alt</figcaption></figure>`, between two `<p>`. It renders 576px wide in a 576px column, CLS 0. |
| AC-12 | met | The test walks every text node on all 5 built pages: no monospace outside `pre`/`code`, and `pre`/`code` text is monospace. |
| AC-13 | met | `test-log.txt`: the broken fixture (bad date, no `art`) gives `exit 1`, `[InvalidContentEntryDataError] blog → zz-broken-fixture …`, with the full path `src/content/blog/zz-broken-fixture/index.md`. A `draft: true` fixture has no page and no `/blog/` listing. Both fixtures are removed in `finally`. The schema is in `src/content.config.ts` and is `.strict()`. |
| AC-14 | met | `test-log.txt`: `pnpm new-post "Zz Scaffold Fixture"` prints `Created src/content/blog/zz-scaffold-fixture/index.md` with `title`, `date: 2026-11-16`, `art: _placeholder`. A second run exits 1 with `… already exists`, and the file is unchanged. |
| AC-15 | met | Screenshots: `transition-frame-1/2/3.png`, with animations slowed 10x through CDP. `startViewTransition` was called. Groups seen: `root`, `text-left` old, `text-right` new, `art-right` old, `art-left` new (fade, 260ms text / 400ms art). Frame mean brightness 23 / 14 / 19 of 255 (no white), stdev 30 / 7 / 24 (never blank). |
| AC-16 | met | `pnpm test` gives `74 passed, 0 failed, 0 skipped`. It runs headless, writes 30 files to `.orchestration/reports/site-shots/`, and exits 1 on any failed check (it did, earlier in development). |
| AC-17 | met (with variance) | Scores in `lighthouse.json` (`pnpm build && pnpm lighthouse`, mobile, local static server): `/` perf **100**, a11y **100**; `/blog/first-post/` perf **99**, a11y **100**. One earlier run gave `/` perf 81 (TBT 780ms) while other agents were rendering in Blender; three later runs gave 99–100. |
| AC-18 | met | Full text dump of `/`, `/blog/`, `/blocks/` is below and in `text-dump.txt`. It contains only names, labels, dates, sample post text and link text. |

### AC-18 text dump

```
===== /
Your Name
Your role
Project one 2026 / Project two 2025 / Project three 2024
Blog  GitHub  Email

===== /blog/
Home
Blog
First post 10 Nov 2026 / Second post 2 Oct 2026

===== /blocks/
Home / Blocks / Palette bg ink emerald teal deep leaf gold copper bronze / Dither / Art over Dither /
EntryList (rows) / PostList (rows) / LinkRow Blog GitHub Email / BackLink Blog / Prose
Heading two / Heading three / Body text with bold, italic, a link, inline code and a footnote.1 /
A wireframe sphere inside a ring / A blockquote. / Unordered item ×2 / Ordered item ×2 /
Column Value One 1 Two 2 / // A code block … / Footnotes (screen-reader-only heading) / A footnote with a back arrow. ↩
```

## Tests run

```
$ pnpm install
Done (pnpm v11.15.0)

$ pnpm build
[build] 5 page(s) built in ~0.8s
[build] Complete!

$ pnpm test
… 74 lines of PASS …
PASS  [AC-4] script fallback (simulated): 1 -> mid -> 0 (paused) -> 1 (playing)  (1 / 0.5 / 0 / 1)
PASS  [AC-4] firefox: dissolve (CSS) 1 -> mid -> 0 -> 1  (1 / 0.5 / 0 / 1)
PASS  [AC-6] webkit: art blends with mix-blend-mode screen
74 passed, 0 failed, 0 skipped

$ pnpm lighthouse
/ {"performance":100,"accessibility":100,"best-practices":100,"seo":100,"lcp":"1.4 s","cls":"0","tbt":"0 ms"}
/blog/first-post/ {"performance":99,"accessibility":100,"best-practices":100,"seo":100,"lcp":"2.0 s","cls":"0","tbt":"50 ms"}

$ pnpm dev    # non-interactive shell
Dev server running at http://localhost:4321   (curl /blog/first-post/ -> 200; stopped with `astro dev stop`)
```

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
| `.orchestration/reports/site.md`, `.orchestration/reports/site-shots/*` | added |

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
| `cookie` ^2 | third-party | Workaround, see Deviations |
| `playwright` (dev) | third-party | Self-test and screenshots (Chromium, Firefox, WebKit) |
| `lighthouse` (dev) | third-party | `pnpm lighthouse` |
| `src/components/*`, `src/lib/*` | original | Blocks and helpers |
| `scripts/new-post.mjs` | original | Post scaffolder |
| `tests/*.mjs` | original | Self-test |

### Primitives

- **Post:** `src/content/blog/<slug>/index.md` plus images beside it. Frontmatter is `title`, `date`, `art`, optional `draft`, `summary` (strict schema).
- **Site config:** `src/content/site.yaml` with `name`, `role`, `art`, `entries[] {label, detail?, href?}`, `links[] {label, href}`. It is validated with zod at build.
- **Art reference:** a slug that resolves to `public/art/<slug>/meta.json` at build. If it is missing, `_placeholder` is used and the build prints a warning.
- **Tokens:** CSS custom properties on `:root`, plus Tailwind `@theme` colours and fonts.

### High-level workflows

- **New post:** `pnpm new-post "Title"` creates a folder and frontmatter. Write the markdown, drop images in the folder, set `art`, push.
- **Build:** the collection validates (a bad file fails with its path), drafts are filtered in production, pages render, and `resolveArt` reads `meta.json` per page.
- **Art load:** the inline blurred still shows first. On `astro:page-load` the script sets `source.src` and calls `play()`. On `playing` it crossfades (instantly if playable within 50ms). With reduced motion it shows only `poster.png` and the video never loads.
- **Mobile dissolve:** a CSS scroll-driven animation over 0–120px of root scroll. Where scroll timelines are unsupported, a script sets `--dissolve-p`. A scroll listener pauses the video when fully dissolved and resumes it otherwise.

### Data and endpoints

- Reads `public/art/<slug>/{loop.webm,loop.mp4,poster.png,meta.json}`. `meta.json` is `{ slug, subject, width, height, fps, frames, duration, blurDataUrl }`. Missing `loop.webm` or `loop.mp4` drops that `<source>`.
- No server endpoints.

## Deviations from the design

- **Markdown processor.** Astro 7 replaced remark/rehype with Sätteri, so `markdown.rehypePlugins` would need the old unified package. The figure caption is a Sätteri hast plugin (`src/lib/figure-plugin.mjs`) instead. GFM footnotes, tables and Shiki work unchanged.
- **`cookie` direct dependency.** This worktree sits inside the main checkout. Astro's prerender bundle in `dist/.prerender/` imports the bare `cookie` module, and Node resolved it upward to an old CommonJS `cookie` in `/Users/ty/repos/portfolio/node_modules`, which broke the build. Adding `cookie@^2` at the project root fixes it. It is probably also needed in a clean clone with pnpm's strict layout. Remove it if a future Astro bundles it.
- **Caption rule, taken literally.** A caption appears only when the image has a title (`![alt](./x.png "title")`), and the caption text is the alt text, not the title. If the owner meant "caption = title", it is a one-line change in `figure-plugin.mjs`.
- **Art pane is an inset rounded panel** (8–14px inset, 14px radius) rather than full-bleed. The design does not specify this; it is a visual choice.
- **`pnpm new-post` writes an empty body** and no `draft` line, so a new post publishes as soon as it is pushed. The test also covers this.
- **Extra script `pnpm lighthouse`.** Lighthouse is not part of `pnpm test`, which keeps the test around 40s and avoids a flaky perf gate.
- **`pnpm dev` detaches in a non-interactive shell.** Astro 7 itself runs the dev server in the background when stdin is not a terminal; stop it with `astro dev stop`. In a normal terminal it should run in the foreground, but I did not check that.
- **Placeholder WebM** is encoded at a fixed 900 kbps (485 KB) because Blender's VP9 quality presets produced 2–3 MB. It shows mild compression noise on the lines. It is a stand-in.

## Not done or not verified

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
