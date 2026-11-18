// Paint tools for the Life field: a brush that lays real live cells, a gravity well that carries
// an empty circle with a ring of cells around it, and explosions that push cells outward as a
// shockwave. Everything is cells: tools write into the simulation's own arrays (alive, trail,
// paint) or, for the parts that are not permanent, into the classify() output the renderer
// draws, so the metal shader shades them like everything else.
//
// Coordinates are visible-window cells (floats allowed), mapped onto the torus through
// windowOrigin(). The grid size comes from the caller on each call, since the pane can resize.

import { windowOrigin, rampByte, type Life } from './dither-sim';

export interface Grid {
  cols: number;
  rows: number;
}

/** well radius (empty inside) and how far its ring reaches out */
const WELL_R = 7;
const WELL_RING = 6;
/** explosion reach in cells and its time to full size */
const BLAST_R = 26;
const BLAST_MS = 560;
/** brush: cells drawn per one-way trip through the ramp, and the ramp range it uses */
const BRUSH_TRIP = 60;
const BRUSH_TOP = 0.8;
/** a stroke stays as drawn this long before its cells are handed to Life, so it reads as a
 *  line behind the pointer and then comes alive segment by segment */
const BRUSH_HOLD = 450;

interface Blast {
  x: number;
  y: number;
  t0: number;
  r: number;
  seed: number;
}

// cheap stable hash -> [0, 1), for grain that does not crawl like a Bayer pattern would
function hash(x: number, y: number, s: number) {
  let h = Math.imul(x * 374761393 + y * 668265263 + s * 2147483647, 1274126177);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

export interface Tools {
  brush(x: number, y: number, down: boolean): void;
  brushEnd(): void;
  /** hand any held stroke to Life now */
  flushBrush(): void;
  /** where the pointer is for the well; null lets it dissolve */
  well(x: number | null, y: number | null): void;
  explode(x: number, y: number, now: number): void;
  /** per animation frame: move the well, advance blasts. True while anything is animating. */
  frame(now: number): boolean;
  /** after each Life step: the well keeps its circle clear */
  afterStep(): void;
  /** draw the non-permanent parts (well ring, blast fronts) into classify() output */
  paint(cells: Uint8Array, now: number): void;
  /** drop the well at once (the text panel opened) */
  dropWell(): void;
  clear(): void;
}

export function createTools(life: Life, grid: () => Grid): Tools {
  const r = Math.random;
  const ti = (x: number, y: number, g: Grid) => {
    const { ox, oy } = windowOrigin(life, g.cols, g.rows);
    return ((oy + y + life.h) % life.h) * life.w + ((ox + x + life.w) % life.w);
  };
  const inGrid = (x: number, y: number, g: Grid) => x >= 0 && y >= 0 && x < g.cols && y < g.rows;

  // ---- brush ----
  let last: { x: number; y: number } | null = null;
  let dist = 0;
  const brushPos = () => {
    const k = (dist / BRUSH_TRIP) % 2;
    return (k < 1 ? k : 2 - k) * BRUSH_TOP;
  };
  let pending: { x: number; y: number; i: number; p: number; t: number }[] = [];
  function dab(cx: number, cy: number, g: Grid) {
    const x = Math.floor(cx), y = Math.floor(cy);
    if (!inGrid(x, y, g)) return;
    pending.push({ x, y, i: ti(x, y, g), p: rampByte(brushPos()), t: performance.now() });
  }
  function commitDabs(before: number) {
    let n = 0;
    while (n < pending.length && pending[n].t <= before) {
      const d = pending[n++];
      life.alive[d.i] = 1;
      life.trail[d.i] = 1;
      life.paint[d.i] = d.p;
    }
    if (n) {
      pending = pending.slice(n);
      life.markPainted();
    }
  }

  // ---- well ----
  let target: { x: number; y: number } | null = null;
  let wx = 0, wy = 0;
  let strength = 0; // 0..1, fades in and out
  let wellOn = false;
  let lastFrame = 0;

  /** push every cell inside the circle out to just past its edge, along its own direction */
  function pushOut(g: Grid) {
    if (strength < 0.5) return;
    const R = WELL_R * Math.min(1, strength * 1.4);
    const x0 = Math.max(0, Math.floor(wx - R - 1)), x1 = Math.min(g.cols - 1, Math.ceil(wx + R + 1));
    const y0 = Math.max(0, Math.floor(wy - R - 1)), y1 = Math.min(g.rows - 1, Math.ceil(wy + R + 1));
    for (let y = y0; y <= y1; y++)
      for (let x = x0; x <= x1; x++) {
        const dx = x + 0.5 - wx, dy = y + 0.5 - wy;
        const d = Math.hypot(dx, dy);
        if (d >= R) continue;
        const i = ti(x, y, g);
        if (life.alive[i]) {
          const ux = d > 0.01 ? dx / d : r() - 0.5, uy = d > 0.01 ? dy / d : r() - 0.5;
          for (const k of [0.6, 1.6, 2.6, 3.6]) {
            const nx = Math.floor(wx + ux * (R + k)), ny = Math.floor(wy + uy * (R + k));
            if (!inGrid(nx, ny, g)) break;
            const j = ti(nx, ny, g);
            if (life.alive[j]) continue;
            life.alive[j] = 1;
            life.trail[j] = 1;
            life.paint[j] = life.paint[i];
            break;
          }
        }
        life.alive[i] = 0;
        life.trail[i] = 0;
        life.paint[i] = 0;
      }
  }

  // ---- blasts ----
  let blasts: Blast[] = [];
  let seedN = 1;
  const blastEase = (t: number) => 1 - Math.pow(1 - t, 2.2);

  function advance(b: Blast, now: number, g: Grid) {
    const t = Math.min(1, (now - b.t0) / BLAST_MS);
    const R = BLAST_R * blastEase(t);
    const hot = rampByte(1 - 0.3 * t);
    const x0 = Math.max(0, Math.floor(b.x - R - 1)), x1 = Math.min(g.cols - 1, Math.ceil(b.x + R + 1));
    const y0 = Math.max(0, Math.floor(b.y - R - 1)), y1 = Math.min(g.rows - 1, Math.ceil(b.y + R + 1));
    // snowplough: everything inside the front is carried to the front, leaving a cooling wake
    for (let y = y0; y <= y1; y++)
      for (let x = x0; x <= x1; x++) {
        const dx = x + 0.5 - b.x, dy = y + 0.5 - b.y;
        const d = Math.hypot(dx, dy);
        if (d >= R - 0.5) continue;
        const i = ti(x, y, g);
        if (!life.alive[i]) continue;
        const ux = d > 0.01 ? dx / d : Math.cos(r() * 6.283), uy = d > 0.01 ? dy / d : Math.sin(r() * 6.283);
        const k = R + r() * 1.2;
        const nx = Math.floor(b.x + ux * k), ny = Math.floor(b.y + uy * k);
        life.alive[i] = 0;
        // a faint cooling wake, so the centre reads as hollow
        life.trail[i] = 0.22;
        life.paint[i] = rampByte(0.55 - 0.35 * t);
        if (!inGrid(nx, ny, g)) continue;
        const j = ti(nx, ny, g);
        life.alive[j] = 1;
        life.trail[j] = 1;
        life.paint[j] = hot;
      }
    b.r = R;
    if (t < 1) return true;
    // cooled: the carried cells take ordinary ramp colours
    for (let y = Math.max(0, Math.floor(b.y - R - 3)); y <= Math.min(g.rows - 1, Math.ceil(b.y + R + 3)); y++)
      for (let x = Math.max(0, Math.floor(b.x - R - 3)); x <= Math.min(g.cols - 1, Math.ceil(b.x + R + 3)); x++) {
        const i = ti(x, y, g);
        if (life.alive[i] && life.paint[i] >= rampByte(0.65)) life.paint[i] = rampByte(0.45 + r() * 0.35);
      }
    // debris: small clumps around the edge (single cells would just die), and a few inside
    const clumps = Math.round((Math.PI * 2 * R) / 5);
    for (let k = 0; k < clumps + 4; k++) {
      if (k < clumps && r() > 0.55) continue;
      const a = r() * Math.PI * 2;
      const rr = k < clumps ? R + (r() - 0.5) * 2.5 : R * (0.2 + r() * 0.5);
      const cx = Math.round(b.x + Math.cos(a) * rr), cy = Math.round(b.y + Math.sin(a) * rr);
      const col = rampByte(0.35 + r() * 0.45);
      for (let dy = -1; dy <= 1; dy++)
        for (let dx = -1; dx <= 1; dx++) {
          if (r() > 0.55 || !inGrid(cx + dx, cy + dy, g)) continue;
          const i = ti(cx + dx, cy + dy, g);
          life.alive[i] = 1;
          life.trail[i] = 1;
          life.paint[i] = col;
        }
    }
    return false;
  }

  return {
    brush(x, y, down) {
      const g = grid();
      if (down || !last) {
        last = { x, y };
        dab(x, y, g);
      } else {
        // fill between samples so fast strokes stay continuous
        const dx = x - last.x, dy = y - last.y;
        const n = Math.max(1, Math.ceil(Math.hypot(dx, dy) * 2));
        let px = Math.floor(last.x), py = Math.floor(last.y);
        for (let k = 1; k <= n; k++) {
          const cx = last.x + (dx * k) / n, cy = last.y + (dy * k) / n;
          const fx = Math.floor(cx), fy = Math.floor(cy);
          if (fx === px && fy === py) continue;
          // no diagonal-only joins: a one-cell line should read as connected
          if (fx !== px && fy !== py) dab(fx, py, g);
          dist += 1;
          dab(cx, cy, g);
          px = fx;
          py = fy;
        }
        last = { x, y };
      }
    },
    brushEnd() {
      last = null;
    },
    flushBrush() {
      commitDabs(Infinity);
    },
    well(x, y) {
      if (x === null || y === null) {
        wellOn = false;
        return;
      }
      if (!wellOn && strength < 0.05) (wx = x), (wy = y);
      target = { x, y };
      wellOn = true;
    },
    explode(x, y, now) {
      blasts.push({ x, y, t0: now, r: 0, seed: seedN++ });
      life.markPainted();
    },
    frame(now) {
      const g = grid();
      const dt = lastFrame ? Math.min(64, now - lastFrame) : 16;
      lastFrame = now;
      // the well eases after the pointer and fades in/out over about 250ms
      strength = Math.min(1, Math.max(0, strength + (wellOn ? 1 : -1) * (dt / 250)));
      if (target && strength > 0) {
        const k = 1 - Math.pow(0.65, dt / 16);
        wx += (target.x - wx) * k;
        wy += (target.y - wy) * k;
        if (wellOn) pushOut(g);
      }
      if (pending.length) commitDabs(now - BRUSH_HOLD);
      if (blasts.length) {
        blasts = blasts.filter((b) => advance(b, now, g));
        life.markPainted();
      }
      if (!wellOn && strength === 0) target = null;
      return strength > 0 || blasts.length > 0 || pending.length > 0;
    },
    afterStep() {
      if (wellOn) pushOut(grid());
    },
    paint(cells, now) {
      const g = grid();
      const put = (x: number, y: number, v: number, b: number) => {
        if (!inGrid(x, y, g)) return;
        const o = (y * g.cols + x) * 4;
        if (cells[o] >= v && cells[o + 2]) return; // never dim a brighter painted cell
        cells[o] = v;
        cells[o + 2] = b;
      };
      if (strength > 0 && target) {
        const R = WELL_R * Math.min(1, strength * 1.4);
        const out = R + WELL_RING;
        for (let y = Math.floor(wy - out); y <= Math.ceil(wy + out); y++)
          for (let x = Math.floor(wx - out); x <= Math.ceil(wx + out); x++) {
            if (!inGrid(x, y, g)) continue;
            const d = Math.hypot(x + 0.5 - wx, y + 0.5 - wy);
            const o = (y * g.cols + x) * 4;
            if (d < R) {
              cells[o] = 0; // pure empty inside, even before the next push
              continue;
            }
            if (d > out) continue;
            const f = (d - R) / WELL_RING; // 0 at the rim, 1 at the outer edge
            const dens = Math.pow(1 - f, 0.8) * 0.9 * strength;
            if (hash(x, y, 7) > dens) continue;
            put(x, y, f < 0.4 ? 255 : f < 0.75 ? 150 : 90, rampByte(0.95 - f * 0.8));
          }
      }
      for (const d of pending) put(d.x, d.y, 255, d.p);
      for (const b of blasts) {
        const t = Math.min(1, (now - b.t0) / BLAST_MS);
        const R = BLAST_R * blastEase(t);
        const fade = 1 - t * 0.55;
        for (let y = Math.floor(b.y - R - 2); y <= Math.ceil(b.y + R + 2); y++)
          for (let x = Math.floor(b.x - R - 2); x <= Math.ceil(b.x + R + 2); x++) {
            const d = Math.hypot(x + 0.5 - b.x, y + 0.5 - b.y);
            const e = R - d; // >0 behind the front
            if (e < -1.2 || e > 8) continue;
            const n = hash(x, y, b.seed + Math.floor(t * 10));
            if (e < 1.6) {
              // the front: thick, hot, blue-white
              if (n < 0.85 * fade) put(x, y, 255, rampByte(1 - 0.15 * t));
            } else if (n < Math.pow(1 - e / 8, 1.4) * 0.8 * fade) {
              // behind it, cooling through the ramp
              put(x, y, e < 4 ? 255 : e < 6 ? 150 : 90, rampByte(0.85 - (e / 8) * 0.7));
            }
          }
      }
    },
    dropWell() {
      wellOn = false;
      strength = 0;
      target = null;
    },
    clear() {
      blasts = [];
      pending = [];
      wellOn = false;
      strength = 0;
      target = null;
      last = null;
      dist = 0;
    },
  };
}
