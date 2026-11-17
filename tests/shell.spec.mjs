// AC-23..27: Timeline block, the home 50/50 split, and the locked blog shell.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'yaml';
import { check, sleep } from './lib.mjs';

const root = process.cwd();
const SHOTS = join(root, '.orchestration/reports/site-shots');
const POST = '/blog/first-post/';

const halves = (page) =>
  page.evaluate(() => {
    const area = document.querySelector('[data-home-timelines]').getBoundingClientRect();
    const [p, c] = [...document.querySelectorAll('[data-home-timelines] > .home-half')].map((h) => h.getBoundingClientRect());
    const sc = [...document.querySelectorAll('[data-home-timelines] [data-tl-scroll]')].map((s) => ({
      overflow: s.scrollHeight > s.clientHeight + 1,
      fadeBelow: s.hasAttribute('data-more-below'),
      bar: getComputedStyle(s).scrollbarWidth,
      firstTop: s.querySelector('.tl-step').getBoundingClientRect().top - s.getBoundingClientRect().top,
    }));
    const doc = document.scrollingElement;
    return { area: area.height, p: p.height, c: c.height, pTop: p.top, cTop: c.top, sc, docScroll: doc.scrollHeight > innerHeight, sh: doc.scrollHeight, ih: innerHeight };
  });

const fillTo12 = (page) =>
  page.evaluate(() => {
    document.querySelectorAll('[data-home-timelines] .tl-list').forEach((ol) => {
      const items = [...ol.children];
      let i = 0;
      while (ol.children.length < 12) ol.append(items[i++ % items.length].cloneNode(true));
    });
    document.querySelectorAll('[data-tl-scroll]').forEach((s) => s.dispatchEvent(new Event('scroll')));
  });

export async function shellTests(browser, base, log) {
  const site = parse(readFileSync(join(root, 'src/content/site.yaml'), 'utf8'));

  // ---- AC-23/24: Timeline structure on home
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    await page.goto(base + '/');
    await sleep(600);
    await page.locator('[data-home-timelines]').screenshot({ path: join(SHOTS, 'home-timelines.png') });
    const tl = await page.evaluate(() =>
      [...document.querySelectorAll('[data-home-timelines] .tl')].map((t) => ({
        label: t.querySelector('.tl-label').textContent.trim(),
        steps: [...t.querySelectorAll('.tl-step')].map((s, i, all) => ({
          svg: !!s.querySelector('.tl-node > svg'),
          title: s.querySelector('.tl-title').textContent.trim(),
          link: s.querySelector('a.tl-title')?.getAttribute('href') || null,
          sub: s.querySelector('.tl-sub')?.textContent.trim() || null,
          year: s.querySelector('.tl-year').textContent.trim(),
          yearRight: Math.abs(s.querySelector('.tl-year').getBoundingClientRect().right - s.getBoundingClientRect().right) < 1,
          rail: i < all.length - 1 ? getComputedStyle(s, '::before').height : 'last',
          current: s.hasAttribute('data-current'),
        })),
      })),
    );
    const iconFont = await page.evaluate(() => [...document.styleSheets].some((ss) => { try { return [...ss.cssRules].some((r) => /lucide/i.test(r.cssText)); } catch { return false; } }));
    log.push('home timelines: ' + JSON.stringify(tl));
    const [proj, comp] = tl;
    check('AC-24', 'two timelines labelled Projects and Companies', proj?.label === 'Projects' && comp?.label === 'Companies');
    check('AC-23', 'every step: inline SVG icon node, title, year at the far right', tl.every((t) => t.steps.every((s) => s.svg && s.title && s.year && s.yearRight)));
    check('AC-23', 'rail line connects the nodes', tl.every((t) => t.steps.slice(0, -1).every((s) => parseFloat(s.rail) > 4)), tl.map((t) => t.steps.map((s) => s.rail).join(',')).join(' | '));
    check('AC-23', 'newest step marked current, only that one', tl.every((t) => t.steps[0].current && t.steps.slice(1).every((s) => !s.current)));
    check('AC-23', 'icons are inline SVG at build (no icon font)', !iconFont);
    check('AC-24', 'projects match site.yaml (title, year, link)', site.projects.every((e, i) => proj.steps[i].title === e.title && proj.steps[i].year === String(e.year) && proj.steps[i].link === (e.href ?? null)));
    check('AC-24', 'companies match site.yaml (name, role subtitle, year range right)', site.companies.every((e, i) => comp.steps[i].title === e.title && comp.steps[i].sub === e.subtitle && comp.steps[i].year === String(e.year)));
    await ctx.close();
  }

  // ---- AC-25: 50/50 split
  for (const [w, h] of [[1440, 900], [1280, 720], [1440, 1100]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    await page.goto(base + '/');
    await sleep(400);
    const a = await halves(page);
    await fillTo12(page);
    await sleep(200);
    const b = await halves(page);
    if (w === 1280) await page.screenshot({ path: join(SHOTS, 'home-1280x720-12-entries.png') });
    if (w === 1440 && h === 900) {
      await page.screenshot({ path: join(SHOTS, 'home-1440x900-12-entries.png') });
    }
    log.push(`home ${w}x${h}: 3 entries ${JSON.stringify(a)} | 12 entries ${JSON.stringify(b)}`);
    check('AC-25', `${w}x${h}: halves equal within 1px (3 entries)`, Math.abs(a.p - a.c) <= 1 && Math.abs(a.p + a.c - a.area) <= 1, `${a.p.toFixed(1)} / ${a.c.toFixed(1)} of ${a.area.toFixed(1)}`);
    check('AC-25', `${w}x${h}: halves equal within 1px (12 entries)`, Math.abs(b.p - b.c) <= 1 && Math.abs(b.p - a.p) <= 1, `${b.p.toFixed(1)} / ${b.c.toFixed(1)}`);
    check('AC-25', `${w}x${h}: overflow scrolls inside its half with a fade, no scrollbar chrome`, b.sc.every((s) => s.overflow && s.fadeBelow && s.bar === 'none'));
    check('AC-25', `${w}x${h}: few entries align to the top`, a.sc.every((s) => s.firstTop < 12), a.sc.map((s) => s.firstTop.toFixed(0)).join(', '));
    if (h <= 900) check('AC-25', `${w}x${h}: the page itself does not scroll`, !a.docScroll && !b.docScroll, `scrollHeight ${a.sh} vs ${a.ih}`);
    await ctx.close();
  }
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });
    const page = await ctx.newPage();
    await page.goto(base + '/');
    await sleep(400);
    const m = await page.evaluate(() => ({
      stacked: (() => { const [p, c] = [...document.querySelectorAll('.home-half')].map((x) => x.getBoundingClientRect()); return c.top >= p.bottom - 1; })(),
      natural: [...document.querySelectorAll('[data-tl-scroll]')].every((s) => s.scrollHeight <= s.clientHeight + 1),
      pageScrolls: document.scrollingElement.scrollHeight > innerHeight,
    }));
    await page.evaluate(() => window.scrollTo(0, 500));
    await sleep(400);
    await page.screenshot({ path: join(SHOTS, 'mobile-home-timelines.png') });
    check('AC-25', 'below 800px: timelines stack at natural height and the page scrolls', m.stacked && m.natural && m.pageScrolls, JSON.stringify(m));
    await ctx.close();
  }

  // ---- AC-26: /blocks shows Timeline in both forms and the overflow case
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    await page.goto(base + '/blocks/');
    await page.locator('[data-test="timeline-companies"]').scrollIntoViewIfNeeded();
    await sleep(300);
    const b = await page.evaluate(() => {
      const c = document.querySelector('[data-test="timeline-companies"]');
      const o = document.querySelector('[data-test="timeline-overflow"] [data-tl-scroll]');
      return { subs: c.querySelectorAll('.tl-sub').length, plain: document.querySelector('[data-test="timeline-overflow"] .tl-sub') === null, overflow: o.scrollHeight > o.clientHeight, steps: o.querySelectorAll('.tl-step').length };
    });
    await page.locator('[data-test="timeline-companies"]').screenshot({ path: join(SHOTS, 'blocks-timeline-companies.png') });
    await page.locator('[data-test="timeline-overflow"]').screenshot({ path: join(SHOTS, 'blocks-timeline-overflow.png') });
    check('AC-26', '/blocks: Timeline with subtitles, without, and the overflow case', b.subs >= 3 && b.plain && b.overflow && b.steps === 12, JSON.stringify(b));
    await ctx.close();
  }

  // ---- AC-27: locked blog shell
  for (const [w, h] of [[1440, 900], [1280, 720]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    for (const p of ['/blog/', POST]) {
      await page.goto(base + p);
      await sleep(300);
      const d = await page.evaluate(() => ({ sh: document.scrollingElement.scrollHeight, ih: innerHeight }));
      check('AC-27', `${w}x${h} ${p}: document does not scroll (scrollHeight === innerHeight)`, d.sh === d.ih, `${d.sh} vs ${d.ih}`);
    }
    const pane = () =>
      page.evaluate(() => {
        const m = document.querySelector('main[data-pane]');
        return { top: Math.round(m.scrollTop), max: m.scrollHeight - m.clientHeight, win: window.scrollY, above: m.hasAttribute('data-more-above'), below: m.hasAttribute('data-more-below'), bar: getComputedStyle(m).scrollbarWidth, osb: getComputedStyle(m).overscrollBehaviorY, art: document.querySelector('[data-split-art]').getBoundingClientRect().top, back: document.querySelector('[data-back]').getBoundingClientRect().top, pad: parseFloat(getComputedStyle(m).paddingTop) };
      });
    // keyboard without a click (fresh load, nothing clicked)
    await page.goto(base + POST);
    await sleep(400);
    const k0 = await pane();
    await page.keyboard.press('ArrowDown');
    await sleep(300);
    const k1 = await pane();
    await page.keyboard.press('PageDown');
    await sleep(400);
    const k2 = await pane();
    await page.keyboard.press('End');
    await sleep(500);
    const k3 = await pane();
    await page.keyboard.press('Home');
    await sleep(500);
    const k4 = await pane();
    await page.keyboard.press('Space');
    await sleep(400);
    const k5 = await pane();
    await page.keyboard.press('Home');
    await sleep(400);
    log.push(`${w}x${h} keyboard (max ${k0.max}): start ${k0.top}, ArrowDown ${k1.top}, PageDown ${k2.top}, End ${k3.top}, Home ${k4.top}, Space ${k5.top}`);
    check('AC-27', `${w}x${h}: keyboard scrolls the pane without a click (ArrowDown, PageDown, End, Home, Space)`, k0.top === 0 && k1.top > 0 && k2.top > k1.top && Math.abs(k3.top - k3.max) <= 2 && k4.top === 0 && k5.top > 100 && [k1, k2, k3, k5].every((s) => s.win === 0), `${k1.top}, ${k2.top}, ${k3.top}/${k3.max}, ${k4.top}, ${k5.top}`);
    check('AC-27', `${w}x${h}: thin scrollbar, no overscroll chaining, padding above the title`, k0.bar === 'thin' && k0.osb === 'contain' && k0.pad >= 20, `${k0.bar}, ${k0.osb}, ${k0.pad}px`);
    if (w === 1440) await page.screenshot({ path: join(SHOTS, 'post-pane-top.png') });
    check('AC-27', `${w}x${h}: fade only where clipped (top: bottom fade only)`, !k0.above && k0.below);
    // wheel over the text pane, then over the art pane
    await page.mouse.move(w * 0.7, h * 0.5);
    await page.mouse.wheel(0, 200);
    await sleep(500);
    const wh1 = await pane();
    if (w === 1440) await page.screenshot({ path: join(SHOTS, 'post-pane-middle.png') });
    await page.mouse.move(w * 0.2, h * 0.5);
    await page.mouse.wheel(0, 120);
    await sleep(500);
    const wh2 = await pane();
    check('AC-27', `${w}x${h}: wheel scrolls the pane, art and back arrow stay put`, wh1.top >= 150 && wh1.win === 0 && wh1.art === k0.art && wh1.back === k0.back && wh1.above && wh1.below, `pane ${wh1.top}, window ${wh1.win}`);
    check('AC-27', `${w}x${h}: wheel over the art pane also scrolls the text pane`, wh2.top > wh1.top && wh2.win === 0, `${wh1.top} -> ${wh2.top}`);
    await page.mouse.move(w * 0.7, h * 0.5);
    await page.mouse.wheel(0, 20000);
    await sleep(600);
    await page.mouse.wheel(0, 2000);
    await sleep(400);
    const end = await pane();
    if (w === 1440) await page.screenshot({ path: join(SHOTS, 'post-pane-end.png') });
    check('AC-27', `${w}x${h}: at the end, more wheel does not move the page`, Math.abs(end.top - end.max) <= 2 && end.win === 0 && !end.below && end.above, `pane ${end.top}/${end.max}, window ${end.win}`);
    // footnote round trip inside the pane
    await page.keyboard.press('Home');
    await sleep(400);
    await page.click('.prose [data-footnote-ref] >> nth=0');
    await sleep(600);
    const fn = await page.evaluate(() => { const t = document.querySelector(':target'); const r = t?.getBoundingClientRect(); return { hash: location.hash, inView: !!r && r.top >= 0 && r.bottom <= innerHeight, bg: t ? getComputedStyle(t).backgroundColor : null, pane: document.querySelector('main[data-pane]').scrollTop, win: scrollY }; });
    await page.click('#user-content-fn-1 .data-footnote-backref');
    await sleep(600);
    const fb = await page.evaluate(() => { const t = document.querySelector(':target'); const r = t?.getBoundingClientRect(); return { hash: location.hash, inView: !!r && r.top >= 0 && r.bottom <= innerHeight, pane: document.querySelector('main[data-pane]').scrollTop, win: scrollY }; });
    check('AC-27', `${w}x${h}: footnote ref -> note -> back, inside the pane, highlighted`, fn.hash === '#user-content-fn-1' && fn.inView && fn.pane > 0 && fn.win === 0 && fn.bg !== 'rgba(0, 0, 0, 0)' && fb.hash === '#user-content-fnref-1' && fb.inView && fb.win === 0, JSON.stringify({ fn, fb }));
    await ctx.close();
  }

  // heading anchor + back/forward restoration + new post starts at top
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    await page.goto(base + POST + '#a-heading');
    await sleep(500);
    const anchor = await page.evaluate(() => { const r = document.getElementById('a-heading').getBoundingClientRect(); return { top: r.top, pane: document.querySelector('main[data-pane]').scrollTop, win: scrollY }; });
    check('AC-27', 'heading anchor (#a-heading) scrolls the pane to bring the heading into view', anchor.pane > 0 && anchor.top >= 0 && anchor.top < 900 - 60 && anchor.win === 0, JSON.stringify(anchor));

    await page.goto(base + '/blog/');
    await sleep(400);
    await page.click('main a[href="/blog/first-post/"]');
    await page.waitForURL('**/blog/first-post/');
    await sleep(600);
    const fresh = await page.evaluate(() => document.querySelector('main[data-pane]').scrollTop);
    check('AC-27', 'a newly opened post starts at the top', fresh === 0, `scrollTop ${fresh}`);
    await page.evaluate(() => (document.querySelector('main[data-pane]').scrollTop = 600));
    await sleep(400);
    await page.click('[data-back]');
    await page.waitForURL(/\/blog\/$/);
    await sleep(600);
    await page.goBack();
    await page.waitForURL('**/blog/first-post/');
    await sleep(800);
    const back = await page.evaluate(() => document.querySelector('main[data-pane]').scrollTop);
    await page.goForward();
    await page.waitForURL(/\/blog\/$/);
    await sleep(500);
    await page.goBack();
    await page.waitForURL('**/blog/first-post/');
    await sleep(800);
    const back2 = await page.evaluate(() => document.querySelector('main[data-pane]').scrollTop);
    check('AC-27', 'back/forward restores the pane position', Math.abs(back - 600) <= 2 && Math.abs(back2 - 600) <= 2, `after back ${back}, after forward+back ${back2}`);
    await ctx.close();
  }
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });
    const page = await ctx.newPage();
    await page.goto(base + POST);
    await sleep(300);
    const m = await page.evaluate(() => ({ docScrolls: document.scrollingElement.scrollHeight > innerHeight, paneOverflow: getComputedStyle(document.querySelector('main')).overflowY }));
    check('AC-27', 'below 800px: unchanged, the document scrolls', m.docScrolls && m.paneOverflow === 'visible', JSON.stringify(m));
    await ctx.close();
  }
}
