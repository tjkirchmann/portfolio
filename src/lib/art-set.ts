import { z } from 'astro/zod';

/** One art piece in a pane: slug in public/art/, lucide icon and label for the switcher. */
export const artItem = z
  .object({
    slug: z.string().min(1),
    icon: z.string().min(1),
    label: z.string().min(1),
    backdrop: z.boolean().optional().default(true),
  })
  .strict();

/** `art` is a single slug or a list of pieces; the first piece is the default. */
export const artField = z.union([z.string().min(1), z.array(artItem).min(1)]);

export type ArtItem = z.infer<typeof artItem>;
export type ArtField = z.infer<typeof artField>;

export function artList(art: ArtField | undefined): ArtItem[] {
  if (!art) return [{ slug: '_placeholder', icon: 'circle-dot', label: 'Art', backdrop: true }];
  if (typeof art === 'string') return [{ slug: art, icon: 'circle-dot', label: 'Art', backdrop: true }];
  return art;
}
