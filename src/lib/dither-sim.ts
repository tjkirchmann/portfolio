// Life-like fields for the Dither block. Pure TypeScript (erasable syntax only), shared by the
// build (warm-up, so every page starts pre-evolved) and the browser (stepping and drawing).
//
// Each simulation lives on a small torus (SIM x SIM cells). Two channels are drawn:
//   density: what goes through the Bayer threshold (solid middles, halftone edges)
//   age:     how long a place has been occupied; picks the palette colour (green -> gold -> copper)

export type Mode = 'life' | 'smooth' | 'flow';
export const MODES: Mode[] = ['life', 'smooth', 'flow'];

export interface Sim {
  mode: Mode;
  w: number;
  h: number;
  /** state channels, all in 0..1; the first two are always density and age */
  ch: Float32Array[];
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

// ---------- helpers ----------

/** age follows occupancy: rises slowly where dense, falls faster where empty */
function updateAge(density: Float32Array, age: Float32Array, rise: number, fall: number, on = 0.25) {
  for (let i = 0; i < age.length; i++) {
    const a = density[i] > on ? age[i] + rise : age[i] - fall;
    age[i] = a < 0 ? 0 : a > 1 ? 1 : a;
  }
}

/** 3x3 box blur on a torus, src -> dst */
function blur3(src: Float32Array, dst: Float32Array, w: number, h: number) {
  for (let y = 0; y < h; y++) {
    const ym = ((y + h - 1) % h) * w, y0 = y * w, yp = ((y + 1) % h) * w;
    for (let x = 0; x < w; x++) {
      const xm = (x + w - 1) % w, xp = (x + 1) % w;
      dst[y0 + x] =
        (src[ym + xm] + src[ym + x] + src[ym + xp] + src[y0 + xm] + src[y0 + x] + src[y0 + xp] + src[yp + xm] + src[yp + x] + src[yp + xp]) / 9;
    }
  }
}

function blobs(r: () => number, w: number, h: number, n: number, rMin: number, rMax: number, into: Float32Array, value = 1) {
  for (let b = 0; b < n; b++) {
    const cx = r() * w, cy = r() * h, rad = rMin + r() * (rMax - rMin);
    for (let y = Math.floor(cy - rad); y <= cy + rad; y++) {
      for (let x = Math.floor(cx - rad); x <= cx + rad; x++) {
        const d = Math.hypot(x - cx, y - cy) / rad;
        if (d > 1) continue;
        const i = ((y + h) % h) * w + ((x + w) % w);
        into[i] = Math.max(into[i], value * (r() < 0.75 ? 1 : 0) * (1 - d * 0.3));
      }
    }
  }
}

// ---------- life: a Conway-family automaton with decaying trails ----------
export const LIFE = {
  // B3/S23 (Conway): restless, never fills; quiet patches are reseeded
  B: [0, 0, 0, 1, 0, 0, 0, 0, 0],
  S: [0, 0, 1, 1, 0, 0, 0, 0, 0],
  every: 3,
  rise: 0.09,
  decay: 0.955,
};
// The automaton runs on a coarse grid (one generation every few steps) and each live cell
// feeds a slowly decaying trail. The blurred trail is what gets dithered, so activity reads as
// large soft masses that drift, merge and fade. Stalls, die-offs and overfills are nudged
// quietly with a small random patch.

function lifeSim(seed: number, w: number, h: number): Sim {
  const r = rng(seed);
  const alive = new Float32Array(w * h);
  const next = new Float32Array(w * h);
  const trail = new Float32Array(w * h);
  const density = new Float32Array(w * h);
  const age = new Float32Array(w * h);
  // seed: a few soup patches on black
  for (let b = 0; b < 3; b++) {
    const cx = Math.floor(r() * w), cy = Math.floor(r() * h), rad = 3 + Math.floor(r() * 3);
    for (let y = -rad; y <= rad; y++)
      for (let x = -rad; x <= rad; x++)
        if (x * x + y * y <= rad * rad && r() < 0.62) alive[((cy + y + h) % h) * w + ((cx + x + w) % w)] = 1;
  }
  const B = LIFE.B;
  const S = LIFE.S;
  let quiet = 0;
  const sim: Sim = {
    mode: 'life', w, h, ch: [density, age, alive, trail], steps: 0,
    step() {
      tick++;
      if (tick % LIFE.every === 0) generation();
      for (let i = 0; i < trail.length; i++) trail[i] = alive[i] ? Math.min(1, trail[i] + LIFE.rise) : trail[i] * LIFE.decay;
      blur3(trail, density, w, h);
      updateAge(density, age, 0.006, 0.01, 0.3);
      sim.steps++;
    },
  };
  let tick = 0;
  function generation() {
      let changed = 0, pop = 0;
      for (let y = 0; y < h; y++) {
        const ym = ((y + h - 1) % h) * w, y0 = y * w, yp = ((y + 1) % h) * w;
        for (let x = 0; x < w; x++) {
          const xm = (x + w - 1) % w, xp = (x + 1) % w;
          const n = alive[ym + xm] + alive[ym + x] + alive[ym + xp] + alive[y0 + xm] + alive[y0 + xp] + alive[yp + xm] + alive[yp + x] + alive[yp + xp];
          const a = alive[y0 + x];
          const v = a ? S[n] : B[n];
          next[y0 + x] = v;
          if (v !== a) changed++;
          pop += v;
        }
      }
      alive.set(next);
      // keep it from going still, from dying, or from filling: quietly nudge
      quiet = changed < 2 ? quiet + 1 : 0;
      const frac = pop / (w * h);
      if (quiet > 12 || frac < 0.06) {
        const cx = Math.floor(r() * w), cy = Math.floor(r() * h);
        for (let y = -2; y <= 2; y++) for (let x = -2; x <= 2; x++) if (r() < 0.55) alive[((cy + y + h) % h) * w + ((cx + x + w) % w)] = 1;
        quiet = 0;
      } else if (frac > 0.42) {
        const cx = Math.floor(r() * w), cy = Math.floor(r() * h);
        for (let y = -3; y <= 3; y++) for (let x = -3; x <= 3; x++) alive[((cy + y + h) % h) * w + ((cx + x + w) % w)] = 0;
      }
  }
  return sim;
}

// ---------- smooth: Lenia-style continuous field ----------

export const LENIA = { R: 5, mu: 0.15, sigma: 0.017, dt: 0.1, blobs: 3 };

function lenia(seed: number, w: number, h: number): Sim {
  const r = rng(seed);
  const { R, mu, sigma, dt } = LENIA;
  const A = new Float32Array(w * h);
  const U = new Float32Array(w * h);
  const density = new Float32Array(w * h);
  const age = new Float32Array(w * h);
  // ring kernel as an offset list
  const kx: number[] = [], ky: number[] = [], kw: number[] = [];
  let sum = 0;
  for (let y = -R; y <= R; y++)
    for (let x = -R; x <= R; x++) {
      const d = Math.hypot(x, y) / R;
      if (d <= 0 || d >= 1) continue;
      const v = Math.exp(4 - 1 / (d * (1 - d)));
      kx.push(x); ky.push(y); kw.push(v); sum += v;
    }
  const n = kw.length;
  const KX = Int32Array.from(kx), KY = Int32Array.from(ky), KW = Float32Array.from(kw.map((v) => v / sum));
  blobs(r, w, h, LENIA.blobs, R * 0.7, R * 1.1, A);
  const twoS2 = 2 * sigma * sigma;
  const sim: Sim = {
    mode: 'smooth', w, h, ch: [density, age, A], steps: 0,
    step() {
      let mass = 0;
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          let u = 0;
          for (let k = 0; k < n; k++) {
            const yy = y + KY[k], xx = x + KX[k];
            u += A[(yy < 0 ? yy + h : yy >= h ? yy - h : yy) * w + (xx < 0 ? xx + w : xx >= w ? xx - w : xx)] * KW[k];
          }
          U[y * w + x] = u;
        }
      }
      for (let i = 0; i < A.length; i++) {
        const g = 2 * Math.exp(-((U[i] - mu) ** 2) / twoS2) - 1;
        const a = A[i] + dt * g;
        A[i] = a < 0 ? 0 : a > 1 ? 1 : a;
        mass += A[i];
      }
      const frac = mass / (w * h);
      if (frac < 0.03) blobs(r, w, h, 1, R * 0.8, R * 1.4, A);
      blur3(A, density, w, h);
      updateAge(density, age, 0.005, 0.015, 0.2);
      sim.steps++;
    },
  };
  return sim;
}

// ---------- flow: Gray-Scott reaction-diffusion ----------

function grayScott(seed: number, w: number, h: number): Sim {
  const r = rng(seed);
  const u = new Float32Array(w * h).fill(1);
  const v = new Float32Array(w * h);
  const u2 = new Float32Array(w * h);
  const v2 = new Float32Array(w * h);
  const density = new Float32Array(w * h);
  const tmp = new Float32Array(w * h);
  const age = new Float32Array(w * h);
  const F = 0.026, K = 0.061, Du = 0.21, Dv = 0.105;
  const seedV = new Float32Array(w * h);
  blobs(r, w, h, 4, 2, 4, seedV);
  for (let i = 0; i < v.length; i++) if (seedV[i] > 0) { v[i] = 0.5 + r() * 0.2; u[i] = 0.5; }
  const ITER = 6;
  const sim: Sim = {
    mode: 'flow', w, h, ch: [density, age, u, v], steps: 0,
    step() {
      for (let it = 0; it < ITER; it++) {
        for (let y = 0; y < h; y++) {
          const ym = ((y + h - 1) % h) * w, y0 = y * w, yp = ((y + 1) % h) * w;
          for (let x = 0; x < w; x++) {
            const xm = (x + w - 1) % w, xp = (x + 1) % w, i = y0 + x;
            const lu = (u[ym + x] + u[yp + x] + u[y0 + xm] + u[y0 + xp]) * 0.2 + (u[ym + xm] + u[ym + xp] + u[yp + xm] + u[yp + xp]) * 0.05 - u[i];
            const lv = (v[ym + x] + v[yp + x] + v[y0 + xm] + v[y0 + xp]) * 0.2 + (v[ym + xm] + v[ym + xp] + v[yp + xm] + v[yp + xp]) * 0.05 - v[i];
            const uvv = u[i] * v[i] * v[i];
            u2[i] = u[i] + Du * lu - uvv + F * (1 - u[i]);
            v2[i] = v[i] + Dv * lv + uvv - (F + K) * v[i];
          }
        }
        u.set(u2);
        v.set(v2);
      }
      let mass = 0;
      for (let i = 0; i < v.length; i++) {
        tmp[i] = Math.min(1, v[i] * 3);
        mass += v[i];
      }
      if (mass / (w * h) < 0.01) {
        const s = new Float32Array(w * h);
        blobs(r, w, h, 2, 2, 4, s);
        for (let i = 0; i < v.length; i++) if (s[i] > 0) { v[i] = 0.5; u[i] = 0.5; }
      }
      blur3(tmp, density, w, h);
      updateAge(density, age, 0.004, 0.012, 0.25);
      sim.steps++;
    },
  };
  return sim;
}

export const SIZES: Record<Mode, number> = { life: 20, smooth: 20, flow: 28 };

export function createSim(mode: Mode, seed: string): Sim {
  const s = hashSeed(`${mode}:${seed}`);
  const n = SIZES[mode];
  if (mode === 'life') return lifeSim(s, n, n);
  if (mode === 'flow') return grayScott(s, n, n);
  return lenia(s, n, n);
}

export const WARMUP: Record<Mode, number> = { life: 160, smooth: 220, flow: 260 };

// ---------- state transfer (build -> browser) ----------

export function encodeState(sim: Sim): string {
  const bytes = new Uint8Array(sim.ch.length * sim.w * sim.h);
  sim.ch.forEach((c, k) => {
    for (let i = 0; i < c.length; i++) bytes[k * c.length + i] = Math.round(Math.min(1, Math.max(0, c[i])) * 255);
  });
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

export function decodeState(sim: Sim, b64: string) {
  const bin = atob(b64);
  const len = sim.w * sim.h;
  if (bin.length !== sim.ch.length * len) return false;
  sim.ch.forEach((c, k) => {
    for (let i = 0; i < len; i++) c[i] = bin.charCodeAt(k * len + i) / 255;
  });
  return true;
}

// ---------- drawing ----------

const BAYER = [
  0, 32, 8, 40, 2, 34, 10, 42, 48, 16, 56, 24, 50, 18, 58, 26,
  12, 44, 4, 36, 14, 46, 6, 38, 60, 28, 52, 20, 62, 30, 54, 22,
  3, 35, 11, 43, 1, 33, 9, 41, 51, 19, 59, 27, 49, 17, 57, 25,
  15, 47, 7, 39, 13, 45, 5, 37, 63, 31, 55, 23, 61, 29, 53, 21,
].map((v) => (v + 0.5) / 64);

export interface Mapping {
  cols: number;
  rows: number;
  i00: Int32Array; i10: Int32Array; i01: Int32Array; i11: Int32Array;
  fx: Float32Array; fy: Float32Array;
}

/** how much of the torus is shown: >1 crops in, so features read larger */
export const ZOOM: Record<Mode, number> = { life: 1, smooth: 1.8, flow: 1.5 };

/** Precomputes bilinear lookups from the display grid into the sim grid ("cover" fit). */
export function makeMapping(sim: Sim, cols: number, rows: number): Mapping {
  const n = cols * rows;
  const m: Mapping = {
    cols, rows,
    i00: new Int32Array(n), i10: new Int32Array(n), i01: new Int32Array(n), i11: new Int32Array(n),
    fx: new Float32Array(n), fy: new Float32Array(n),
  };
  const scale = Math.max(cols / sim.w, rows / sim.h) * ZOOM[sim.mode]; // display cells per sim cell
  const ox = (cols / scale - sim.w) / 2, oy = (rows / scale - sim.h) / 2;
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const sx = (x + 0.5) / scale - ox - 0.5, sy = (y + 0.5) / scale - oy - 0.5;
      const x0 = Math.floor(sx), y0 = Math.floor(sy);
      const a = ((x0 % sim.w) + sim.w) % sim.w, b = ((y0 % sim.h) + sim.h) % sim.h;
      const a1 = (a + 1) % sim.w, b1 = (b + 1) % sim.h;
      const i = y * cols + x;
      m.i00[i] = b * sim.w + a; m.i10[i] = b * sim.w + a1; m.i01[i] = b1 * sim.w + a; m.i11[i] = b1 * sim.w + a1;
      m.fx[i] = sx - x0; m.fy[i] = sy - y0;
    }
  }
  return m;
}

export const PALETTE = {
  bg: '#0a0c0b', deep: '#326e54', teal: '#579d87', emerald: '#76c8a5', leaf: '#73984f',
  gold: '#bbc368', copper: '#9f814e', bronze: '#85692c',
};
/** young -> old */
export const RAMP = ['#326e54', '#579d87', '#76c8a5', '#73984f', '#bbc368', '#9f814e'];

/** Palette stops as RGB, scaled by intensity (to keep the wireframe readable on top). */
export function rampColours(ramp: string[], intensity: number): Uint8Array {
  const out = new Uint8Array(ramp.length * 3);
  ramp.forEach((c, k) => {
    for (let j = 0; j < 3; j++) out[k * 3 + j] = Math.round(parseInt(c.slice(1 + j * 2, 3 + j * 2), 16) * intensity);
  });
  return out;
}

const BG = [10, 12, 11];

/** Writes one frame into an RGBA buffer of cols x rows. Returns the fraction of empty cells. */
/** density remap per mode: v' = (v - offset) * gain */
export const GAIN: Record<Mode, number> = { life: 2.2, smooth: 2.4, flow: 1.4 };
export const OFFSET: Record<Mode, number> = { life: 0.12, smooth: 0.1, flow: 0.05 };

/** Writes one frame into an RGBA buffer of cols x rows. Returns the fraction of empty cells.
 *  Both the on/off decision (density) and the colour step (age) go through the Bayer matrix,
 *  so masses are flat palette colours with ordered transitions, never smooth gradients. */
export function draw(sim: Sim, m: Mapping, lut: Uint8Array, out: Uint8ClampedArray): number {
  const d = sim.ch[0], g = sim.ch[1];
  const gain = GAIN[sim.mode], off = OFFSET[sim.mode];
  const stops = lut.length / 3 - 1;
  let empty = 0;
  const n = m.cols * m.rows;
  for (let i = 0; i < n; i++) {
    const fx = m.fx[i], fy = m.fy[i];
    const w00 = (1 - fx) * (1 - fy), w10 = fx * (1 - fy), w01 = (1 - fx) * fy, w11 = fx * fy;
    const v = (d[m.i00[i]] * w00 + d[m.i10[i]] * w10 + d[m.i01[i]] * w01 + d[m.i11[i]] * w11 - off) * gain;
    const x = i % m.cols, y = (i / m.cols) | 0;
    const o = i * 4;
    if (v > BAYER[((y & 7) << 3) | (x & 7)]) {
      // colour: edges stay deep/teal, solid bodies emerald-leaf, cores that are dense and old reach gold/copper
      const age = g[m.i00[i]] * w00 + g[m.i10[i]] * w10 + g[m.i01[i]] * w01 + g[m.i11[i]] * w11;
      const dens = v > 1.4 ? 1 : (v - 0.4) / 1.0;
      let t = (dens > 0 ? dens : 0) * 0.55 + age * 0.6;
      if (t > 1) t = 1;
      const a = t * stops;
      let k = a | 0;
      if (a - k > BAYER[(((x + 3) & 7) << 3) | ((y + 5) & 7)]) k++;
      const li = (k > stops ? stops : k) * 3;
      out[o] = lut[li]; out[o + 1] = lut[li + 1]; out[o + 2] = lut[li + 2];
    } else {
      out[o] = BG[0]; out[o + 1] = BG[1]; out[o + 2] = BG[2];
      empty++;
    }
    out[o + 3] = 255;
  }
  return empty / n;
}
