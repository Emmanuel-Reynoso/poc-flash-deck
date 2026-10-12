import { useCallback, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { errorMessage } from '../../shared/messages';
import { filesApi, putToBlob } from '../api';

export interface UploadItem {
  key: string;
  name: string;
  progress: number;
  status: 'uploading' | 'done' | 'error';
  error?: string;
}

const CONCURRENCY = 3;

/** Uploads files in parallel (bounded), tracking progress per file. */
export function useUploadQueue() {
  const queryClient = useQueryClient();
  const [items, setItems] = useState<UploadItem[]>([]);
  const counter = useRef(0);

  const patch = useCallback((key: string, changes: Partial<UploadItem>) => {
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...changes } : it)));
  }, []);

  const uploadOne = useCallback(
    async (key: string, file: File) => {
      try {
        const ticket = await filesApi.startUpload(file);
        await putToBlob(ticket, file, (p) => patch(key, { progress: Math.min(p, 0.99) }));
        await filesApi.completeUpload(ticket.file.id);
        patch(key, { status: 'done', progress: 1 });
        await queryClient.invalidateQueries({ queryKey: ['files'] });
      } catch (err) {
        patch(key, { status: 'error', error: errorMessage(err) });
      }
    },
    [patch, queryClient],
  );

  const enqueue = useCallback(
    async (files: File[]) => {
      const jobs = files.map((file) => ({ key: `u${++counter.current}`, file }));
      setItems((prev) => [
        ...jobs.map(({ key, file }) => ({ key, name: file.name, progress: 0, status: 'uploading' as const })),
        ...prev,
      ]);

      let next = 0;
      const worker = async () => {
        while (next < jobs.length) {
          const job = jobs[next++];
          await uploadOne(job.key, job.file);
        }
      };
      await Promise.all(Array.from({ length: Math.min(CONCURRENCY, jobs.length) }, worker));
    },
    [uploadOne],
  );

  /** Adds client-side rejections (wrong type, too big) to the same list. */
  const reject = useCallback((entries: { name: string; error: string }[]) => {
    setItems((prev) => [
      ...entries.map((e) => ({ key: `u${++counter.current}`, name: e.name, progress: 0, status: 'error' as const, error: e.error })),
      ...prev,
    ]);
  }, []);

  const clearFinished = useCallback(() => setItems((prev) => prev.filter((it) => it.status === 'uploading')), []);

  return { items, enqueue, reject, clearFinished };
}
