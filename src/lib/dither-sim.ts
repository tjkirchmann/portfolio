// The Dither block's simulation: Conway's Life at display resolution, one automaton cell per
// drawn square. Pure TypeScript (erasable syntax only), shared by the build (seeding and
// warm-up, so every page starts pre-evolved) and the browser (stepping and drawing).
//
// Live cells are solid emerald. A cell that dies leaves a trail that fades over a second or
// two; the trail goes through an 8x8 Bayer threshold (teal, then deep, then gone), which is
// where the halftone comes from. Nothing is blurred or upscaled.

/** The torus is fixed so the build can pre-evolve it; panes show a centred window onto it. */
export const SIZE = 192;
export const WARMUP = 240;

export interface Life {
  w: number;
  h: number;
  alive: Uint8Array;
  trail: Float32Array;
  steps: number;
  step(): void;
}

// ---------- seeded randomness ----------

export function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- the automaton ----------

/** trail multiplier per step: about 1.5 s from full to gone at 10 steps/s */
export const DECAY = 0.84;
/** initial random fill; the warm-up burns it down to Life's usual sparse mix */
export const SOUP = 0.3;
/** below this fraction of cells changing per step, a methuselah is planted */
export const ACTIVITY = 0.012;

/** `fill: false` skips the initial soup, for a field that will be loaded with decodeState. */
export function createLife(seed: string, w = SIZE, h = SIZE, fill = true): Life {
  const r = rng(hashSeed(`life:${seed}`));
  const alive = new Uint8Array(w * h);
  const next = new Uint8Array(w * h);
  const trail = new Float32Array(w * h);
  const col = new Uint8Array(w);

  const soup = (cx: number, cy: number, rad: number, p: number) => {
    for (let y = -rad; y <= rad; y++)
      for (let x = -rad; x <= rad; x++)
        if (r() < p) alive[((cy + y + h) % h) * w + ((cx + x + w) % w)] = 1;
  };
  // sparse soup patches on black; the warm-up turns them into gliders, ash and oscillators
  if (fill) for (let i = 0; i < alive.length; i++) alive[i] = r() < SOUP ? 1 : 0;

  // methuselahs: tiny seeds that run for hundreds of generations before settling
  const SEEDS = [
    [[1, 0], [2, 0], [0, 1], [1, 1], [1, 2]], // R-pentomino
    [[1, 0], [3, 1], [0, 2], [1, 2], [4, 2], [5, 2], [6, 2]], // acorn
    [[6, 0], [0, 1], [1, 1], [1, 2], [5, 2], [6, 2], [7, 2]], // diehard
  ];
  const plant = () => {
    // mostly inside the central window that panes show
    const cx = Math.floor(w * (0.2 + r() * 0.6)), cy = Math.floor(h * (0.15 + r() * 0.7));
    const shape = SEEDS[Math.floor(r() * SEEDS.length)];
    const flip = r() < 0.5, rot = r() < 0.5;
    for (const [a, b] of shape) {
      let x = flip ? -a : a, y = b;
      if (rot) [x, y] = [y, x];
      alive[((cy + y + h) % h) * w + ((cx + x + w) % w)] = 1;
    }
  };

  let quiet = 0;
  const life: Life = {
    w, h, alive, trail, steps: 0,
    step() {
      let changed = 0;
      let pop = 0;
      // column sums of three rows, then a sliding window of three columns: 3 adds per cell
      for (let y = 0; y < h; y++) {
        const ym = (y === 0 ? h - 1 : y - 1) * w, y0 = y * w, yp = (y === h - 1 ? 0 : y + 1) * w;
        for (let x = 0; x < w; x++) col[x] = alive[ym + x] + alive[y0 + x] + alive[yp + x];
        let left = col[w - 1], mid = col[0];
        for (let x = 0; x < w; x++) {
          const right = col[x === w - 1 ? 0 : x + 1];
          const i = y0 + x;
          const a = alive[i];
          const n = left + mid + right - a;
          const v = n === 3 || (a === 1 && n === 2) ? 1 : 0;
          next[i] = v;
          changed += v ^ a;
          pop += v;
          left = mid;
          mid = right;
        }
      }
      for (let i = 0; i < alive.length; i++) {
        const a = next[i];
        trail[i] = a ? 1 : trail[i] * DECAY;
        alive[i] = a;
      }
      // keep it alive but sparse: when it settles into ash, drop a small soup somewhere
      quiet = changed < w * h * ACTIVITY ? quiet + 1 : 0;
      if (quiet > 3) {
        plant();
        quiet = 0;
      }
      if (pop > w * h * 0.12) {
        // never let it thicken: thin a random patch (rarely needed in Life)
        const cx = Math.floor(r() * w), cy = Math.floor(r() * h);
        for (let y = -6; y <= 6; y++) for (let x = -6; x <= 6; x++) alive[((cy + y + h) % h) * w + ((cx + x + w) % w)] = 0;
      }
      life.steps++;
    },
  };
  return life;
}

// ---------- state transfer (build -> browser) ----------
// 2 bits per cell: 3 live, 2 fresh trail, 1 old trail, 0 empty. Enough to redraw the
// pre-evolved frame exactly as the dither sees it, trails included.

const LEVELS = [0, 0.2, 0.55, 1];

export function encodeState(l: Life): string {
  const bytes = new Uint8Array(Math.ceil(l.alive.length / 4));
  for (let i = 0; i < l.alive.length; i++) {
    const t = l.trail[i];
    const q = l.alive[i] ? 3 : t > 0.4 ? 2 : t > 0.08 ? 1 : 0;
    bytes[i >> 2] |= q << ((i & 3) * 2);
  }
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

export function decodeState(l: Life, b64: string): boolean {
  const bin = atob(b64);
  if (bin.length !== Math.ceil(l.alive.length / 4)) return false;
  for (let i = 0; i < l.alive.length; i++) {
    const q = (bin.charCodeAt(i >> 2) >> ((i & 3) * 2)) & 3;
    l.alive[i] = q === 3 ? 1 : 0;
    l.trail[i] = LEVELS[q];
  }
  return true;
}

// ---------- drawing ----------

const BAYER = Float32Array.from(
  [
    0, 32, 8, 40, 2, 34, 10, 42, 48, 16, 56, 24, 50, 18, 58, 26,
    12, 44, 4, 36, 14, 46, 6, 38, 60, 28, 52, 20, 62, 30, 54, 22,
    3, 35, 11, 43, 1, 33, 9, 41, 51, 19, 59, 27, 49, 17, 57, 25,
    15, 47, 7, 39, 13, 45, 5, 37, 63, 31, 55, 23, 61, 29, 53, 21,
  ],
  (v) => (v + 0.5) / 64,
);

export const BG = [10, 12, 11];
/** emerald (live), teal (fresh trail), deep (old trail) */
export const COLOURS = ['#76c8a5', '#579d87', '#326e54'];

export function colours(intensity: number): Uint8Array {
  const out = new Uint8Array(9);
  COLOURS.forEach((c, k) => {
    for (let j = 0; j < 3; j++) {
      const v = parseInt(c.slice(1 + j * 2, 3 + j * 2), 16);
      out[k * 3 + j] = Math.round(BG[j] + (v - BG[j]) * intensity);
    }
  });
  return out;
}

/** Top-left of the visible window in torus coordinates, centred. */
export function windowOrigin(l: Life, cols: number, rows: number) {
  return { ox: Math.floor((l.w - Math.min(cols, l.w)) / 2), oy: Math.floor((l.h - Math.min(rows, l.h)) / 2) };
}

/** Draws cols x rows cells (1 automaton cell = 1 pixel) into RGBA. Returns the empty fraction. */
export function draw(l: Life, cols: number, rows: number, pal: Uint8Array, out: Uint8ClampedArray): number {
  const { ox, oy } = windowOrigin(l, cols, rows);
  let empty = 0;
  for (let y = 0; y < rows; y++) {
    const ty = (oy + y) % l.h;
    for (let x = 0; x < cols; x++) {
      const i = ty * l.w + ((ox + x) % l.w);
      const o = (y * cols + x) * 4;
      let k = -1;
      if (l.alive[i]) k = 0;
      else {
        const t = l.trail[i];
        const b = BAYER[((y & 7) << 3) | (x & 7)];
        // trail density thins through the dither; colour steps teal -> deep, also dithered
        if (t * 0.9 > b) k = t > 0.35 + 0.3 * BAYER[(((x + 4) & 7) << 3) | ((y + 2) & 7)] ? 1 : 2;
      }
      if (k < 0) {
        out[o] = BG[0]; out[o + 1] = BG[1]; out[o + 2] = BG[2];
        empty++;
      } else {
        out[o] = pal[k * 3]; out[o + 1] = pal[k * 3 + 1]; out[o + 2] = pal[k * 3 + 2];
      }
      out[o + 3] = 255;
    }
  }
  return empty / (cols * rows);
}
