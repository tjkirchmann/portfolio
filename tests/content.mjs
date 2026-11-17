// Content workflow checks: schema errors name the file, drafts stay out of production,
// new-post scaffolds and refuses to overwrite. Each fixture is removed afterwards.
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { check } from './lib.mjs';

const root = process.cwd();
const blog = join(root, 'src/content/blog');
const astroBin = join(root, 'node_modules/.bin/astro');

function build(outDir) {
  const r = spawnSync(astroBin, ['build', '--outDir', outDir], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  return { code: r.status, out: (r.stdout || '') + (r.stderr || '') };
}

export async function contentTests(log) {
  const tmp = mkdtempSync(join(tmpdir(), 'site-content-'));
  try {
    // AC-13: broken frontmatter fails the build and names the file
    const bad = join(blog, 'zz-broken-fixture');
    mkdirSync(bad, { recursive: true });
    writeFileSync(join(bad, 'index.md'), '---\ntitle: Broken\ndate: not-a-date\n---\n\nBody.\n');
    let r;
    try {
      r = build(join(tmp, 'bad'));
    } finally {
      rmSync(bad, { recursive: true, force: true });
    }
    const lines = r.out.split('\n').filter((l) => /zz-broken-fixture|InvalidContentEntry|art|date/i.test(l)).slice(0, 8);
    log.push('$ astro build   # with src/content/blog/zz-broken-fixture/index.md (bad date, no art)', `exit ${r.code}`, ...lines);
    check('AC-13', 'broken frontmatter fails the build', r.code !== 0, `exit ${r.code}`);
    check('AC-13', 'build error names the file', /zz-broken-fixture/.test(r.out));
    check('AC-13', 'broken fixture removed', !existsSync(bad));

    // AC-13: draft posts are left out of production builds
    const draft = join(blog, 'zz-draft-fixture');
    mkdirSync(draft, { recursive: true });
    writeFileSync(join(draft, 'index.md'), '---\ntitle: Draft fixture\ndate: 2026-01-01\nart: _placeholder\ndraft: true\n---\n\nBody.\n');
    try {
      r = build(join(tmp, 'draft'));
    } finally {
      rmSync(draft, { recursive: true, force: true });
    }
    const listed = existsSync(join(tmp, 'draft/blog/index.html')) && readFileSync(join(tmp, 'draft/blog/index.html'), 'utf8').includes('Draft fixture');
    check('AC-13', 'draft build exits 0', r.code === 0, `exit ${r.code}`);
    check('AC-13', 'draft post has no page in production', !existsSync(join(tmp, 'draft/blog/zz-draft-fixture/index.html')));
    check('AC-13', 'draft post not listed on /blog/', !listed);

    // AC-24: a bad site.yaml entry fails the build with a clear message
    const siteFile = join(root, 'src/content/site.yaml');
    const original = readFileSync(siteFile, 'utf8');
    try {
      writeFileSync(siteFile, original.replace('icon: layers', 'icon: not-an-icon').replace(/(- title: Company two\n\s+subtitle: Role\n)\s+year: .*\n/, '$1'));
      r = build(join(tmp, 'site'));
    } finally {
      writeFileSync(siteFile, original);
    }
    const msg = r.out.split('\n').filter((l) => /site\.yaml|projects|companies|icon/.test(l)).slice(0, 4);
    log.push('$ astro build   # site.yaml with an unknown icon and a company without a year', `exit ${r.code}`, ...msg);
    check('AC-24', 'bad site.yaml entry fails the build', r.code !== 0, `exit ${r.code}`);
    check('AC-24', 'message names the file, the entry and the problem', /site\.yaml is invalid/.test(r.out) && /projects\.1\.icon: unknown icon "not-an-icon"/.test(r.out) && /companies\.1\.year/.test(r.out));
    check('AC-24', 'site.yaml restored', readFileSync(siteFile, 'utf8') === original);

    // AC-14: new-post scaffolds, then refuses to overwrite
    const title = 'Zz Scaffold Fixture';
    const dir = join(blog, 'zz-scaffold-fixture');
    try {
      const a = spawnSync(process.execPath, ['scripts/new-post.mjs', title], { cwd: root, encoding: 'utf8' });
      const file = join(dir, 'index.md');
      const body = existsSync(file) ? readFileSync(file, 'utf8') : '';
      const d = new Date();
      const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      log.push(`$ pnpm new-post "${title}"`, (a.stdout + a.stderr).trim(), body.trim());
      check('AC-14', 'new-post creates <slug>/index.md', a.status === 0 && existsSync(file));
      check('AC-14', "frontmatter has title, today's date, art: _placeholder",
        body.includes(`title: "${title}"`) && body.includes(`date: ${today}`) && body.includes('art: _placeholder'));
      writeFileSync(file, body + 'Edited.\n');
      const b = spawnSync(process.execPath, ['scripts/new-post.mjs', title], { cwd: root, encoding: 'utf8' });
      log.push(`$ pnpm new-post "${title}"   # again`, `exit ${b.status}`, (b.stdout + b.stderr).trim());
      check('AC-14', 'second run refuses (non-zero exit)', b.status !== 0);
      check('AC-14', 'existing file untouched', readFileSync(file, 'utf8').endsWith('Edited.\n'));
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}
