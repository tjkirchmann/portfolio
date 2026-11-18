// The home hover panel's room in the Life field. When it opens, every cell inside a centred
// rectangle walks out to the rectangle's edge (each on its own jittered lattice path, all
// arriving within WALK ms) and settles into a 1-2 cell frame. While held, the inside stays
// empty and the frame stays put; the frame cells are drawn but are not Life neighbours, so the
// simulation outside carries on as it would. On release the frame cells become ordinary live
// cells and life grows back in.
//
// Everything here is in visible-window cell coordinates (x right, y down), mapped onto the
// torus through windowOrigin().

import { windowOrigin, type Life } from './dither-sim';

export const WALK = 500;
/** the walk back in after the panel closes */
export const BACK = 450;

interface Mover {
  /** path as visible indices, start first */
  path: Int32Array;
  delay: number;
  dur: number;
  /** 255 live, 150/90 trail: the look it starts with */
  v0: number;
  /** what it ends as: 255 frame cell, 0 fades out (overflow) */
  v1: number;
  hue: number;
  /** frame slot it lands in, -1 for overflow */
  slot: number;
}

export interface Rect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface Carve {
  rect: Rect;
  /** performance.now() when every cell has arrived */
  settleAt: number;
  walking(now: number): boolean;
  /** after each Life step: keep the inside empty */
  hold(): void;
  /** write the inside, the walkers and the frame into classify() output */
  paint(cells: Uint8Array, now: number): void;
  /** start handing the frame (and anything still walking) back: they walk in to a few seed
   *  spots; `quick` lands them at once */
  release(now: number, quick?: boolean): void;
  /** the walk back has finished (call commit) */
  done(now: number): boolean;
  /** put the returned cells into Life */
  commit(): void;
}

/** out of the way at once, then slowing as they line up */
const ease = (t: number) => 1 - Math.pow(1 - t, 2.4);

function gauss(r: () => number) {
  return (r() + r() + r() - 1.5) * 1.15;
}

/**
 * Opens a carve. `share` is the rectangle's fraction of the pane on each axis. `instant` skips
 * the walk (reduced motion, resize).
 */
export function openCarve(life: Life, cols: number, rows: number, now: number, instant = false, share = 0.64): Carve {
  const r = Math.random;
  const { ox, oy } = windowOrigin(life, cols, rows);
  const ti = (x: number, y: number) => ((oy + y + life.h) % life.h) * life.w + ((ox + x + life.w) % life.w);
  const vi = (x: number, y: number) => y * cols + x;
  const inGrid = (x: number, y: number) => x >= 0 && y >= 0 && x < cols && y < rows;

  const rw = Math.max(4, Math.round(cols * share));
  const rh = Math.max(4, Math.round(rows * share));
  const x0 = Math.floor((cols - rw) / 2), y0 = Math.floor((rows - rh) / 2);
  const x1 = x0 + rw, y1 = y0 + rh;
  const rect = { x0, y0, x1, y1 };
  const inside = (x: number, y: number) => x >= x0 && x < x1 && y >= y0 && y < y1;

  // frame slots: ring k (0 = touching the rectangle, 1 = next out), listed per side so a
  // walker can look along its side for a free one
  type Side = { pts: Int32Array; fixed: number; along0: number; horiz: boolean; nx: number; ny: number };
  const sides = (k: number): Side[] => {
    const lx = x0 - 1 - k, rx = x1 + k, ty = y0 - 1 - k, by = y1 + k;
    const run = (n: number, f: (i: number) => number) => Int32Array.from({ length: n }, (_, i) => f(i));
    return [
      { pts: run(by - ty + 1, (i) => vi(lx, ty + i)), fixed: lx, along0: ty, horiz: false, nx: -1, ny: 0 },
      { pts: run(by - ty + 1, (i) => vi(rx, ty + i)), fixed: rx, along0: ty, horiz: false, nx: 1, ny: 0 },
      { pts: run(rx - lx + 1, (i) => vi(lx + i, ty)), fixed: ty, along0: lx, horiz: true, nx: 0, ny: -1 },
      { pts: run(rx - lx + 1, (i) => vi(lx + i, by)), fixed: by, along0: lx, horiz: true, nx: 0, ny: 1 },
    ];
  };
  const rings = [sides(0), sides(1)];
  const taken = new Uint8Array(cols * rows);
  const slotOk = (s: number) => s >= 0 && !taken[s] && inGrid(s % cols, Math.floor(s / cols));

  function claim(side: number, along: number): number {
    // most go to the inner ring, some to the outer one, so the frame is 1-2 cells and ragged
    const order = r() < 0.4 ? [1, 0] : [0, 1];
    for (const k of order) {
      const sd = rings[k][side];
      const a = along - sd.along0;
      for (let o = 0; o <= 5; o++) {
        for (const s of o ? [a + o, a - o] : [a]) {
          if (s < 0 || s >= sd.pts.length) continue;
          const p = sd.pts[s];
          if (slotOk(p)) {
            taken[p] = 1;
            return p;
          }
        }
      }
    }
    return -1;
  }

  /** jittered lattice walk; mostly toward the target, now and then a sideways step */
  function walk(sx: number, sy: number, tx: number, ty: number): Int32Array {
    const out = [vi(sx, sy)];
    let x = sx, y = sy;
    let px = Math.max(0, tx - sx), mx = Math.max(0, sx - tx), py = Math.max(0, ty - sy), my = Math.max(0, sy - ty);
    const horizMain = px + mx >= py + my;
    let guard = 0;
    while (px + mx + py + my > 0 && guard++ < 400) {
      if (r() < 0.14) {
        // a wobble across the main direction, paid back later
        if (horizMain) (py++, my++);
        else (px++, mx++);
      }
      const tot = px + mx + py + my;
      let pick = r() * tot;
      if ((pick -= px) < 0) (x++, px--);
      else if ((pick -= mx) < 0) (x--, mx--);
      else if ((pick -= py) < 0) (y++, py--);
      else (y--, my--);
      out.push(vi(Math.min(cols - 1, Math.max(0, x)), Math.min(rows - 1, Math.max(0, y))));
    }
    return Int32Array.from(out);
  }

  function timing() {
    if (instant) return { delay: 0, dur: 0 };
    const delay = r() * 90;
    const dur = Math.max(160, WALK - delay - r() * 140);
    return { delay, dur };
  }

  // 1. everything visible inside the rectangle becomes a walker
  const start: { x: number; y: number; v: number; hue: number; d: number }[] = [];
  for (let y = y0; y < y1; y++)
    for (let x = x0; x < x1; x++) {
      const i = ti(x, y);
      const t = life.trail[i];
      const v = life.alive[i] ? 255 : t > 0.4 ? 150 : t > 0.1 ? 90 : 0;
      if (v) start.push({ x, y, v, hue: life.hue[i] * 127, d: Math.min(x - x0, x1 - 1 - x, y - y0, y1 - 1 - y) });
      life.alive[i] = 0;
      life.trail[i] = 0;
    }
  // nearest the edge claim their slots first
  start.sort((a, b) => a.d - b.d || r() - 0.5);
  const tau = 2.5 + Math.min(rw, rh) * 0.05;
  const movers: Mover[] = [];
  for (const c of start) {
    const ds = [c.x - x0, x1 - 1 - c.x, c.y - y0, y1 - 1 - c.y];
    const w = ds.map((d) => Math.exp(-d / tau));
    let pick = r() * (w[0] + w[1] + w[2] + w[3]);
    let side = 0;
    while (side < 3 && (pick -= w[side]) >= 0) side++;
    const sd = rings[0][side];
    const along = Math.round((sd.horiz ? c.x : c.y) + gauss(r) * 2.2);
    const slot = claim(side, along);
    let tx: number, ty: number;
    if (slot >= 0) (tx = slot % cols), (ty = Math.floor(slot / cols));
    else {
      // no room in the frame: walk just past it and fade into the field
      const k = 2 + Math.floor(r() * 2);
      tx = sd.horiz ? along : side === 0 ? x0 - 1 - k : x1 + k;
      ty = sd.horiz ? (side === 2 ? y0 - 1 - k : y1 + k) : along;
      tx = Math.min(cols - 1, Math.max(0, tx));
      ty = Math.min(rows - 1, Math.max(0, ty));
    }
    movers.push({ path: walk(c.x, c.y, tx, ty), ...timing(), v0: c.v, v1: slot >= 0 ? 255 : 0, hue: c.hue, slot });
  }

  // 2. top up from just outside: the inner ring mostly, the outer one here and there, leaving
  // gaps so it reads as grown rather than drawn
  const FILL = [0.6, 0.35];
  for (let k = 0; k < 2; k++)
  for (let s = 0; s < 4; s++) {
    const sd = rings[k][s];
    for (let a = 0; a < sd.pts.length; a++) {
      const p = sd.pts[a];
      if (!slotOk(p) || r() > FILL[k]) continue;
      const px = p % cols, py = Math.floor(p / cols);
      // look outward for a live cell to pull in; otherwise one is born a little way out
      let from = -1;
      for (let d = 3 - k; d <= 8 && from < 0; d++)
        for (const lat of [0, 1, -1, 2, -2]) {
          const qx = px + sd.nx * d + (sd.horiz ? lat : 0), qy = py + sd.ny * d + (sd.horiz ? 0 : lat);
          if (!inGrid(qx, qy) || inside(qx, qy)) continue;
          const q = vi(qx, qy);
          if (taken[q]) continue;
          if (life.alive[ti(qx, qy)]) {
            from = q;
            break;
          }
        }
      let v0 = 255;
      if (from < 0) {
        const d = 2 + Math.floor(r() * 4);
        const qx = Math.min(cols - 1, Math.max(0, px + sd.nx * d)), qy = Math.min(rows - 1, Math.max(0, py + sd.ny * d));
        from = vi(qx, qy);
        v0 = 90;
      } else {
        const t = ti(from % cols, Math.floor(from / cols));
        life.alive[t] = 0;
        life.trail[t] = 0;
      }
      taken[p] = 1;
      taken[from] = 1;
      const fx = from % cols, fy = Math.floor(from / cols);
      movers.push({ path: walk(fx, fy, px, py), ...timing(), v0, v1: 255, hue: life.hue[ti(px, py)] * 127, slot: p });
    }
  }

  const settleAt = now + (instant ? 0 : WALK);
  // after release: each frame cell walks back in to one of a few seed spots, where they land
  // as small soups and Life takes over from there
  let back: { path: Int32Array; delay: number; dur: number; v: number; hue: number }[] | null = null;
  let backAt = 0;
  let committed = false;

  const at = (m: Mover, now: number) => {
    const t = instant ? 1 : Math.min(1, Math.max(0, (now - (settleAt - WALK) - m.delay) / m.dur));
    const e = ease(t);
    const p = m.path[Math.min(m.path.length - 1, Math.round(e * (m.path.length - 1)))];
    const v = m.v1 ? m.v0 + (255 - m.v0) * e : m.v0 * (1 - e);
    return { p, v: v < 40 ? 0 : v >= 200 ? 255 : v >= 120 ? 150 : 90 };
  };
  const backPos = (b: NonNullable<typeof back>[number], now: number) => {
    const t = Math.min(1, Math.max(0, (now - backAt - b.delay) / b.dur));
    return b.path[Math.min(b.path.length - 1, Math.round(ease(t) * (b.path.length - 1)))];
  };

  function commit() {
    if (committed || !back) return;
    committed = true;
    for (const b of back) {
      const p = b.path[b.path.length - 1];
      const i = ti(p % cols, Math.floor(p / cols));
      if (b.v === 255) {
        life.alive[i] = 1;
        life.trail[i] = 1;
      } else life.trail[i] = Math.max(life.trail[i], b.v === 90 ? 0.2 : 0.6);
    }
  }

  return {
    rect,
    settleAt,
    walking: (now) => (back ? !committed : !instant && now < settleAt),
    hold() {
      if (back) return;
      for (let y = y0; y < y1; y++)
        for (let x = x0; x < x1; x++) {
          const i = ti(x, y);
          life.alive[i] = 0;
          life.trail[i] = 0;
        }
    },
    paint(cells, now) {
      if (committed) return;
      if (back) {
        for (const b of back) {
          const o = backPos(b, now) * 4;
          cells[o] = b.v;
          cells[o + 1] = b.hue;
          cells[o + 2] = 0;
        }
        return;
      }
      for (let y = y0; y < y1; y++) cells.fill(0, (y * cols + x0) * 4, (y * cols + x1) * 4);
      for (const m of movers) {
        const { p, v } = at(m, now);
        if (!v) continue;
        const o = p * 4;
        cells[o] = v;
        cells[o + 1] = m.hue;
        cells[o + 2] = 0;
      }
    },
    release(now, quick = false) {
      if (back) return;
      backAt = now;
      // seed spots spread over the room; each walker heads for the nearest few at random
      const n = Math.max(3, Math.round(((rw + rh) * 2) / 45));
      const seeds = Array.from({ length: n }, () => ({
        x: x0 + 4 + Math.floor(r() * Math.max(1, rw - 8)),
        y: y0 + 4 + Math.floor(r() * Math.max(1, rh - 8)),
      }));
      back = [];
      for (const m of movers) {
        const { p, v } = at(m, now);
        if (!v) continue;
        const px = p % cols, py = Math.floor(p / cols);
        const near = seeds
          .map((q) => ({ q, d: Math.hypot(q.x - px, q.y - py) }))
          .sort((a, b) => a.d - b.d)
          .slice(0, 3);
        const q = near[Math.floor(r() * r() * near.length)].q;
        const tx = Math.min(cols - 1, Math.max(0, Math.round(q.x + gauss(r) * 3)));
        const ty = Math.min(rows - 1, Math.max(0, Math.round(q.y + gauss(r) * 3)));
        const delay = quick ? 0 : r() * 80;
        back.push({ path: quick ? Int32Array.of(vi(tx, ty)) : walk(px, py, tx, ty), delay, dur: quick ? 0 : Math.max(160, BACK - delay - r() * 120), v: v === 255 ? 255 : v, hue: m.hue });
      }
      if (quick) commit();
    },
    done: (now) => committed || (!!back && now >= backAt + BACK),
    commit,
  };
}
