// Writes public/art/_placeholder/meta.json from the rendered poster.
// The real art pipeline writes its own meta.json; this only serves the stand-in.
import sharp from 'sharp';
import { writeFile } from 'node:fs/promises';

const dir = new URL('../public/art/_placeholder/', import.meta.url);
const poster = sharp(new URL('poster.png', dir).pathname);
const { width, height } = await poster.metadata();
const tiny = await poster.clone().resize(24, 24, { fit: 'inside' }).webp({ quality: 60 }).toBuffer();
const fps = 24, frames = 96;
const meta = {
  slug: '_placeholder',
  subject: 'placeholder',
  width, height, fps, frames,
  duration: frames / fps,
  blurDataUrl: `data:image/webp;base64,${tiny.toString('base64')}`,
};
await writeFile(new URL('meta.json', dir), JSON.stringify(meta, null, 2) + '\n');
console.log('meta.json', meta.width, meta.height, meta.blurDataUrl.length, 'chars');
