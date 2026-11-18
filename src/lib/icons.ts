// Icons, inlined as SVG at build. No icon font, no client JS.
//
// A name is `name` (in the default pack) or `pack:name`. The default pack is Lucide from
// lucide-static; any other pack is an Iconify JSON set installed as `@iconify-json/<pack>`
// (ph, tabler, pixelarticons, iconoir, simple-icons). Switching the whole site to another
// pack is DEFAULT_PACK plus the per-item names in site.yaml.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

export const DEFAULT_PACK = 'lucide';
export const DEFAULT_ICON = 'circle-dot';

const LUCIDE = join(process.cwd(), 'node_modules', 'lucide-static', 'icons');

interface IconifyIcon {
  body: string;
  width?: number;
  height?: number;
  left?: number;
  top?: number;
}
interface IconifySet {
  width?: number;
  height?: number;
  left?: number;
  top?: number;
  icons: Record<string, IconifyIcon>;
  aliases?: Record<string, { parent: string } & Partial<IconifyIcon>>;
}

const sets = new Map<string, IconifySet | null>();
function iconifySet(pack: string): IconifySet | null {
  if (!sets.has(pack)) {
    const file = join(process.cwd(), 'node_modules', '@iconify-json', pack, 'icons.json');
    sets.set(pack, /^[a-z0-9-]+$/.test(pack) && existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : null);
  }
  return sets.get(pack)!;
}

function split(name: string): [string, string] {
  const i = name.indexOf(':');
  return i < 0 ? [DEFAULT_PACK, name] : [name.slice(0, i), name.slice(i + 1)];
}

function iconifyLookup(set: IconifySet, n: string): IconifyIcon | null {
  let extra: Partial<IconifyIcon> = {};
  for (let k = 0; k < 4; k++) {
    if (set.icons[n]) return { ...set.icons[n], ...extra };
    const a = set.aliases?.[n];
    if (!a) return null;
    const { parent, ...rest } = a;
    extra = { ...rest, ...extra };
    n = parent;
  }
  return null;
}

export function iconExists(name: string): boolean {
  const [pack, n] = split(name);
  if (!/^[a-z0-9-]+$/.test(n)) return false;
  if (pack === 'lucide') return existsSync(join(LUCIDE, `${n}.svg`));
  const set = iconifySet(pack);
  return !!set && !!iconifyLookup(set, n);
}

const cache = new Map<string, string>();

/** Returns inline SVG markup for an icon name (`name` or `pack:name`). */
export function icon(name: string | undefined, size = 15): string {
  const full = name || DEFAULT_ICON;
  const key = `${full}@${size}`;
  if (cache.has(key)) return cache.get(key)!;
  if (!iconExists(full)) throw new Error(`Unknown icon "${full}". Use a lucide name (https://lucide.dev/icons) or pack:name for an installed @iconify-json pack`);
  const [pack, n] = split(full);
  let svg: string;
  if (pack === 'lucide') {
    svg = readFileSync(join(LUCIDE, `${n}.svg`), 'utf8')
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/\s*class="[^"]*"/, '')
      .replace(/width="24"/, `width="${size}"`)
      .replace(/height="24"/, `height="${size}"`)
      .replace(/stroke-width="2"/, 'stroke-width="1.75"')
      .replace('<svg', '<svg aria-hidden="true" focusable="false"')
      .replace(/\n\s*/g, ' ')
      .trim();
  } else {
    const set = iconifySet(pack)!;
    const ic = iconifyLookup(set, n)!;
    const w = ic.width ?? set.width ?? 16, h = ic.height ?? set.height ?? 16;
    const l = ic.left ?? set.left ?? 0, t = ic.top ?? set.top ?? 0;
    svg = `<svg aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="${l} ${t} ${w} ${h}">${ic.body}</svg>`;
  }
  cache.set(key, svg);
  return svg;
}
