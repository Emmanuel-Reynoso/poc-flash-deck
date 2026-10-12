import { Link } from 'react-router-dom';
import type { Label } from '../labels/types';
import { formatBytes, formatDate } from '../shared/format';
import type { FileChanges } from './api';
import { FILE_DRAG_TYPE } from './drag';
import { viewPath } from './paths';
import type { HtmlFile } from './types';

export type FileAction = 'share' | 'rename' | 'link' | 'delete';

interface Props {
  file: HtmlFile;
  labels: Label[];
  busy: boolean;
  dragging: boolean;
  copied: boolean;
  onCopy: () => void;
  /** Opens the dialog for that action. */
  onAction: (action: FileAction) => void;
  /** Changes that need no dialog: visibility and label. */
  onChange: (changes: FileChanges) => void;
  onDragStart: () => void;
  onDragEnd: () => void;
}

export function FileRow({ file: f, labels, busy, dragging, copied, onCopy, onAction, onChange, onDragStart, onDragEnd }: Props) {
  const isOrg = f.visibility === 'org';
  const canMove = labels.length > 0;

  return (
    <li
      className={`file${canMove ? ' file--movable' : ''}${dragging ? ' is-dragging' : ''}`}
      draggable={canMove}
      onDragStart={(e) => {
        e.dataTransfer.setData(FILE_DRAG_TYPE, f.id);
        e.dataTransfer.effectAllowed = 'move';
        onDragStart();
      }}
      onDragEnd={onDragEnd}
    >
      {canMove && (
        <span className="file__grip" aria-hidden="true" title="Arrastrá para mover a otra etiqueta">
          ⠿
        </span>
      )}
      <div className="file__main">
        <Link to={viewPath(f)} className="file__title" draggable={false}>
          {f.title}
        </Link>
        <p className="file__meta">
          {f.fileName} · {formatBytes(f.sizeBytes)} · {formatDate(f.createdAt)}
          {f.slug && <> · {viewPath(f)}</>}
        </p>
      </div>

      <button
        type="button"
        className={`badge${isOrg ? ' badge--org' : ''}`}
        title={isOrg ? 'Cualquier persona de la organización con el enlace puede verlo' : 'Solo vos podés verlo'}
        disabled={busy}
        onClick={() => onChange({ visibility: isOrg ? 'private' : 'org' })}
      >
        {isOrg ? 'Organización' : 'Solo yo'}
      </button>

      <div className="file__actions">
        <button type="button" className="btn btn--ghost" onClick={onCopy}>
          {copied ? 'Copiado' : 'Copiar enlace'}
        </button>
        <button type="button" className="btn btn--ghost" onClick={() => onAction('share')}>
          Compartir
        </button>
        <button type="button" className="btn btn--ghost" onClick={() => onAction('rename')}>
          Renombrar
        </button>
        <button type="button" className="btn btn--ghost" onClick={() => onAction('link')}>
          Editar enlace
        </button>
        <button type="button" className="btn btn--ghost btn--danger" onClick={() => onAction('delete')}>
          Eliminar
        </button>
        {canMove && (
          // Same as dragging the row, for keyboard and touch.
          <select
            className="file__label"
            aria-label={`Etiqueta de ${f.title}`}
            value={f.labelId ?? ''}
            onChange={(e) => onChange({ labelId: e.target.value || null })}
          >
            <option value="">Sin etiqueta</option>
            {labels.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        )}
      </div>
    </li>
  );
}
