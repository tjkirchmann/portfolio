// Browser self-test against the built site. Saves screenshots to .orchestration/reports/site-shots/.
import { chromium, firefox, webkit } from 'playwright';
import sharp from 'sharp';
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'yaml';
import { serve } from './serve.mjs';
import { check, skip, sleep } from './lib.mjs';

const root = process.cwd();
const dist = join(root, 'dist');
const SHOTS = join(root, '.orchestration/reports/site-shots');
const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };
const PALETTE = { ink: 'rgb(233, 236, 232)', emerald: 'rgb(118, 200, 165)', gold: 'rgb(187, 195, 104)', teal: 'rgb(87, 157, 135)' };
const POST = '/blog/first-post/';

const shot = (page, name, opts = {}) => page.screenshot({ path: join(SHOTS, `${name}.png`), ...opts });

function htmlPages(dir, base = '') {
  const out = [];
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (f.startsWith('.') || f === '_astro' || f === 'art') continue;
    if (statSync(p).isDirectory()) out.push(...htmlPages(p, `${base}/${f}`));
    else if (f === 'index.html') out.push(`${base}/`);
  }
  return out;
}

async function stats(buf) {
  const s = await sharp(buf).stats();
  const mean = (s.channels[0].mean + s.channels[1].mean + s.channels[2].mean) / 3;
  const sd = (s.channels[0].stdev + s.channels[1].stdev + s.channels[2].stdev) / 3;
  return { mean, sd };
}

// Counts rAF calls and layout shifts from page start.
const INIT = () => {
  window.__raf = 0;
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => {
    window.__raf++;
    return raf(cb);
  };
  window.__cls = 0;
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value;
    }).observe({ type: 'layout-shift', buffered: true });
  } catch {}
  window.__vt = 0;
  if (document.startViewTransition) {
    const svt = document.startViewTransition.bind(document);
    document.startViewTransition = (...a) => {
      window.__vt++;
      return svt(...a);
    };
  }
  window.__artLog = [];
  new MutationObserver((ms) => {
    for (const m of ms) {
      if (m.attributeName === 'data-state' && m.target.matches?.('[data-art]')) {
        window.__artLog.push({ state: m.target.dataset.state, t: performance.now(), instant: m.target.hasAttribute('data-instant') });
      }
    }
  }).observe(document, { attributes: true, subtree: true, attributeFilter: ['data-state'] });
};

const paneState = (page) =>
  page.evaluate(() => {
    const p = document.querySelector('[data-split-art]');
    const cs = getComputedStyle(p);
    const v = p.querySelector('video');
    const blur = /blur\(([\d.]+)px\)/.exec(cs.filter);
    return {
      opacity: Number(cs.opacity),
      blur: blur ? Number(blur[1]) : 0,
      visibility: cs.visibility,
      paused: v ? v.paused : null,
      scrollY: window.scrollY,
      hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      cls: window.__cls,
    };
  });

async function scrollTo(page, y) {
  await page.evaluate((y) => window.scrollTo(0, y), y);
  await sleep(350);
}

export async function siteTests(log, text) {
  // AC-1
  const pages = htmlPages(dist);
  log.push('$ ls dist', readdirSync(dist).join('  '), 'pages: ' + pages.join('  '));
  check('AC-1', 'dist has /, /blog/, /blocks/', ['/', '/blog/', '/blocks/'].every((p) => pages.includes(p)));
  const posts = readdirSync(join(root, 'src/content/blog')).filter((d) => existsSync(join(root, 'src/content/blog', d, 'index.md')));
  check('AC-1', 'one page per sample post', posts.every((p) => pages.includes(`/blog/${p}/`)), posts.join(', '));

  // AC-11: built HTML of the sample post
  const postHtml = readFileSync(join(dist, 'blog/first-post/index.html'), 'utf8');
  const img = /<figure><img[^>]+>/.exec(postHtml)?.[0] || '';
  log.push('built <figure> in dist/blog/first-post/index.html:', /<figure>.*?<\/figure>/s.exec(postHtml)?.[0] || '(none)');
  check('AC-11', 'post image has srcset', /srcset="[^"]+ 360w, [^"]+"/.test(img));
  check('AC-11', 'post image is lazy with width and height', /loading="lazy"/.test(img) && /width="\d+"/.test(img) && /height="\d+"/.test(img));
  check('AC-11', 'titled image gets alt as figcaption', /<figcaption>A wireframe sphere inside a ring<\/figcaption>/.test(postHtml));
  check('AC-11', 'image sits between paragraphs', /<\/p>\s*<figure>.*?<\/figure>\s*<p>/s.test(postHtml));

  const server = await serve(dist);
  const base = server.url;
  const browser = await chromium.launch();
  try {
    const ctx = await browser.newContext({ viewport: DESKTOP, deviceScaleFactor: 2 });
    await ctx.addInitScript(INIT);
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));

    // AC-2: home
    await page.goto(base + '/');
    await page.waitForSelector('[data-art][data-state="ready"]', { timeout: 8000 }).catch(() => {});
    await sleep(500);
    await shot(page, 'desktop-home');
    const site = parse(readFileSync(join(root, 'src/content/site.yaml'), 'utf8'));
    const home = await page.evaluate(() => {
      const main = document.querySelector('main').getBoundingClientRect();
      const art = document.querySelector('[data-split-art]').getBoundingClientRect();
      return {
        textLeft: main.x < art.x,
        h1: document.querySelector('main h1')?.textContent.trim(),
        role: document.querySelector('main .page-sub')?.textContent.trim(),
        rows: [...document.querySelectorAll('main .rows li')].map((l) => l.textContent.replace(/\s+/g, ' ').trim()),
        links: [...document.querySelectorAll('main .linkrow a')].map((a) => [a.textContent.trim(), a.getAttribute('href')]),
        linksBottom: document.querySelector('main .linkrow').getBoundingClientRect().bottom > window.innerHeight * 0.8,
      };
    });
    check('AC-2', 'home: text pane left, art pane right', home.textLeft);
    check('AC-2', 'home: name and role from site.yaml', home.h1 === site.name && home.role === site.role);
    check('AC-2', 'home: entry rows from site.yaml', home.rows.length === site.entries.length && site.entries.every((e, i) => home.rows[i].startsWith(e.label)));
    check('AC-2', 'home: link row from site.yaml, at the bottom', home.linksBottom && site.links.every((l, i) => home.links[i]?.[0] === l.label && home.links[i]?.[1] === l.href));

    // Focus states, with real keyboard input
    await page.keyboard.press('Tab');
    await sleep(100);
    const focus = await page.evaluate(() => {
      const el = document.activeElement;
      const cs = getComputedStyle(el);
      return { text: el.textContent.trim().replace(/\s+/g, ' '), outline: `${cs.outlineStyle} ${cs.outlineWidth} ${cs.outlineColor}` };
    });
    await shot(page, 'desktop-home-focus');
    check('POLISH', 'keyboard focus is visible (Tab on home)', /solid 2px/.test(focus.outline), `${focus.text}: ${focus.outline}`);

    // AC-8: dither drawn at DPR, static
    const dither = await page.evaluate(async () => {
      const c = document.querySelector('[data-split-art] canvas[data-dither]');
      const r = c.getBoundingClientRect();
      const ctx = c.getContext('2d');
      const d = ctx.getImageData(0, 0, c.width, c.height).data;
      const colours = new Set();
      for (let i = 0; i < d.length; i += 4 * 97) colours.add(`${d[i]},${d[i + 1]},${d[i + 2]}`);
      window.__raf = 0;
      await new Promise((res) => setTimeout(res, 1200));
      return { w: c.width, h: c.height, cw: r.width, ch: r.height, dpr: devicePixelRatio, colours: colours.size, raf: window.__raf };
    });
    check('AC-8', 'dither canvas sized at device pixel ratio', dither.w === Math.round(dither.cw * dither.dpr) && dither.h === Math.round(dither.ch * dither.dpr), `${dither.w}x${dither.h} for ${dither.cw}x${dither.ch} @${dither.dpr}x`);
    check('AC-8', 'dither has several palette colours', dither.colours >= 3, `${dither.colours} colours sampled`);
    check('AC-8', 'no animation loop while idle (0 rAF calls in 1.2s)', dither.raf === 0, `${dither.raf} calls`);

    // AC-6: art over dither on /blocks
    await page.goto(base + '/blocks/');
    await page.waitForSelector('[data-test="art-over-dither"] [data-art][data-state="ready"]', { timeout: 8000 }).catch(() => {});
    await sleep(600);
    await shot(page, 'desktop-blocks', { fullPage: true });
    const stage = page.locator('[data-test="art-over-dither"]');
    await stage.scrollIntoViewIfNeeded();
    await sleep(300);
    const stageBuf = await stage.screenshot({ path: join(SHOTS, 'blocks-art-over-dither.png') });
    const blend = await page.evaluate(() => {
      const art = document.querySelector('[data-test="art-over-dither"] [data-art]');
      const v = art.querySelector('video');
      const r = art.getBoundingClientRect();
      const s = art.parentElement.getBoundingClientRect();
      return { mode: getComputedStyle(v).mixBlendMode, slug: art.dataset.art, top: r.top - s.top, left: r.left - s.left, w: r.width, h: r.height, sw: s.width };
    });
    // sample the top band inside the art box (dither is brightest at the top of this stage)
    const { data, info } = await sharp(stageBuf).raw().toBuffer({ resolveWithObject: true });
    const scale = info.width / blend.sw;
    let sum = 0, n = 0;
    for (let y = Math.round((blend.top + 4) * scale); y < Math.round((blend.top + 24) * scale); y++) {
      for (let x = Math.round((blend.left + blend.w * 0.05) * scale); x < Math.round((blend.left + blend.w * 0.3) * scale); x++) {
        const o = (y * info.width + x) * info.channels;
        sum += data[o + 1];
        n++;
      }
    }
    const green = sum / n;
    check('AC-6', 'video uses mix-blend-mode: screen', blend.mode === 'screen');
    check('AC-6', 'dither shows through the black matte inside the art box', green > 60, `mean green ${green.toFixed(0)} in the art box top band`);
    check('AC-5', 'missing art folder falls back to _placeholder', blend.slug === '_placeholder');

    // AC-12: monospace only inside pre / code, on every built page
    let monoBad = [];
    let codeOk = true;
    for (const p of pages) {
      await page.goto(base + p);
      const r = await page.evaluate(() => {
        const bad = [];
        const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        let codeMono = true;
        while (w.nextNode()) {
          const t = w.currentNode;
          if (!t.textContent.trim()) continue;
          const el = t.parentElement;
          if (!el || el.closest('script, style, noscript')) continue;
          const ff = getComputedStyle(el).fontFamily;
          const mono = /mono|monospace|courier|menlo|consolas/i.test(ff);
          const inCode = !!el.closest('pre, code');
          if (mono && !inCode) bad.push(`${el.tagName}: "${t.textContent.trim().slice(0, 30)}" -> ${ff}`);
          if (inCode && !mono) codeMono = false;
        }
        return { bad, codeMono };
      });
      monoBad.push(...r.bad.map((b) => `${p} ${b}`));
      codeOk &&= r.codeMono;
    }
    check('AC-12', `no monospace outside pre/code (${pages.length} pages walked)`, monoBad.length === 0, monoBad.slice(0, 3).join('; '));
    check('AC-12', 'pre/code text is monospace', codeOk);

    // AC-18 text dumps
    for (const p of ['/', '/blog/', '/blocks/']) {
      await page.goto(base + p);
      text[p] = await page.evaluate(() => document.body.innerText.replace(/\n{3,}/g, '\n\n').trim());
    }

    // AC-3: blog index + post, mirrored, sticky art
    await page.goto(base + '/blog/');
    await sleep(800);
    await shot(page, 'desktop-blog');
    const idx = await page.evaluate(() => ({
      artLeft: document.querySelector('[data-split-art]').getBoundingClientRect().x < document.querySelector('main').getBoundingClientRect().x,
      back: document.querySelector('[data-split-art] [data-back]')?.getAttribute('href'),
    }));
    check('AC-3', 'blog index: art left, text right', idx.artLeft);
    check('AC-3', 'blog index: back arrow in art pane goes to /', idx.back === '/');

    await page.goto(base + POST);
    await page.waitForSelector('[data-art][data-state="ready"]', { timeout: 8000 }).catch(() => {});
    await sleep(500);
    await shot(page, 'desktop-post-top');
    const before = await page.evaluate(() => ({
      art: document.querySelector('[data-split-art]').getBoundingClientRect().toJSON(),
      title: document.querySelector('main h1').getBoundingClientRect().top,
      back: document.querySelector('[data-split-art] [data-back]')?.getAttribute('href'),
      backTop: document.querySelector('[data-split-art] [data-back]').getBoundingClientRect().top,
      artLeft: document.querySelector('[data-split-art]').getBoundingClientRect().x < document.querySelector('main').getBoundingClientRect().x,
    }));
    await scrollTo(page, 400);
    await shot(page, 'desktop-post-scrolled');
    const after = await page.evaluate(() => ({
      art: document.querySelector('[data-split-art]').getBoundingClientRect().toJSON(),
      title: document.querySelector('main h1').getBoundingClientRect().top,
    }));
    check('AC-3', 'post: art left, text right', before.artLeft);
    check('AC-3', 'post: back arrow goes to /blog/', before.back === '/blog/');
    check('AC-3', 'post: art pane fixed while text scrolls', Math.abs(before.art.top - after.art.top) < 1 && Math.abs(before.art.height - after.art.height) < 1 && after.title < before.title - 300, `art top ${before.art.top}->${after.art.top}, title ${before.title.toFixed(0)}->${after.title.toFixed(0)}`);

    // AC-9: palette in markdown
    await scrollTo(page, 0);
    const colours = await page.evaluate(() => {
      const c = (sel) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el).color : null;
      };
      return {
        body: c('.prose p'),
        bold: c('.prose strong'),
        link: c('.prose p a[href^="http"]'),
        linkDeco: getComputedStyle(document.querySelector('.prose p a[href^="http"]')).textDecorationColor,
        ref: c('.prose [data-footnote-ref]'),
        back: c('.prose .data-footnote-backref'),
      };
    });
    log.push('computed colours on ' + POST + ': ' + JSON.stringify(colours));
    const accents = Object.values(PALETTE).filter((v) => v !== PALETTE.ink);
    check('AC-9', 'body text is --ink', colours.body === PALETTE.ink, colours.body);
    check('AC-9', 'bold is --emerald', colours.bold === PALETTE.emerald, colours.bold);
    check('AC-9', 'links use a palette accent (underline --teal)', colours.linkDeco === PALETTE.teal, `color ${colours.link}, underline ${colours.linkDeco}`);
    check('AC-9', 'footnote marks use --gold', colours.ref === PALETTE.gold, colours.ref);
    check('AC-9', 'footnote back-arrows use --gold', colours.back === PALETTE.gold && accents.includes(colours.back), colours.back);

    // AC-10: footnotes both ways
    await page.click('.prose [data-footnote-ref] >> nth=0');
    await sleep(400);
    const atNote = await page.evaluate(() => {
      const t = document.querySelector(':target');
      const r = t?.getBoundingClientRect();
      return { hash: location.hash, tag: t?.tagName, bg: t ? getComputedStyle(t).backgroundColor : null, inView: r ? r.top >= 0 && r.bottom <= innerHeight : false };
    });
    await shot(page, 'desktop-footnote-target');
    check('AC-10', 'footnote list is numbered at the end', await page.evaluate(() => {
      const f = document.querySelector('.prose section.footnotes');
      return !!f && f.querySelector('ol')?.children.length === 2 && f === f.parentElement.lastElementChild;
    }));
    check('AC-10', 'ref jumps to the footnote', atNote.hash === '#user-content-fn-1' && atNote.tag === 'LI' && atNote.inView, JSON.stringify(atNote));
    check('AC-10', 'footnote target is highlighted', atNote.bg && atNote.bg !== 'rgba(0, 0, 0, 0)', atNote.bg);
    await page.click('#user-content-fn-1 .data-footnote-backref');
    await sleep(400);
    const atRef = await page.evaluate(() => {
      const t = document.querySelector(':target');
      const r = t?.getBoundingClientRect();
      return { hash: location.hash, bg: t ? getComputedStyle(t).backgroundColor : null, inView: r ? r.top >= 0 && r.bottom <= innerHeight : false };
    });
    await shot(page, 'desktop-footnote-back');
    check('AC-10', 'back-arrow jumps to the reference, highlighted', atRef.hash === '#user-content-fnref-1' && atRef.inView && atRef.bg !== 'rgba(0, 0, 0, 0)', JSON.stringify(atRef));

    // AC-11: rendered width = text column, no layout shift from the image
    const imgBox = await page.evaluate(async () => {
      const img = document.querySelector('.prose figure img');
      img.scrollIntoView({ block: 'center' });
      await new Promise((r) => setTimeout(r, 600));
      const col = document.querySelector('.prose').getBoundingClientRect();
      const r = img.getBoundingClientRect();
      return { w: r.width, h: r.height, col: col.width, complete: img.complete, current: img.currentSrc.split('/').pop(), cls: window.__cls };
    });
    check('AC-11', 'image renders at text-column width', Math.abs(imgBox.w - imgBox.col) < 1, `${imgBox.w}px in ${imgBox.col}px column, loaded ${imgBox.current}`);
    check('AC-11', 'no layout shift on the post (CLS < 0.01)', imgBox.cls < 0.01, `CLS ${imgBox.cls.toFixed(4)}`);

    check('AC-16', 'no console errors on desktop pages', errors.length === 0, errors.slice(0, 2).join(' | '));
    await ctx.close();

    // AC-5: throttled video: blurred still first, then crossfade
    {
      const c = await browser.newContext({ viewport: DESKTOP, deviceScaleFactor: 2 });
      await c.addInitScript(INIT);
      const p = await c.newPage();
      await p.route('**/art/**/loop.*', async (route) => {
        await sleep(2000);
        await route.continue();
      });
      await p.goto(base + POST);
      await sleep(700);
      const art = p.locator('[data-split-art] [data-art]');
      await art.screenshot({ path: join(SHOTS, 'art-throttled-before.png') });
      const pre = await p.evaluate(() => {
        const a = document.querySelector('[data-split-art] [data-art]');
        return {
          state: a.dataset.state,
          blurOpacity: getComputedStyle(a.querySelector('.art-blur')).opacity,
          blurSrc: a.querySelector('.art-blur').src.slice(0, 22),
          videoOpacity: getComputedStyle(a.querySelector('video')).opacity,
        };
      });
      await p.waitForSelector('[data-split-art] [data-art][data-state="ready"]', { timeout: 10000 }).catch(() => {});
      await sleep(700);
      await art.screenshot({ path: join(SHOTS, 'art-throttled-after.png') });
      const post = await p.evaluate(() => {
        const a = document.querySelector('[data-split-art] [data-art]');
        const v = a.querySelector('video');
        return { state: a.dataset.state, videoOpacity: getComputedStyle(v).opacity, videoFilter: getComputedStyle(v).filter, blurOpacity: getComputedStyle(a.querySelector('.art-blur')).opacity, playing: !v.paused, log: window.__artLog };
      });
      log.push('throttled video (2s delay): before ' + JSON.stringify(pre), 'after ' + JSON.stringify(post));
      check('AC-5', 'before video: inline blurred still visible, video hidden', pre.state === 'loading' && pre.blurOpacity === '1' && pre.blurSrc.startsWith('data:image/') && pre.videoOpacity === '0', JSON.stringify(pre));
      check('AC-5', 'after canplay: video visible, blur at 0, still faded', post.state === 'ready' && post.videoOpacity === '1' && /blur\(0(px)?\)|none/.test(post.videoFilter) && post.blurOpacity === '0' && post.playing, JSON.stringify({ ...post, log: undefined }));
      const loadingT = post.log.find((l) => l.state === 'loading')?.t;
      const readyT = post.log.find((l) => l.state === 'ready')?.t;
      check('AC-5', 'throttled load crossfades (not instant)', readyT - loadingT > 1500 && !post.log.find((l) => l.state === 'ready').instant, `${(readyT - loadingT).toFixed(0)}ms`);

      // Cached: same context, video now in cache, revisit
      await p.unroute('**/art/**/loop.*');
      await p.goto(base + POST);
      await p.waitForSelector('[data-split-art] [data-art][data-state="ready"]', { timeout: 8000 }).catch(() => {});
      await p.goto(base + POST);
      await p.waitForSelector('[data-split-art] [data-art][data-state="ready"]', { timeout: 8000 }).catch(() => {});
      const cached = await p.evaluate(() => window.__artLog);
      const l = cached.find((x) => x.state === 'loading');
      const r = cached.find((x) => x.state === 'ready');
      const dt = r && l ? r.t - l.t : Infinity;
      log.push('cached revisit art log: ' + JSON.stringify(cached));
      if (dt < 50) check('AC-5', 'cached video: swap with no blur-in (instant)', r.instant, `${dt.toFixed(1)}ms to playable`);
      else skip('AC-5', 'cached video: swap with no blur-in', `video took ${dt.toFixed(0)}ms to become playable on revisit; the instant path was not exercised`);
      await c.close();
    }

    // AC-7: reduced motion
    {
      const c = await browser.newContext({ viewport: DESKTOP, deviceScaleFactor: 2, reducedMotion: 'reduce' });
      await c.addInitScript(INIT);
      const p = await c.newPage();
      const videoReqs = [];
      p.on('request', (r) => /\/loop\.(webm|mp4)/.test(r.url()) && videoReqs.push(r.url()));
      await p.goto(base + '/');
      await sleep(1500);
      await shot(p, 'reduced-motion-home');
      const st = await p.evaluate(() => {
        const a = document.querySelector('[data-art]');
        const poster = a.querySelector('.art-poster');
        return { state: a.dataset.state, posterShown: getComputedStyle(poster).display !== 'none' && poster.complete && poster.naturalWidth > 0, videoShown: getComputedStyle(a.querySelector('video')).display !== 'none', paused: a.querySelector('video').paused };
      });
      check('AC-7', 'reduced motion: still poster shown', st.state === 'still' && st.posterShown, JSON.stringify(st));
      check('AC-7', 'reduced motion: video never plays or loads', st.paused && !st.videoShown && videoReqs.length === 0, `${videoReqs.length} video requests`);
      const cdp = await c.newCDPSession(p);
      await cdp.send('Animation.enable');
      await cdp.send('Animation.setPlaybackRate', { playbackRate: 0.1 });
      await p.click('main .linkrow a[href="/blog/"]');
      await sleep(150);
      const anims = await p.evaluate(() => ({ vt: window.__vt, d: document.getAnimations().filter((a) => a.effect?.pseudoElement?.startsWith('::view-transition')).map((a) => a.effect.getComputedTiming().duration) }));
      await p.waitForURL('**/blog/');
      check('AC-7', 'reduced motion: page transitions disabled', anims.d.every((d) => d <= 1), `startViewTransition calls: ${anims.vt}; view-transition animation durations: [${anims.d.join(', ')}]`);
      await c.close();
    }

    // AC-15: view transitions, three frames, no white/black flash
    {
      const c = await browser.newContext({ viewport: DESKTOP, deviceScaleFactor: 1 });
      await c.addInitScript(INIT);
      const p = await c.newPage();
      await p.goto(base + '/');
      await p.waitForSelector('[data-art][data-state="ready"]', { timeout: 8000 }).catch(() => {});
      await sleep(400);
      const cdp = await c.newCDPSession(p);
      await cdp.send('Animation.enable');
      await cdp.send('Animation.setPlaybackRate', { playbackRate: 0.1 });
      await p.click('main .linkrow a[href="/blog/"]');
      const frames = [];
      for (const [i, wait] of [[1, 200], [2, 1300], [3, 1500]]) {
        await sleep(wait);
        const buf = await p.screenshot({ path: join(SHOTS, `transition-frame-${i}.png`) });
        frames.push(await stats(buf));
      }
      const vt = await p.evaluate(() => ({ vt: window.__vt, groups: document.getAnimations().filter((a) => a.effect?.pseudoElement?.startsWith('::view-transition')).map((a) => a.effect.pseudoElement) }));
      await cdp.send('Animation.setPlaybackRate', { playbackRate: 1 });
      await p.waitForURL('**/blog/');
      log.push('transition frames (mean, stdev of RGB): ' + frames.map((f) => `${f.mean.toFixed(1)}/${f.sd.toFixed(1)}`).join('  '), 'view transition calls: ' + vt.vt);
      check('AC-15', 'navigation uses a view transition', vt.vt >= 1 && vt.groups.length > 0, [...new Set(vt.groups)].join(' '));
      log.push('view-transition pseudo animations mid-navigation: ' + [...new Set(vt.groups)].join(' '));
      check('AC-15', 'no white flash in captured frames', frames.every((f) => f.mean < 120), frames.map((f) => f.mean.toFixed(0)).join(', '));
      check('AC-15', 'no blank black frame (content visible in each)', frames.every((f) => f.sd > 6), frames.map((f) => f.sd.toFixed(1)).join(', '));
      await c.close();
    }

    // AC-4: mobile
    for (const [name, path] of [['home', '/'], ['post', POST]]) {
      const c = await browser.newContext({ viewport: MOBILE, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
      await c.addInitScript(INIT);
      const p = await c.newPage();
      await p.goto(base + path);
      await p.waitForSelector('[data-art][data-state="ready"]', { timeout: 8000 }).catch(() => {});
      await sleep(500);
      const s = {};
      for (const [label, y] of [['0', 0], ['60', 60], ['200', 200], ['back-0', 0]]) {
        await scrollTo(p, y);
        if (label === 'back-0') await sleep(300);
        await shot(p, `mobile-${name}-${label}`);
        s[label] = await paneState(p);
      }
      const textTop = await p.evaluate(() => document.querySelector('main').getBoundingClientRect().top);
      const artH = await p.evaluate(() => document.querySelector('[data-split-art]').getBoundingClientRect().height);
      log.push(`mobile ${name}: ` + JSON.stringify(s));
      check('AC-4', `mobile ${name}: art fills top, text starts under it`, s['0'].opacity === 1 && artH > MOBILE.height * 0.5 && textTop >= artH - 1, `art ${artH.toFixed(0)}px, text at ${textTop.toFixed(0)}px`);
      check('AC-4', `mobile ${name}: no horizontal scroll`, !s['0'].hscroll && !s['200'].hscroll);
      check('AC-4', `mobile ${name}: half dissolved at 60px`, s['60'].opacity > 0.3 && s['60'].opacity < 0.7 && s['60'].blur > 3, `opacity ${s['60'].opacity}, blur ${s['60'].blur}px`);
      check('AC-4', `mobile ${name}: gone at 200px, video paused`, s['200'].opacity === 0 && s['200'].visibility === 'hidden' && s['200'].paused === true, JSON.stringify(s['200']));
      check('AC-4', `mobile ${name}: restored at top, video playing again`, s['back-0'].opacity === 1 && s['back-0'].blur === 0 && s['back-0'].paused === false, JSON.stringify(s['back-0']));
      check('AC-4', `mobile ${name}: no layout shift (CLS < 0.01)`, s['back-0'].cls < 0.01, `CLS ${s['back-0'].cls.toFixed(4)}`);
      await c.close();
    }

    // AC-4: script fallback, simulated in Chromium (every engine here supports scroll timelines).
    // CSS.supports reports false so the script drives --dissolve-p; the native animation is switched off.
    {
      const c = await browser.newContext({ viewport: MOBILE, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
      await c.addInitScript(() => {
        const orig = CSS.supports.bind(CSS);
        CSS.supports = (...a) => (String(a.join(' ')).includes('animation-timeline') ? false : orig(...a));
        document.addEventListener('DOMContentLoaded', () => {
          const st = document.createElement('style');
          st.textContent = `@media (max-width: 799.98px) { .split > .split-art { animation: none !important;
            opacity: calc(1 - var(--dissolve-p, 0)) !important; filter: blur(calc(var(--dissolve-p, 0) * 14px)) !important;
            visibility: var(--dissolve-vis, visible) !important; } }`;
          document.head.append(st);
        });
      });
      await c.addInitScript(INIT);
      const p = await c.newPage();
      await p.goto(base + POST);
      await p.waitForSelector('[data-art][data-state="ready"]', { timeout: 8000 }).catch(() => {});
      const s = {};
      for (const [label, y] of [['0', 0], ['60', 60], ['200', 200], ['back-0', 0]]) {
        await scrollTo(p, y);
        if (label === 'back-0') await sleep(300);
        s[label] = await paneState(p);
      }
      await scrollTo(p, 60);
      await shot(p, 'mobile-post-60-script-fallback');
      log.push('script fallback (simulated): ' + JSON.stringify(s));
      check('AC-4', 'script fallback (simulated): 1 -> mid -> 0 (paused) -> 1 (playing)', s['0'].opacity === 1 && s['60'].opacity > 0.3 && s['60'].opacity < 0.7 && s['200'].opacity === 0 && s['200'].visibility === 'hidden' && s['200'].paused && s['back-0'].opacity === 1 && !s['back-0'].paused, `${s['0'].opacity} / ${s['60'].opacity} / ${s['200'].opacity} / ${s['back-0'].opacity}`);
      await c.close();
    }
  } finally {
    await browser.close();
  }

  // Cross-browser: script fallback (Firefox has no scroll timelines) and blend mode
  for (const [name, type] of [['firefox', firefox], ['webkit', webkit]]) {
    let b;
    try {
      b = await type.launch();
    } catch (e) {
      skip('AC-4/6', `${name} checks`, `browser not available: ${String(e.message).split('\n')[0]}`);
      continue;
    }
    try {
      const c = await b.newContext({ viewport: MOBILE, deviceScaleFactor: 2 });
      const p = await c.newPage();
      await p.goto(base + POST);
      await sleep(1500);
      const support = await p.evaluate(() => CSS.supports('animation-timeline: scroll()'));
      const s = {};
      for (const [label, y] of [['0', 0], ['60', 60], ['200', 200], ['back-0', 0]]) {
        await scrollTo(p, y);
        s[label] = await paneState(p);
      }
      await shot(p, `${name}-mobile-post-60-check`);
      log.push(`${name} (scroll timeline ${support ? 'native' : 'script fallback'}): ` + JSON.stringify(s));
      check('AC-4', `${name}: dissolve (${support ? 'CSS' : 'script fallback'}) 1 -> mid -> 0 -> 1`, s['0'].opacity === 1 && s['60'].opacity > 0.3 && s['60'].opacity < 0.7 && s['200'].opacity === 0 && s['back-0'].opacity === 1, `${s['0'].opacity} / ${s['60'].opacity} / ${s['200'].opacity} / ${s['back-0'].opacity}`);
      await p.setViewportSize(DESKTOP);
      await p.goto(base + '/blocks/');
      const stage = p.locator('[data-test="art-over-dither"]');
      await stage.scrollIntoViewIfNeeded();
      await sleep(2500);
      await stage.screenshot({ path: join(SHOTS, `${name}-art-over-dither.png`) });
      const st = await p.evaluate(() => {
        const a = document.querySelector('[data-test="art-over-dither"] [data-art]');
        return { state: a.dataset.state, mode: getComputedStyle(a.querySelector('video')).mixBlendMode };
      });
      check('AC-6', `${name}: art blends with mix-blend-mode screen`, st.mode === 'screen', JSON.stringify(st));
      await c.close();
    } finally {
      await b.close();
    }
  }

  await server.close();
}
