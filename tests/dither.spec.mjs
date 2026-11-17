// AC-19..22: the dithered life simulation.
import { join } from 'node:path';
import { check, sleep } from './lib.mjs';

const SHOTS = join(process.cwd(), '.orchestration/reports/site-shots');
const MODES = ['life'];
// allowed simulation colours: bg, and emerald / teal / deep at any intensity over bg
const ALLOWED = ['10,12,11'];

const readCanvas = (page, sel) =>
  page.evaluate((sel) => {
    const c = document.querySelector(sel);
    const r = c.getBoundingClientRect();
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    const colours = new Map();
    let empty = 0;
    for (let i = 0; i < d.length; i += 4) {
      const k = `${d[i]},${d[i + 1]},${d[i + 2]}`;
      colours.set(k, (colours.get(k) || 0) + 1);
      if (d[i] === 10 && d[i + 1] === 12 && d[i + 2] === 11) empty++;
    }
    // structure at a coarse scale: fill fraction per 8x8 block. Masses on black give blocks that are
    // full next to blocks that are empty (high spread); static noise at the same coverage gives
    // nearly equal blocks (spread about 0.06).
    const B = 8, fills = [];
    for (let by = 0; by + B <= c.height; by += B) for (let bx = 0; bx + B <= c.width; bx += B) {
      let on = 0;
      for (let y = by; y < by + B; y++) for (let x = bx; x < bx + B; x++) { const o = (y * c.width + x) * 4; if (!(d[o] === 10 && d[o + 1] === 12)) on++; }
      fills.push(on / (B * B));
    }
    const mean = fills.reduce((a, b) => a + b, 0) / fills.length;
    const clumped = fills.filter((f) => f > 0.5).length / fills.length;
    const maxFill = Math.max(...fills);
    const spread = Math.sqrt(fills.reduce((a, b) => a + (b - mean) ** 2, 0) / fills.length);
    return {
      w: c.width, h: c.height, cssW: r.width, cssH: r.height, dpr: devicePixelRatio,
      cell: Number(c.dataset.cell), rendering: getComputedStyle(c).imageRendering,
      steps: Number(c.dataset.steps || 0), avgMs: Number(c.dataset.avgMs || 0), maxMs: Number(c.dataset.maxMs || 0),
      empty: empty / (d.length / 4), colours: [...colours.entries()].sort((a, b) => b[1] - a[1]).map(([k, n]) => [k, +(n / (d.length / 4)).toFixed(3)]),
      coherence: spread, clumped, maxFill,
      hash: [...d].reduce((h, v, i) => (i % 4 === 3 ? h : (h * 31 + v) >>> 0), 7),
    };
  }, sel);

// emerald, teal, deep mixed over bg at intensity t
const GREENS = [[118, 200, 165], [87, 157, 135], [50, 110, 84]];
const BGC = [10, 12, 11];
function greenAt(t) {
  return GREENS.map((c) => c.map((v, j) => Math.round(BGC[j] + (v - BGC[j]) * t)).join(','));
}

export async function ditherTests(browser, base, log) {
  // ---- three modes on /blocks: crisp cells, steps/s, cost, empty space, colour, 0/5/20s frames
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 2600 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    await page.goto(base + '/blocks/');
    await sleep(150);
    const sel = (m) => `[data-test="dither-${m}"] canvas[data-dither]`;
    const t0 = {}, t5 = {}, t20 = {};
    for (const m of MODES) {
      t0[m] = await readCanvas(page, sel(m));
      await page.locator(`[data-test="dither-${m}"]`).screenshot({ path: join(SHOTS, `dither-${m}-00s.png`) });
    }
    await sleep(4800);
    for (const m of MODES) {
      t5[m] = await readCanvas(page, sel(m));
      await page.locator(`[data-test="dither-${m}"]`).screenshot({ path: join(SHOTS, `dither-${m}-05s.png`) });
    }
    const s5 = Date.now();
    await sleep(15000);
    const span = (Date.now() - s5) / 1000;
    for (const m of MODES) {
      t20[m] = await readCanvas(page, sel(m));
      await page.locator(`[data-test="dither-${m}"]`).screenshot({ path: join(SHOTS, `dither-${m}-20s.png`) });
    }
    for (const m of MODES) {
      const a = t0[m], b = t5[m], c = t20[m];
      const rate = (c.steps - b.steps) / span;
      const cellCss = a.cssW / a.w;
      log.push(`dither ${m}: grid ${a.w}x${a.h} (one automaton cell per square), cell ${cellCss.toFixed(3)}css (${(cellCss * a.dpr).toFixed(2)} device px), ${rate.toFixed(2)} steps/s, avg ${c.avgMs}ms max ${c.maxMs}ms per step (step+draw), empty ${a.empty.toFixed(3)} / ${b.empty.toFixed(3)} / ${c.empty.toFixed(3)}, 8x8 blocks over half full ${a.clumped.toFixed(3)} / ${b.clumped.toFixed(3)} / ${c.clumped.toFixed(3)} (max block fill ${Math.max(a.maxFill, b.maxFill, c.maxFill).toFixed(2)}), colours ${JSON.stringify(c.colours)}`);
      check('AC-19', `${m}: square cells on whole device pixels, pixelated`, Math.abs(cellCss * a.dpr - Math.round(cellCss * a.dpr)) < 0.01 && a.rendering === 'pixelated' && Math.abs(cellCss - a.cell) < 0.5, `${(cellCss * a.dpr).toFixed(2)} device px, ${a.rendering}`);
      const allowed = new Set([...ALLOWED, ...greenAt(1)]);
      const extra = [...new Set([...a.colours, ...b.colours, ...c.colours].map(([k]) => k))].filter((k) => !allowed.has(k));
      check('AC-29', `${m}: no blur or upscale: every pixel is bg, emerald, teal or deep exactly`, extra.length === 0, extra.length ? `unexpected ${extra.slice(0, 4).join(' ')}` : `${new Set([...a.colours, ...c.colours].map(([k]) => k)).size} distinct colours`);
      check('AC-29', `${m}: at least 60% pure --bg at 0s, 5s, 20s`, [a, b, c].every((f) => f.empty >= 0.6), [a, b, c].map((f) => f.empty.toFixed(3)).join(' / '));
      check('AC-29', `${m}: no filled regions (under 5% of 8x8 blocks more than half full, none over 75%)`, [a, b, c].every((f) => f.clumped < 0.05 && f.maxFill <= 0.75), [a, b, c].map((f) => `${f.clumped.toFixed(3)} (max ${f.maxFill.toFixed(2)})`).join(' / '));
      check('AC-22', `${m}: 8-15 steps per second`, rate >= 8 && rate <= 15, `${rate.toFixed(2)}/s over ${span.toFixed(1)}s`);
      check('AC-22', `${m}: main-thread cost under 2ms per step (average)`, c.avgMs < 2, `avg ${c.avgMs}ms, max ${c.maxMs}ms (step + draw + putImageData)`);
      check('AC-22', `${m}: the field evolves (frame changes 0s -> 5s -> 20s)`, a.hash !== b.hash && b.hash !== c.hash);
      const names = new Set([...a.colours, ...b.colours, ...c.colours].map(([k]) => ['emerald', 'teal', 'deep'][greenAt(1).indexOf(k)]).filter(Boolean));
      check('AC-29', `${m}: live cells emerald, trails teal and deep`, names.has('emerald') && names.has('teal') && names.has('deep'), [...names].join(', '));
    }
    await ctx.close();
  }

  // ---- seeding: each page its own pattern; same page twice gives the same start
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    const first = {};
    for (const p of ['/', '/blog/', '/blog/first-post/', '/blog/second-post/']) {
      await page.goto(base + p);
      first[p] = (await readCanvas(page, '[data-split-art] canvas[data-dither]')).hash;
    }
    await page.goto(base + '/');
    const again = (await readCanvas(page, '[data-split-art] canvas[data-dither]')).hash;
    check('AC-22', 'seeded per page: 4 pages, 4 different patterns', new Set(Object.values(first)).size === 4, JSON.stringify(first));
    check('AC-22', 'seeded: same page reloads to the same pattern', again === first['/']);
    // reduced motion: one settled frame, never steps
    const r0 = await readCanvas(page, '[data-split-art] canvas[data-dither]');
    await sleep(2000);
    const r1 = await readCanvas(page, '[data-split-art] canvas[data-dither]');
    await page.screenshot({ path: join(SHOTS, 'reduced-motion-home-dither.png') });
    await page.goto(base + '/blocks/');
    for (const m of MODES) {
      const f = await readCanvas(page, `[data-test="dither-${m}"] canvas[data-dither]`);
      check('AC-22', `${m}: first frame is pre-evolved (0 steps taken, structure already there)`, f.steps === 0 && f.empty < 0.98 && f.empty >= 0.6 && f.colours.length >= 3, `steps ${f.steps}, empty ${f.empty.toFixed(3)}, ${f.colours.length} colours`);
    }
    await page.goto(base + '/');
    check('AC-22', 'reduced motion: settled frame shown, 0 steps in 2s', r1.steps === 0 && r0.hash === r1.hash && r0.empty < 0.98, `steps ${r1.steps}, empty ${r0.empty.toFixed(2)}`);
    await ctx.close();
  }

  // ---- pauses: off-screen, hidden tab, mobile dissolved
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    await page.goto(base + '/blocks/');
    const sel = '[data-test="dither-life"] canvas[data-dither]';
    const steps = () => page.evaluate((s) => Number(document.querySelector(s).dataset.steps || 0), sel);
    await page.locator('[data-test="dither-life"]').scrollIntoViewIfNeeded();
    await sleep(1200);
    const vis0 = await steps();
    await sleep(1000);
    const vis1 = await steps();
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await sleep(300);
    const off0 = await steps();
    await sleep(1500);
    const off1 = await steps();
    check('AC-22', 'steps while visible', vis1 - vis0 >= 7, `${vis1 - vis0} steps in 1s`);
    check('AC-22', 'pauses when off-screen', off1 === off0, `${off1 - off0} steps in 1.5s off-screen`);

    await page.goto(base + '/');
    await sleep(1200);
    const hsel = '[data-split-art] canvas[data-dither]';
    const hs = () => page.evaluate((s) => Number(document.querySelector(s).dataset.steps || 0), hsel);
    const hA = await hs();
    await sleep(1000);
    const h0 = await hs();
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await sleep(100);
    const h1 = await hs();
    await sleep(1500);
    const h2 = await hs();
    await page.evaluate(() => {
      delete document.hidden;
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await sleep(1000);
    const h3 = await hs();
    check('AC-22', 'pauses when the tab is hidden, resumes after', h2 === h1 && h3 > h2 && h0 - hA >= 7, `visible +${h0 - hA} in 1s, hidden +${h2 - h1} in 1.5s, back +${h3 - h2} in 1s`);
    await ctx.close();
  }
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    await page.goto(base + '/blog/first-post/');
    await sleep(1000);
    const hs = () => page.evaluate(() => Number(document.querySelector('[data-split-art] canvas[data-dither]').dataset.steps || 0));
    await page.evaluate(() => window.scrollTo(0, 300));
    await sleep(400);
    const d0 = await hs();
    await sleep(1500);
    const d1 = await hs();
    await page.evaluate(() => window.scrollTo(0, 0));
    await sleep(1200);
    const d2 = await hs();
    check('AC-22', 'mobile: pauses while the art is dissolved, resumes at the top', d1 === d0 && d2 > d1, `dissolved +${d1 - d0} in 1.5s, back at top +${d2 - d1}`);
    await ctx.close();
  }
}
