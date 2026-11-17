import { chromium } from 'playwright';
const base = 'http://127.0.0.1:4399';
const out = process.argv[2];
const b = await chromium.launch();
const list = JSON.parse(process.argv[3]);
for (const [n, p, w, h, s, wait, full] of list) {
  const pg = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
  pg.on('pageerror', (e) => console.log('ERR', n, e.message));
  await pg.goto(base + p); await pg.waitForTimeout(wait || 1500);
  if (s) { await pg.evaluate((s) => window.scrollTo(0, s), s); await pg.waitForTimeout(400); }
  await pg.screenshot({ path: `${out}/${n}.png`, fullPage: !!full }); await pg.close();
}
await b.close();
