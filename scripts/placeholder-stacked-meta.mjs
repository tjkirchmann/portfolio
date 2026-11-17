// Poster and meta.json for public/art/_placeholder-stacked/ from a rendered stacked frame
// (top half picture, bottom half matte). Poster: RGBA, lines over a black fill inside the
// silhouette, transparent outside, as the stacked-alpha contract asks.
// Usage: node scripts/placeholder-stacked-meta.mjs <stacked-frame.png>
import sharp from 'sharp';
import { writeFile } from 'node:fs/promises';

const src = process.argv[2];
const dir = new URL('../public/art/_placeholder-stacked/', import.meta.url);
const { data, info } = await sharp(src).removeAlpha().raw().toBuffer({ resolveWithObject: true });
const w = info.width, h = info.height / 2;
const out = Buffer.alloc(w * h * 4);
for (let y = 0; y < h; y++)
  for (let x = 0; x < w; x++) {
    const t = (y * w + x) * 3, m = ((y + h) * w + x) * 3, o = (y * w + x) * 4;
    const L = [data[t], data[t + 1], data[t + 2]];
    const a = Math.max(data[m], ...L);
    out[o] = L[0]; out[o + 1] = L[1]; out[o + 2] = L[2]; out[o + 3] = a;
  }
const poster = sharp(out, { raw: { width: w, height: h, channels: 4 } });
await poster.clone().png().toFile(new URL('poster.png', dir).pathname);
const tiny = await poster.clone().resize(24, 24).webp({ quality: 60, alphaQuality: 80 }).toBuffer();
const meta = {
  slug: '_placeholder-stacked', subject: 'placeholder (stacked alpha)', width: w, height: h,
  fps: 24, frames: 96, duration: 4, alpha: 'stacked',
  blurDataUrl: `data:image/webp;base64,${tiny.toString('base64')}`,
};
await writeFile(new URL('meta.json', dir), JSON.stringify(meta, null, 2) + '\n');
console.log('ok', w, h);
