// Generates public/lotus.svg: a light blue pixel-art lotus. Run: node scripts/gen-lotus.mjs
import { writeFileSync } from 'node:fs'

const W = 32
const H = 28
const OUT = '#17122e'
const BLUES = ['#eef9ff', '#c4e8fb', '#93cff2', '#64afdc', '#4789bd'] // light -> dark
const px = Array.from({ length: H }, () => Array(W).fill(null))

// A petal is a pointed lens: half-width w * sin(pi * u / L) along its axis.
// angle is degrees from straight up; the petal's base sits at (bx, by).
function petal({ angle, L, w, bx, by, tone }) {
  const a = (angle * Math.PI) / 180
  const ax = Math.sin(a)
  const ay = -Math.cos(a)
  const mask = Array.from({ length: H }, () => Array(W).fill(null))
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const dx = x + 0.5 - bx
      const dy = y + 0.5 - by
      const u = dx * ax + dy * ay
      const v = dx * -ay + dy * ax
      if (u < 0 || u > L) continue
      if (Math.abs(v) <= w * Math.sin((Math.PI * u) / L)) mask[y][x] = { u: u / L, v: v / w }
    }
  }
  const inside = (x, y) => y >= 0 && y < H && x >= 0 && x < W && mask[y][x]
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const m = mask[y][x]
      if (!m) continue
      const edge = !inside(x - 1, y) || !inside(x + 1, y) || !inside(x, y - 1) || !inside(x, y + 1)
      if (edge) {
        px[y][x] = OUT
        continue
      }
      // lighter toward the tip and the axis, darker toward the base and the edges
      const shade = tone + (1 - m.u) * 0.9 + Math.abs(m.v) * 1.3 + (angle < 0 ? 0.25 : 0)
      px[y][x] = BLUES[Math.min(BLUES.length - 1, Math.max(0, Math.round(shade - 0.6)))]
    }
  }
}

// water / pad under the flower
function pad() {
  const cx = 15.5
  const cy = 25
  for (let y = 22; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const d = ((x + 0.5 - cx) / 14.5) ** 2 + ((y + 0.5 - cy) / 2.9) ** 2
      if (d <= 1) {
        const edge = d > 0.68
        px[y][x] = edge ? OUT : y < 25 ? '#5fb59b' : '#3f8f7e'
      }
    }
  }
}

pad()
const bx = 16
const by = 24
petal({ angle: -74, L: 15, w: 2.9, bx, by, tone: 2.2 })
petal({ angle: 74, L: 15, w: 2.9, bx, by, tone: 2.2 })
petal({ angle: -40, L: 19, w: 3.3, bx, by, tone: 1.4 })
petal({ angle: 40, L: 19, w: 3.3, bx, by, tone: 1.4 })
petal({ angle: 0, L: 21, w: 4.2, bx, by, tone: 0.8 })

const rects = []
for (let y = 0; y < H; y++) {
  let x = 0
  while (x < W) {
    const c = px[y][x]
    let run = 1
    while (x + run < W && px[y][x + run] === c) run++
    if (c) rects.push(`<rect x="${x}" y="${y}" width="${run}" height="1" fill="${c}"/>`)
    x += run
  }
}
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" shape-rendering="crispEdges">${rects.join('')}</svg>\n`
writeFileSync(new URL('../public/art/lotus.svg', import.meta.url), svg)
console.log('wrote art/lotus.svg')
