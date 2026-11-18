# Portfolio

Personal portfolio and blog for Ty Kirchmann. Static Astro 7 site, dark. Every page has a
Game of Life simulation pane drawn as metallic pixel cells.

## Layout

- `src/` - Astro site: layouts, UI blocks, styles, content.
- `src/content/site.yaml` - home page content: name, role, `experiences`, `companies`, `links`.
  Each experience and company has a `body` that shows in the hover panel.
- `src/content/blog/<slug>/index.md` - one folder per post, images beside it.
- `src/components/Dither.astro`, `src/lib/dither-sim.ts`, `src/lib/metal.ts` - the life
  simulation and its WebGL metallic renderer. `src/lib/carve.ts` clears the room for the
  hover text panel; `src/lib/tools.ts` is the paint tools (brush, gravity, explosion, reset).
- `art/` - Blender pipeline that renders wireframe loops. `art/subjects/<slug>.py` is one subject.
- `public/art/<slug>/` - rendered loops, committed. Written only by the art pipeline.
- `.orchestration/` - designs and reports for agent-built features.

## Commands

```bash
pnpm install
pnpm dev            # dev server on http://localhost:4321
pnpm build          # static build to dist/
pnpm new-post "Title"   # scaffold a blog post folder
pnpm art <slug>     # render art/subjects/<slug>.py to public/art/<slug>/ (5 parallel workers)
pnpm art <slug> --resume   # continue a stopped render
```

- Restart `pnpm dev` after changing `src/content.config.ts`; the dev content store can come
  back empty and blog posts then 404.
- `pnpm test` and `pnpm lighthouse` exist but the suite is stale after later rounds. The
  owner wants speed over proof: build, serve, look at it. Do not run or extend the suite
  unless asked.
- Blender is at `/Applications/Blender.app/Contents/MacOS/Blender` (5.2 LTS). The Homebrew
  `ffmpeg` on this machine is broken (missing libbluray); do not depend on it.

## House rules

- The owner writes the content. Agents write placeholder copy only, plain and short.
- No monospace type anywhere except inside code blocks.
- No taglines, no decorative subtitles, no filler copy.
- Icons are Pixelarticons, drawn at their native 24px on whole device pixels. All icon
  circles are the same faint emerald ring; there is no "current" marker.
- Colour is greens only across the site. The simulation also uses an aqua and a metallic
  blue. No yellow, gold, orange or copper anywhere.
- Coloured markdown accents (bold, link underlines, footnote marks) carry a slow metallic
  sheen in step with the simulation's light.
- On desktop, blog pages lock the page and scroll only the text pane.

## Archived, kept for reuse

The wireframe ball art is not reachable from the site. It is all still here: the loops in
`public/art/` (gyroscope, knot, spikeball, spikeball-life, waveball, waveball-life), the
player and switcher (`Art.astro`, `ArtSet.astro`, including the stacked-alpha player for
opaque pieces), and `art:` support in `site.yaml` and post frontmatter. `/blocks` shows
them, in `pnpm dev` only: the page lives in `src/dev/` and is left out of production builds. `spikeball-zoom` is unfinished: 191 of 480 frames in the ignored cache.

Art rules when it is used again: one fixed isometric camera for every subject (zoom and
pan allowed, angles fixed), light lines on black for screen blending, colour only in the
`-life` pieces.

## Palette

| Token | Hex | Use |
| --- | --- | --- |
| `--color-bg` | `#0a0c0b` | background |
| `--color-ink` | `#e9ece8` | body text |
| `--color-emerald` | `#76c8a5` | accents, icons, live cells |
| `--color-teal` | `#579d87` | secondary accent, trails |
| `--color-deep` | `#326e54` | fading trails |
| aqua | `#58b3b3` | simulation only |
| blue | `#4a86c8` | simulation only |

The greens were sampled from photos of the green rose chafer (Cetonia aurata).
