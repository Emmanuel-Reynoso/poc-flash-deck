import { useState, type DragEvent, type ReactNode } from 'react';
import { FILE_DRAG_TYPE } from '../files/drag';
import type { Label } from './types';

interface Props {
  /** null is the "Sin etiqueta" section. */
  label: Label | null;
  count: number;
  /** A file is being dragged somewhere on the page. */
  dragActive: boolean;
  onDropFile: (fileId: string) => void;
  /** Opens the dialog for that action. Absent on "Sin etiqueta". */
  onAction?: (action: 'rename' | 'delete') => void;
  children: ReactNode;
}

/** A header with its files. Dropping a file here moves it to this label. */
export function LabelSection({ label, count, dragActive, onDropFile, onAction, children }: Props) {
  const [over, setOver] = useState(false);
  const name = label?.name ?? 'Sin etiqueta';
  const accepts = (e: DragEvent) => e.dataTransfer.types.includes(FILE_DRAG_TYPE);
  // A drop is only allowed where the last enter/over was accepted, so both are handled.
  const allowDrop = (e: DragEvent) => {
    if (!accepts(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setOver(true);
  };

  return (
    <section
      className={`label${dragActive ? ' is-target' : ''}${over ? ' is-over' : ''}`}
      aria-label={label ? `Etiqueta ${name}` : name}
      onDragEnter={allowDrop}
      onDragOver={allowDrop}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false);
      }}
      onDrop={(e) => {
        if (!accepts(e)) return;
        e.preventDefault();
        setOver(false);
        onDropFile(e.dataTransfer.getData(FILE_DRAG_TYPE));
      }}
    >
      <header className="label__header">
        <h2 className="label__name">{name}</h2>
        <span className="muted small">{count}</span>
        {onAction && (
          <div className="label__actions">
            <button type="button" className="btn btn--ghost" onClick={() => onAction('rename')}>
              Renombrar
            </button>
            <button type="button" className="btn btn--ghost btn--danger" onClick={() => onAction('delete')}>
              Eliminar
            </button>
          </div>
        )}
      </header>
      {count > 0 ? <ul className="files">{children}</ul> : <p className="label__empty">Arrastrá archivos acá.</p>}
    </section>
  );
}
