import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'yaml';
import { z } from 'astro/zod';
import { iconExists } from './icons';
import { artField } from './art-set';

const link = z.object({ label: z.string(), href: z.string() });

const step = z
  .object({
    title: z.string().min(1),
    subtitle: z.string().optional(),
    year: z
      .union([z.string(), z.number()], { error: 'a year or range is required, e.g. 2024 or "2021 – 2024"' })
      .transform(String),
    icon: z
      .string()
      .optional()
      .superRefine((v, ctx) => {
        if (v !== undefined && !iconExists(v))
          ctx.addIssue({ code: 'custom', message: `unknown icon "${v}" (use a lucide icon name, see https://lucide.dev/icons)` });
      }),
    href: z.string().optional(),
    /** markdown, shown in the home hover panel (or inline on narrow screens) */
    body: z.string().nullish().transform((v) => v ?? ''),
  })
  .strict();

const schema = z
  .object({
    name: z.string(),
    role: z.string(),
    /** archived: the ball art no longer shows on the site; kept for /blocks and reuse */
    art: artField.optional(),
    experiences: z.array(step),
    companies: z.array(step),
    links: z.array(link),
  })
  .strict();

export type Site = z.infer<typeof schema>;
export type Step = z.infer<typeof step>;

const file = join(process.cwd(), 'src', 'content', 'site.yaml');

export function loadSite(): Site {
  const result = schema.safeParse(parse(readFileSync(file, 'utf8')));
  if (!result.success) {
    const lines = result.error.issues.map((i) => `  ${i.path.join('.') || '(root)'}: ${i.message}`);
    throw new Error(`src/content/site.yaml is invalid:\n${lines.join('\n')}`);
  }
  return result.data;
}
