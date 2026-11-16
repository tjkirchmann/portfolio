// Minimal static server for dist/, with Range support so video loops and seeks like on a CDN.
import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.avif': 'image/avif',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
  '.webm': 'video/webm',
  '.mp4': 'video/mp4',
};

export function serve(root, port = 0) {
  const server = createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    let file = normalize(join(root, decodeURIComponent(url.pathname)));
    if (!file.startsWith(root)) return res.writeHead(403).end();
    if (existsSync(file) && statSync(file).isDirectory()) file = join(file, 'index.html');
    if (!existsSync(file)) {
      const nf = join(root, '404.html');
      res.writeHead(404, { 'content-type': TYPES['.html'] });
      return existsSync(nf) ? createReadStream(nf).pipe(res) : res.end('Not found');
    }
    const size = statSync(file).size;
    const type = TYPES[extname(file)] || 'application/octet-stream';
    const immutable = url.pathname.startsWith('/_astro/');
    const headers = {
      'content-type': type,
      'accept-ranges': 'bytes',
      'cache-control': immutable ? 'public, max-age=31536000, immutable' : 'public, max-age=3600',
    };
    const range = req.headers.range && /bytes=(\d*)-(\d*)/.exec(req.headers.range);
    if (range) {
      const start = range[1] ? Number(range[1]) : 0;
      const end = range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
      res.writeHead(206, { ...headers, 'content-range': `bytes ${start}-${end}/${size}`, 'content-length': end - start + 1 });
      return createReadStream(file, { start, end }).pipe(res);
    }
    res.writeHead(200, { ...headers, 'content-length': size });
    if (req.method === 'HEAD') return res.end();
    createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => {
    server.listen(port, '127.0.0.1', () => {
      const { port: p } = server.address();
      resolve({ url: `http://127.0.0.1:${p}`, close: () => new Promise((r) => server.close(r)) });
    });
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const root = join(process.cwd(), 'dist');
  const { url } = await serve(root, Number(process.argv[2] || 4399));
  console.log(`serving ${root} at ${url}`);
}
