// pnpm lighthouse: mobile Lighthouse on the production build (run `pnpm build` first).
// Uses Playwright's Chromium in a throwaway profile. Writes scores to site-shots/lighthouse.json.
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { chromium } from 'playwright';
import { serve } from './serve.mjs';

const root = process.cwd();

// async, so the in-process static server keeps answering while Lighthouse runs
function run(cmd, args, env) {
  return new Promise((resolve) => {
    const p = spawn(cmd, args, { env, stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    p.stderr.on('data', (d) => (stderr += d));
    p.stdout.resume();
    p.on('close', (status) => resolve({ status, stderr }));
  });
}
const server = await serve(join(root, 'dist'));
const tmp = mkdtempSync(join(tmpdir(), 'site-lh-'));
const lh = join(root, 'node_modules/.bin/lighthouse');
const scores = {};
let ok = true;
try {
  for (const path of ['/', '/blog/first-post/']) {
    const out = join(tmp, 'r.json');
    const r = await run(lh, [
      server.url + path,
      '--quiet',
      '--form-factor=mobile',
      '--only-categories=performance,accessibility,best-practices,seo',
      '--output=json',
      `--output-path=${out}`,
      '--chrome-flags=--headless=new --no-first-run',
    ], { ...process.env, TMPDIR: tmp, CHROME_PATH: chromium.executablePath() });
    if (r.status !== 0) {
      console.error(r.stderr.slice(-2000));
      ok = false;
      continue;
    }
    const j = JSON.parse(readFileSync(out, 'utf8'));
    if (process.env.LH_KEEP) writeFileSync(join(process.env.LH_KEEP, path.replace(/\W+/g, '_') + '.json'), JSON.stringify(j));
    const s = Object.fromEntries(Object.entries(j.categories).map(([k, v]) => [k, Math.round(v.score * 100)]));
    s.lcp = j.audits['largest-contentful-paint'].displayValue;
    s.cls = j.audits['cumulative-layout-shift'].displayValue;
    s.tbt = j.audits['total-blocking-time'].displayValue;
    scores[path] = s;
    const failing = Object.values(j.audits).filter((a) => a.score !== null && a.score < 0.9 && a.scoreDisplayMode !== 'informative' && a.scoreDisplayMode !== 'notApplicable').map((a) => a.id);
    console.log(path, JSON.stringify(s), failing.length ? `below 0.9: ${failing.join(', ')}` : '');
    if (s.performance < 95 || s.accessibility < 100) ok = false;
  }
} finally {
  await server.close();
  rmSync(tmp, { recursive: true, force: true });
}
writeFileSync(join(root, '.orchestration/reports/site-shots/lighthouse.json'), JSON.stringify(scores, null, 2) + '\n');
process.exit(ok ? 0 : 1);
