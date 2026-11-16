import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const blog = defineCollection({
  loader: glob({ pattern: '*/index.md', base: './src/content/blog' }),
  schema: z
    .object({
      title: z.string().min(1),
      date: z.coerce.date(),
      art: z.string().min(1),
      draft: z.boolean().optional().default(false),
      summary: z.string().optional(),
    })
    .strict(),
});

export const collections = { blog };
