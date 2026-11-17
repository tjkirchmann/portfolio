// AC-28 greens only, AC-31 no cells outside the rounded art panel.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import sharp from 'sharp';
import { check, sleep } from './lib.mjs';

const root = process.cwd();
const SHOTS = join(root, '.orchestration/reports/site-shots');
const REMOVED = ['bbc368', '9f814e', '85692c', '73984f', 'c9a46a', '--gold', '--copper', '--bronze', '--leaf', 'color-gold', 'color-copper', 'color-bronze', 'color-leaf'];
const HUE = [120, 200]; // green to teal
const CHROMA = 24; // below this (0-255 max-min) a colour counts as neutral

function hue(r, g, b) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), c = mx - mn;
  if (!c) return { c, h: 0 };
  let h;
  if (mx === r) h = ((g - b) / c) % 6;
  else if (mx === g) h = (b - r) / c + 2;
  else h = (r - g) / c + 4;
  h *= 60;
  if (h < 0) h += 360;
  return { c, h };
}
const offBand = (r, g, b) => {
  const { c, h } = hue(r, g, b);
  return c > CHROMA && (h < HUE[0] || h > HUE[1]);
};

function walk(dir, out = []) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) { if (!(f === 'art' && dir.endsWith('public'))) walk(p, out); }
    else if (/\.(astro|ts|mjs|js|css|md|yaml|svg|json)$/.test(f)) out.push(p);
  }
  return out;
}

async function pixelScan(buf) {
  const { data, info } = await sharp(buf).raw().toBuffer({ resolveWithObject: true });
  let bad = 0, worst = null;
  for (let i = 0; i < data.length; i += info.channels * 2) {
    if (offBand(data[i], data[i + 1], data[i + 2])) {
      bad++;
      if (!worst) worst = `${data[i]},${data[i + 1]},${data[i + 2]} at px ${i / info.channels}`;
    }
  }
  return { bad, worst, total: data.length / info.channels / 2 };
}

export async function paletteTests(browser, base, log, pages) {
  // source grep
  const files = [...walk(join(root, 'src')), ...walk(join(root, 'public')), join(root, 'astro.config.mjs')];
  const hits = [];
  for (const f of files) {
    const t = readFileSync(f, 'utf8').toLowerCase();
    for (const r of REMOVED) if (t.includes(r)) hits.push(`${relative(root, f)}: ${r}`);
  }
  log.push(`AC-28 grep for ${REMOVED.join(' ')} in ${files.length} files: ${hits.length ? hits.join('; ') : 'no matches'}`);
  check('AC-28', 'source grep: removed colours and tokens appear nowhere in src/, public/ (minus art), astro.config', hits.length === 0, hits.slice(0, 4).join('; '));

  // computed colours and pixels on every page, desktop and mobile
  const computedBad = [];
  const pixelBad = [];
  for (const [vw, vh, tag] of [[1440, 900, 'desktop'], [390, 844, 'mobile']]) {
    const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    for (const p of pages) {
      await page.goto(base + p);
      await sleep(1200);
      const r = await page.evaluate(({ HUE, CHROMA }) => {
        const cv = document.createElement('canvas').getContext('2d');
        const norm = (v) => {
          cv.fillStyle = '#000';
          cv.fillStyle = v;
          const s = cv.fillStyle;
          if (s.startsWith('#')) return [parseInt(s.slice(1, 3), 16), parseInt(s.slice(3, 5), 16), parseInt(s.slice(5, 7), 16), 1];
          const m = s.match(/[\d.]+/g).map(Number);
          return [m[0], m[1], m[2], m[3] ?? 1];
        };
        const hueOf = (r, g, b) => {
          const mx = Math.max(r, g, b), mn = Math.min(r, g, b), c = mx - mn;
          if (!c) return [0, 0];
          let h = mx === r ? ((g - b) / c) % 6 : mx === g ? (b - r) / c + 2 : (r - g) / c + 4;
          h *= 60;
          return [c, h < 0 ? h + 360 : h];
        };
        const props = ['color', 'background-color', 'border-top-color', 'border-bottom-color', 'border-left-color', 'border-right-color', 'outline-color', 'text-decoration-color', 'fill', 'stroke', 'column-rule-color', 'caret-color'];
        const bad = [];
        let n = 0;
        for (const el of document.querySelectorAll('*')) {
          const cs = getComputedStyle(el);
          for (const pr of props) {
            const v = cs.getPropertyValue(pr);
            if (!v || v === 'none' || v.startsWith('url') || v === 'auto') continue;
            const [r, g, b, a] = norm(v);
            n++;
            if (a === 0) continue;
            const [c, h] = hueOf(r, g, b);
            if (c > CHROMA && (h < HUE[0] || h > HUE[1])) bad.push(`${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : ''} ${pr}: ${v}`);
          }
        }
        // canvases (the simulation)
        let cbad = 0;
        document.querySelectorAll('canvas[data-dither]').forEach((c) => {
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          for (let i = 0; i < d.length; i += 4) {
            const [cc, h] = hueOf(d[i], d[i + 1], d[i + 2]);
            if (cc > CHROMA && (h < HUE[0] || h > HUE[1])) cbad++;
          }
        });
        return { bad, n, cbad };
      }, { HUE, CHROMA });
      computedBad.push(...r.bad.map((b) => `${tag} ${p} ${b}`));
      if (r.cbad) computedBad.push(`${tag} ${p} canvas: ${r.cbad} off-band pixels`);
      const buf = await page.screenshot({ fullPage: tag === 'desktop' && p === '/blocks/' });
      const px = await pixelScan(buf);
      if (px.bad) pixelBad.push(`${tag} ${p}: ${px.bad} px, first ${px.worst}`);
      log.push(`AC-28 ${tag} ${p}: ${r.n} computed colours checked, ${r.bad.length} off-band; canvas off-band ${r.cbad}; screenshot ${px.total} px sampled, ${px.bad} off-band`);
    }
    await ctx.close();
  }
  check('AC-28', `computed colours on ${pages.length} pages x 2 viewports and every canvas frame stay in the green-teal band (hue ${HUE[0]}-${HUE[1]}, neutrals allowed)`, computedBad.length === 0, computedBad.slice(0, 4).join('; '));
  check('AC-28', 'screenshot pixels of every page stay in the green-teal band', pixelBad.length === 0, pixelBad.slice(0, 4).join('; '));

  // AC-31: nothing outside the rounded art panel
  for (const [vw, vh, p, name] of [[1440, 900, '/', 'home-desktop'], [1280, 720, '/', 'home-1280'], [1440, 900, '/blog/first-post/', 'post-desktop'], [390, 844, '/', 'home-mobile'], [390, 844, '/blog/first-post/', 'post-mobile']]) {
    const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    await page.goto(base + p);
    await sleep(1500);
    const geo = await page.evaluate(() => {
      const inner = document.querySelector('.split-art-inner');
      const outer = document.querySelector('[data-split-art]').getBoundingClientRect();
      const r = inner.getBoundingClientRect();
      return { o: outer.toJSON(), r: r.toJSON(), rad: parseFloat(getComputedStyle(inner).borderTopLeftRadius) };
    });
    const buf = await page.screenshot();
    const { data, info } = await sharp(buf).raw().toBuffer({ resolveWithObject: true });
    const s = info.width / vw;
    let outside = 0, coloured = 0;
    const { o, r, rad } = geo;
    const inRounded = (x, y) => {
      if (x < r.left || x > r.right || y < r.top || y > r.bottom) return false;
      const cx = Math.min(Math.max(x, r.left + rad), r.right - rad), cy = Math.min(Math.max(y, r.top + rad), r.bottom - rad);
      return Math.hypot(x - cx, y - cy) <= rad;
    };
    for (let y = Math.max(0, Math.floor(o.top)); y < Math.min(vh, o.bottom); y += 0.5) {
      for (let x = Math.max(0, Math.floor(o.left)); x < Math.min(vw, o.right); x += 0.5) {
        // keep a 1px band at the edge for antialiasing of the clip itself
        const near = inRounded(x - 1, y) || inRounded(x + 1, y) || inRounded(x, y - 1) || inRounded(x, y + 1);
        if (inRounded(x, y) || near) continue;
        if (y < 0 || x < 0) continue;
        outside++;
        const i = (Math.floor(y * s) * info.width + Math.floor(x * s)) * info.channels;
        const { c } = hue(data[i], data[i + 1], data[i + 2]);
        if (c > 12 || data[i + 1] > 40) coloured++;
      }
    }
    if (name === 'home-desktop' || name === 'home-mobile') await page.screenshot({ path: join(SHOTS, `ac31-${name}.png`) });
    log.push(`AC-31 ${name}: ${outside} sample points between the pane edge and the rounded panel, ${coloured} coloured`);
    check('AC-31', `${name}: no cells outside the rounded art panel`, coloured === 0 && outside > 100, `${coloured} coloured of ${outside} points outside`);
    // and only whole cells: the canvas sits inside the panel
    const fit = await page.evaluate(() => {
      const c = document.querySelector('[data-split-art] canvas[data-dither]').getBoundingClientRect();
      const b = document.querySelector('[data-split-art] [data-dither-box]').getBoundingClientRect();
      return c.left >= b.left - 0.01 && c.top >= b.top - 0.01 && c.right <= b.right + 0.01 && c.bottom <= b.bottom + 0.01;
    });
    check('AC-31', `${name}: only whole cells, the grid sits inside its box`, fit);
    await ctx.close();
  }
}
