// pnpm test: content workflow checks, production build, then browser checks with screenshots.
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { results, check } from './lib.mjs';
import { contentTests } from './content.mjs';
import { siteTests } from './site.spec.mjs';

const root = process.cwd();
const SHOTS = join(root, '.orchestration/reports/site-shots');
mkdirSync(SHOTS, { recursive: true });
const log = [];
const text = {};

try {
  await contentTests(log);
  const b = spawnSync(join(root, 'node_modules/.bin/astro'), ['build'], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  check('AC-1', 'production build exits 0', b.status === 0, `exit ${b.status}`);
  if (b.status !== 0) console.log(b.stdout + b.stderr);
  else await siteTests(log, text);
} catch (e) {
  check('RUN', 'self-test ran to completion', false, e.stack);
}

const failed = results.filter((r) => !r.ok);
const skipped = results.filter((r) => r.skipped);
writeFileSync(join(SHOTS, 'test-log.txt'), log.join('\n') + '\n');
writeFileSync(join(SHOTS, 'text-dump.txt'), Object.entries(text).map(([p, t]) => `===== ${p}\n${t}`).join('\n\n') + '\n');
writeFileSync(join(SHOTS, 'results.json'), JSON.stringify(results, null, 2));
console.log(`\n${results.length - failed.length - skipped.length} passed, ${failed.length} failed, ${skipped.length} skipped`);
process.exit(failed.length ? 1 : 0);
