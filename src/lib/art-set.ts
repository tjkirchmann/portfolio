import { z } from 'astro/zod';

/** One art piece in a pane: slug in public/art/, icon and label for the switcher. */
const pieceItem = z
  .object({
    slug: z.string().min(1),
    icon: z.string().min(1),
    label: z.string().min(1),
    backdrop: z.boolean().optional().default(true),
  })
  .strict();

/** A view with no piece in front: just the pane's life simulation. */
const noneItem = z
  .object({
    none: z.literal(true),
    icon: z.string().min(1),
    label: z.string().min(1),
  })
  .strict();

export const artItem = z.union([pieceItem, noneItem]);

/** `art` is a single slug or a list of views; the first is the default. */
export const artField = z.union([z.string().min(1), z.array(artItem).min(1)]);

export type ArtField = z.infer<typeof artField>;
/** normalised: `slug` is '_none' for the simulation-only view */
export interface ArtItem {
  slug: string;
  icon: string;
  label: string;
  backdrop: boolean;
  none: boolean;
}

export const NONE_SLUG = '_none';

export function artList(art: ArtField | undefined): ArtItem[] {
  if (!art) return [{ slug: '_placeholder', icon: 'circle', label: 'Art', backdrop: true, none: false }];
  if (typeof art === 'string') return [{ slug: art, icon: 'circle', label: 'Art', backdrop: true, none: false }];
  return art.map((a) =>
    (a as { none?: boolean }).none === true
      ? { slug: NONE_SLUG, icon: a.icon, label: a.label, backdrop: true, none: true }
      : { slug: (a as { slug: string }).slug, icon: a.icon, label: a.label, backdrop: (a as { backdrop?: boolean }).backdrop !== false, none: false },
  );
}

/** first real piece (for panes that show one piece and no menu) */
export function firstPiece(art: ArtField | undefined): string {
  return artList(art).find((a) => !a.none)?.slug ?? '_placeholder';
}
