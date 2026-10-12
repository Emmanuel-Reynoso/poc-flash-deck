import { apiFetch, jsonBody } from '../shared/http';
import type { HtmlFile, UploadTicket, ViewLink, Visibility } from './types';

const id = encodeURIComponent;

/** `labelId: null` moves the file out of any label. */
export interface FileChanges {
  title?: string;
  visibility?: Visibility;
  slug?: string;
  labelId?: string | null;
}

export const filesApi = {
  list: () => apiFetch<{ items: HtmlFile[] }>('files').then((r) => r.items),

  startUpload: (file: File) =>
    apiFetch<UploadTicket>('files', { method: 'POST', ...jsonBody({ fileName: file.name, sizeBytes: file.size }) }),

  completeUpload: (fileId: string) => apiFetch<HtmlFile>(`files/${id(fileId)}/complete`, { method: 'POST' }),

  update: (fileId: string, changes: FileChanges) =>
    apiFetch<HtmlFile>(`files/${id(fileId)}`, { method: 'PATCH', ...jsonBody(changes) }),

  remove: (fileId: string) => apiFetch<void>(`files/${id(fileId)}`, { method: 'DELETE' }),

  view: (ownerId: string, fileId: string) => apiFetch<ViewLink>(`view/${id(ownerId)}/${id(fileId)}`),

  viewBySlug: (handle: string, slug: string) => apiFetch<ViewLink>(`u/${id(handle)}/${id(slug)}`),
};

/** Upload straight to Blob Storage with the SAS URL; XHR gives upload progress. */
export function putToBlob(
  ticket: UploadTicket,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', ticket.uploadUrl);
    for (const [name, value] of Object.entries(ticket.requiredHeaders)) xhr.setRequestHeader(name, value);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Blob upload failed (${xhr.status})`)));
    xhr.onerror = () => reject(new Error('Network error while uploading'));
    xhr.send(file);
  });
}
