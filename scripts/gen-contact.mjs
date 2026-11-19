// Generates public/art/contact.svg: a dusk pond, same palette family as the project banners.
// Text is overlaid on it in the page, so the top is kept dark and calm. Run: node scripts/gen-contact.mjs
import { writeFileSync } from 'node:fs'

const W = 64
const H = 56
const HORIZON = 40
const px = Array.from({ length: H }, () => Array(W).fill(null))
const set = (x, y, c) => {
  x = Math.floor(x)
  y = Math.floor(y)
  if (x >= 0 && x < W && y >= 0 && y < H) px[y][x] = c
}

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))
const toHex = (rgb) => '#' + rgb.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')
const mix = (a, b, t) => toHex(hex(a).map((v, i) => v + (hex(b)[i] - v) * t))
const BAYER = [
  [0, 8, 2, 10],
  [12, 4, 14, 6],
  [3, 11, 1, 9],
  [15, 7, 13, 5],
]

// deterministic scatter
let seed = 7
const rand = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646

// dithered gradient: sky (navy -> violet -> rose) and water (mirror, darker)
const L = 7
const grad = (y0, y1, from, to, flip) => {
  for (let y = y0; y < y1; y++) {
    const t0 = (y - y0) / (y1 - y0 - 1)
    const t = (flip ? 1 - t0 : t0) * (L - 1)
    const base = Math.floor(t)
    const frac = t - base
    for (let x = 0; x < W; x++) {
      const k = Math.min(L - 1, base + (frac * 16 > BAYER[y % 4][x % 4] ? 1 : 0))
      set(x, y, mix(from, to, k / (L - 1)))
    }
  }
}
grad(0, HORIZON, '#17122e', '#d9507a', false)
grad(HORIZON, H, '#2a1d4f', '#17122e', false)

// stars
for (let i = 0; i < 26; i++) set(rand() * W, rand() * (HORIZON * 0.55), rand() > 0.75 ? '#ffffff' : '#6b5fa8')

// moon with shaded limb
const moon = (mx, my, r, col) => {
  for (let y = -r; y <= r; y++)
    for (let x = -r; x <= r; x++) if (x * x + y * y <= r * r + 1) set(mx + x, my + y, col)
}
moon(53, 31, 4, '#ffe9a8')
moon(54, 32, 3, '#e8cf8c')
set(51, 29, '#fff8d8')
set(52, 29, '#fff8d8')

// far hills along the horizon
for (let x = 0; x < W; x++) {
  const top = Math.round(HORIZON - 3 - 3 * (0.5 + 0.5 * Math.sin(x * 0.22 + 1)) - 2 * Math.sin(x * 0.61))
  for (let y = top; y < HORIZON; y++) set(x, y, y === top ? '#4a3a7a' : '#2f2358')
}
for (let x = 0; x < W; x++) set(x, HORIZON, '#8a6bb8') // shoreline glint

// moon streaks on the water
for (let i = 0; i < 7; i++) {
  const y = HORIZON + 2 + i * 2
  const w = 7 - i
  for (let x = 0; x < w; x++) if ((x + i) % 3 !== 2) set(53 - w / 2 + x, y, i % 2 ? '#e8cf8c' : '#c8aa7a')
}
// ripples
for (let i = 0; i < 16; i++) {
  const y = HORIZON + 2 + Math.floor(rand() * (H - HORIZON - 3))
  const x = Math.floor(rand() * (W - 5))
  for (let k = 0; k < 3 + Math.floor(rand() * 2); k++) set(x + k, y, '#4a3a7a')
}

// a few lily pads
for (const [cx, cy, r] of [[12, 48, 5], [26, 52, 4], [40, 46, 3]]) {
  for (let x = -r; x <= r; x++) {
    for (let y = 0; y <= 1; y++) {
      if ((x * x) / (r * r) + (y * y) / 1.2 <= 1.05) set(cx + x, cy + y, y ? '#3f8f7e' : '#5fb59b')
    }
  }
  set(cx + 1, cy, '#2a1d4f') // notch
}

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
writeFileSync(
  new URL('../public/art/contact.svg', import.meta.url),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" shape-rendering="crispEdges">${rects.join('')}</svg>\n`,
)
console.log('wrote art/contact.svg')
