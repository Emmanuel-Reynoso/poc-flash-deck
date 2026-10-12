import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { labelsApi } from '../labels/api';
import { DeleteLabelDialog } from '../labels/DeleteLabelDialog';
import { LabelSection } from '../labels/LabelSection';
import { NewLabelForm } from '../labels/NewLabelForm';
import { RenameLabelDialog } from '../labels/RenameLabelDialog';
import type { Label } from '../labels/types';
import { absoluteUrl, useCopy } from '../shared/clipboard';
import { errorMessage } from '../shared/messages';
import { ShareDialog } from '../shares/ShareDialog';
import { filesApi, type FileChanges } from './api';
import { DeleteFileDialog } from './DeleteFileDialog';
import { EditLinkDialog } from './EditLinkDialog';
import { FileRow, type FileAction } from './FileRow';
import { viewPath } from './paths';
import { RenameFileDialog } from './RenameFileDialog';
import type { HtmlFile } from './types';

const CHANGE_KEY = ['file-change'];

/** The dialog that is open, if any. One at a time. */
type OpenDialog =
  | { on: 'file'; action: FileAction; file: HtmlFile }
  | { on: 'label'; action: 'rename' | 'delete'; label: Label };

/** "Mis archivos": the user's files, grouped under their labels. */
export function FilesList() {
  const queryClient = useQueryClient();
  const { data: files, isPending, error } = useQuery({ queryKey: ['files'], queryFn: filesApi.list });
  const { data: labels = [] } = useQuery({ queryKey: ['labels'], queryFn: labelsApi.list });
  const [open, setOpen] = useState<OpenDialog | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const { copy, copied } = useCopy();
  const close = () => setOpen(null);

  // Visibility and label change in place, without a dialog.
  const change = useMutation({
    mutationKey: CHANGE_KEY,
    // One at a time, in the order the user made them: two quick moves of the
    // same file must reach the server in that order.
    scope: { id: 'file-changes' },
    mutationFn: ({ id, ...changes }: { id: string } & FileChanges) => filesApi.update(id, changes),
    // Moving between labels shows at once; the server answer confirms or undoes it.
    onMutate: async ({ id, labelId }) => {
      setProblem(null);
      if (labelId === undefined) return undefined;
      await queryClient.cancelQueries({ queryKey: ['files'] });
      const previous = queryClient.getQueryData<HtmlFile[]>(['files']);
      queryClient.setQueryData<HtmlFile[]>(['files'], (list) => list?.map((f) => (f.id === id ? { ...f, labelId } : f)));
      return { previous };
    },
    onError: (err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(['files'], context.previous);
      setProblem(errorMessage(err));
    },
    // Reload once the last queued change is done; earlier would show a stale middle step.
    onSettled: () => {
      if (queryClient.isMutating({ mutationKey: CHANGE_KEY }) === 1) {
        return queryClient.invalidateQueries({ queryKey: ['files'] });
      }
    },
  });

  if (isPending) return <p className="muted">Cargando archivos…</p>;
  if (error) return <p className="error">{errorMessage(error)}</p>;

  const known = new Set(labels.map((l) => l.id));
  const inLabel = (label: Label | null) =>
    files.filter((f) => (label ? f.labelId === label.id : !f.labelId || !known.has(f.labelId)));

  const row = (f: HtmlFile) => (
    <FileRow
      key={f.id}
      file={f}
      labels={labels}
      busy={change.isPending}
      dragging={draggingId === f.id}
      copied={copied === f.id}
      onCopy={() => copy(absoluteUrl(viewPath(f)), f.id)}
      onAction={(action) => setOpen({ on: 'file', action, file: f })}
      onChange={(changes) => change.mutate({ id: f.id, ...changes })}
      onDragStart={() => setDraggingId(f.id)}
      onDragEnd={() => setDraggingId(null)}
    />
  );

  const moveTo = (label: Label | null) => (fileId: string) => {
    setDraggingId(null);
    const file = files.find((f) => f.id === fileId);
    const target = label?.id ?? null;
    if (file && (file.labelId ?? null) !== target) change.mutate({ id: fileId, labelId: target });
  };

  return (
    <>
      <NewLabelForm />

      {problem && (
        <p className="notice" role="alert">
          {problem}
          <button type="button" className="icon-button" aria-label="Cerrar aviso" onClick={() => setProblem(null)}>
            ×
          </button>
        </p>
      )}

      {files.length === 0 && labels.length === 0 && (
        <div className="empty">
          <p>Todavía no subiste archivos.</p>
          <p className="muted">Los que subas van a aparecer acá, listos para abrir y compartir.</p>
        </div>
      )}

      {labels.length === 0
        ? files.length > 0 && <ul className="files">{files.map(row)}</ul>
        : [null, ...labels].map((label) => {
            const items = inLabel(label);
            return (
              <LabelSection
                key={label?.id ?? 'none'}
                label={label}
                count={items.length}
                dragActive={draggingId !== null}
                onDropFile={moveTo(label)}
                onAction={label ? (action) => setOpen({ on: 'label', action, label }) : undefined}
              >
                {items.map(row)}
              </LabelSection>
            );
          })}

      {open?.on === 'file' && open.action === 'share' && <ShareDialog file={open.file} onClose={close} />}
      {open?.on === 'file' && open.action === 'rename' && <RenameFileDialog file={open.file} onClose={close} />}
      {open?.on === 'file' && open.action === 'link' && <EditLinkDialog file={open.file} onClose={close} />}
      {open?.on === 'file' && open.action === 'delete' && <DeleteFileDialog file={open.file} onClose={close} />}
      {open?.on === 'label' && open.action === 'rename' && <RenameLabelDialog label={open.label} onClose={close} />}
      {open?.on === 'label' && open.action === 'delete' && (
        <DeleteLabelDialog label={open.label} fileCount={inLabel(open.label).length} onClose={close} />
      )}
    </>
  );
}
