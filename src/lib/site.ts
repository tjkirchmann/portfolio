import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'yaml';
import { z } from 'astro/zod';

const link = z.object({ label: z.string(), href: z.string() });

const schema = z.object({
  name: z.string(),
  role: z.string(),
  art: z.string().default('_placeholder'),
  entries: z.array(z.object({ label: z.string(), detail: z.string().optional(), href: z.string().optional() })),
  links: z.array(link),
});

export type Site = z.infer<typeof schema>;

const file = join(process.cwd(), 'src', 'content', 'site.yaml');

export function loadSite(): Site {
  const result = schema.safeParse(parse(readFileSync(file, 'utf8')));
  if (!result.success) throw new Error(`src/content/site.yaml is invalid:\n${result.error.message}`);
  return result.data;
}
