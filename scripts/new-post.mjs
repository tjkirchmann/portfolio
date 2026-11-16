// pnpm new-post "Some Title"  ->  src/content/blog/some-title/index.md
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const title = process.argv.slice(2).join(' ').trim();
if (!title) {
  console.error('Usage: pnpm new-post "Post title"');
  process.exit(1);
}

const slug = title
  .normalize('NFKD')
  .replace(/[̀-ͯ]/g, '')
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, '-')
  .replace(/^-+|-+$/g, '');
if (!slug) {
  console.error(`Cannot make a folder name from "${title}". Use letters or numbers.`);
  process.exit(1);
}

const root = process.env.BLOG_DIR || join(process.cwd(), 'src', 'content', 'blog');
const dir = join(root, slug);
const file = join(dir, 'index.md');
if (existsSync(dir)) {
  console.error(`${relative(process.cwd(), dir)} already exists. Pick another title or edit that post.`);
  process.exit(1);
}

const d = new Date();
const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const yamlTitle = JSON.stringify(title);

mkdirSync(dir, { recursive: true });
writeFileSync(
  file,
  `---\ntitle: ${yamlTitle}\ndate: ${today}\nart: _placeholder\n---\n\n`,
);
console.log(`Created ${relative(process.cwd(), file)}`);
