import { hasReadableLink, type Linkable } from '../files/paths';

/** Public link: readable, but only the random token at the end opens it. */
export const sharePath = (f: Linkable, token: string) =>
  hasReadableLink(f) ? `/s/${f.ownerHandle}/${f.slug}-${token}` : `/share/${token}`;
