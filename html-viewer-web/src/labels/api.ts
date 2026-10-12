import { apiFetch, jsonBody } from '../shared/http';
import type { Label } from './types';

const id = encodeURIComponent;

export const labelsApi = {
  list: () => apiFetch<{ items: Label[] }>('labels').then((r) => r.items),

  create: (name: string) => apiFetch<Label>('labels', { method: 'POST', ...jsonBody({ name }) }),

  rename: (labelId: string, name: string) =>
    apiFetch<Label>(`labels/${id(labelId)}`, { method: 'PATCH', ...jsonBody({ name }) }),

  remove: (labelId: string) => apiFetch<void>(`labels/${id(labelId)}`, { method: 'DELETE' }),
};
