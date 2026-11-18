// Icons, inlined as SVG at build. No icon font, no client JS.
//
// A name is `name` (in the default pack) or `pack:name` for any installed Iconify JSON set
// (`@iconify-json/<pack>`). The site uses Pixelarticons: a 24px pixel grid, so icons are drawn
// at whole multiples of 24 with crisp edges (never scaled to fractional sizes).
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

export const DEFAULT_PACK = 'pixelarticons';
export const DEFAULT_ICON = 'circle';
/** the default pack's native grid; render at this size (or a whole multiple) */
export const ICON_GRID = 24;

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

function lookup(set: IconifySet, n: string): IconifyIcon | null {
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
  const set = iconifySet(pack);
  return /^[a-z0-9-]+$/.test(n) && !!set && !!lookup(set, n);
}

const cache = new Map<string, string>();

/** Inline SVG for an icon name (`name` or `pack:name`), `size` CSS px square. */
export function icon(name: string | undefined, size = ICON_GRID): string {
  const full = name || DEFAULT_ICON;
  const key = `${full}@${size}`;
  if (cache.has(key)) return cache.get(key)!;
  if (!iconExists(full)) throw new Error(`Unknown icon "${full}". Use a ${DEFAULT_PACK} name (https://pixelarticons.com) or pack:name for an installed @iconify-json pack`);
  const [pack, n] = split(full);
  const set = iconifySet(pack)!;
  const ic = lookup(set, n)!;
  const w = ic.width ?? set.width ?? 16, h = ic.height ?? set.height ?? 16;
  const l = ic.left ?? set.left ?? 0, t = ic.top ?? set.top ?? 0;
  // only the pixel pack is drawn with hard edges; other packs (brand logos) have curves
  const crisp = pack === DEFAULT_PACK ? ' shape-rendering="crispEdges"' : '';
  const svg = `<svg aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="${l} ${t} ${w} ${h}"${crisp}>${ic.body}</svg>`;
  cache.set(key, svg);
  return svg;
}
