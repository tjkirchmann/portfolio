import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

export interface ArtMeta {
  slug: string;
  subject: string;
  width: number;
  height: number;
  fps: number;
  frames: number;
  duration: number;
  blurDataUrl: string;
  /** "stacked": video is width x 2*height, picture on top, matte below (opaque pieces) */
  alpha?: 'stacked';
}

export interface ResolvedArt extends ArtMeta {
  base: string;
  hasWebm: boolean;
  hasMp4: boolean;
}

const PUBLIC_ART = join(process.cwd(), 'public', 'art');
export const PLACEHOLDER = '_placeholder';

/** Reads public/art/<slug>/meta.json at build time; falls back to the placeholder if missing. */
export function resolveArt(slug: string | undefined): ResolvedArt {
  const wanted = slug && existsSync(join(PUBLIC_ART, slug, 'meta.json')) ? slug : PLACEHOLDER;
  if (slug && wanted !== slug) console.warn(`[art] public/art/${slug}/ not found, using ${PLACEHOLDER}`);
  const dir = join(PUBLIC_ART, wanted);
  const meta = JSON.parse(readFileSync(join(dir, 'meta.json'), 'utf8')) as ArtMeta;
  return {
    ...meta,
    slug: wanted,
    base: `/art/${wanted}/`,
    hasWebm: existsSync(join(dir, 'loop.webm')),
    hasMp4: existsSync(join(dir, 'loop.mp4')),
  };
}
