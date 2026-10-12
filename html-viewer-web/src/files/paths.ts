import type { HtmlFile } from './types';

export type Linkable = Pick<HtmlFile, 'ownerId' | 'id' | 'ownerHandle' | 'slug'>;

export const hasReadableLink = (f: Linkable) => Boolean(f.ownerHandle && f.slug);

/** Internal link (needs sign-in): /u/{user}/{name}. Files without a name keep the id form. */
export const viewPath = (f: Linkable) =>
  hasReadableLink(f) ? `/u/${f.ownerHandle}/${f.slug}` : `/view/${f.ownerId}/${f.id}`;

/**
 * Preview of the link name the API will produce (it has the final word):
 * lowercase letters and digits separated by single dashes.
 */
export const slugify = (text: string) =>
  text
    .normalize('NFKD')
    .replace(/[^\x00-\x7f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
    .replace(/-+$/, '');
