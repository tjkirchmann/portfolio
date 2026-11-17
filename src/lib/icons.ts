// Lucide icons (lucide-static), inlined as SVG at build. No icon font, no client JS.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const DIR = join(process.cwd(), 'node_modules', 'lucide-static', 'icons');
export const DEFAULT_ICON = 'circle-dot';

export const iconExists = (name: string) => /^[a-z0-9-]+$/.test(name) && existsSync(join(DIR, `${name}.svg`));

const cache = new Map<string, string>();

/** Returns inline SVG markup for a lucide icon name. */
export function icon(name: string | undefined, size = 15): string {
  const n = name || DEFAULT_ICON;
  const key = `${n}@${size}`;
  if (cache.has(key)) return cache.get(key)!;
  if (!iconExists(n)) throw new Error(`Unknown icon "${n}". Use a lucide icon name, see https://lucide.dev/icons`);
  const svg = readFileSync(join(DIR, `${n}.svg`), 'utf8')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\s*class="[^"]*"/, '')
    .replace(/width="24"/, `width="${size}"`)
    .replace(/height="24"/, `height="${size}"`)
    .replace(/stroke-width="2"/, 'stroke-width="1.75"')
    .replace('<svg', '<svg aria-hidden="true" focusable="false"')
    .replace(/\n\s*/g, ' ')
    .trim();
  cache.set(key, svg);
  return svg;
}
