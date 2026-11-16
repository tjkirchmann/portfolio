# Portfolio

Personal portfolio and blog. Static Astro site, dark, with a looping wireframe animation per
page.

## Layout

- `src/` - Astro site: layouts, UI blocks, styles, content.
- `src/content/blog/<slug>/index.md` - one folder per post, images beside it.
- `src/content/site.yaml` - home page content (name, role, entries, links).
- `art/` - Blender pipeline that renders wireframe loops. `art/subjects/<slug>.py` is one subject.
- `public/art/<slug>/` - rendered loops, committed. Written only by the art pipeline.
- `.orchestration/` - designs and reports for agent-built features.

## Commands

```bash
pnpm install
pnpm dev            # dev server on http://localhost:4321
pnpm build          # static build to dist/
pnpm test           # site self-test (build, link and render checks, screenshots)
pnpm new-post "Title"   # scaffold a blog post folder
pnpm art <slug>     # render art/subjects/<slug>.py to public/art/<slug>/
```

Blender is at `/Applications/Blender.app/Contents/MacOS/Blender` (5.2 LTS). The Homebrew
`ffmpeg` on this machine is broken (missing libbluray); do not depend on it.

## House rules

- The owner writes the content. Agents write placeholder copy only, plain and short.
- No monospace type anywhere except inside code blocks.
- No taglines, no decorative subtitles, no filler copy.
- All wireframe art uses one fixed isometric camera. The subject moves, the camera never does.
- Wireframe art is light lines on transparency. Colour lives in the dither gradients and in
  markdown accents (bold, links, footnote marks), never in the wireframe.

## Palette

Sampled from photos of the green rose chafer (Cetonia aurata).

| Token | Hex | From |
| --- | --- | --- |
| `--bg` | `#0a0c0b` | near-black |
| `--ink` | `#e9ece8` | body text |
| `--emerald` | `#76c8a5` | elytra highlight |
| `--teal` | `#579d87` | elytra mid |
| `--deep` | `#326e54` | elytra shadow |
| `--leaf` | `#73984f` | elytra, warm light |
| `--gold` | `#bbc368` | pronotum highlight |
| `--copper` | `#9f814e` | elytra seam |
| `--bronze` | `#85692c` | seam shadow |
