import type { ViewLink } from '../files/types';
import { apiFetch, jsonBody } from '../shared/http';
import type { PublicFile, ShareLink } from './types';

const id = encodeURIComponent;

export const sharesApi = {
  list: (fileId: string) => apiFetch<{ items: ShareLink[] }>(`files/${id(fileId)}/shares`).then((r) => r.items),

  create: (fileId: string, expiresInDays: number) =>
    apiFetch<ShareLink>(`files/${id(fileId)}/shares`, { method: 'POST', ...jsonBody({ expiresInDays }) }),

  revoke: (token: string) => apiFetch<void>(`shares/${id(token)}`, { method: 'DELETE' }),

  resolve: (token: string) => apiFetch<ViewLink<PublicFile>>(`public/shares/${id(token)}`),

  resolveReadable: (handle: string, slugAndToken: string) =>
    apiFetch<ViewLink<PublicFile>>(`public/s/${id(handle)}/${id(slugAndToken)}`),
};
