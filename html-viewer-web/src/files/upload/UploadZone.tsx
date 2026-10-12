import { useDropzone, type FileRejection } from 'react-dropzone';
import { useUploadQueue } from './useUploadQueue';

const MAX_MB = Number(import.meta.env.VITE_MAX_UPLOAD_MB ?? 20);

function rejectionText(r: FileRejection): string {
  const code = r.errors[0]?.code;
  if (code === 'file-too-large') return `Supera los ${MAX_MB} MB.`;
  if (code === 'file-invalid-type') return 'Solo se aceptan archivos .html o .htm.';
  return 'Archivo no válido.';
}

export function UploadZone() {
  const { items, enqueue, reject, clearFinished } = useUploadQueue();

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    accept: { 'text/html': ['.html', '.htm'] },
    maxSize: MAX_MB * 1024 * 1024,
    noClick: true,
    onDrop: (accepted, rejected) => {
      if (rejected.length) reject(rejected.map((r) => ({ name: r.file.name, error: rejectionText(r) })));
      if (accepted.length) void enqueue(accepted);
    },
  });

  const finished = items.some((it) => it.status !== 'uploading');

  return (
    <section className="upload">
      <div {...getRootProps({ className: `dropzone${isDragActive ? ' is-active' : ''}` })}>
        <input {...getInputProps()} />
        <svg className="dropzone__icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 16V4m0 0l-4.5 4.5M12 4l4.5 4.5M5 15v3a2 2 0 002 2h10a2 2 0 002-2v-3" />
        </svg>
        <p className="dropzone__title">{isDragActive ? 'Soltá los archivos acá' : 'Arrastrá tus archivos HTML'}</p>
        <p className="dropzone__hint">
          o{' '}
          <button type="button" className="link-button" onClick={open}>
            elegilos desde tu equipo
          </button>{' '}
          · .html / .htm · hasta {MAX_MB} MB
        </p>
      </div>

      {items.length > 0 && (
        <div className="uploads">
          <ul>
            {items.map((it) => (
              <li key={it.key} className={`upload-item upload-item--${it.status}`}>
                <span className="upload-item__name" title={it.name}>
                  {it.name}
                </span>
                {it.status === 'uploading' && (
                  <span className="progress" aria-label={`Subiendo ${Math.round(it.progress * 100)}%`}>
                    <span style={{ width: `${Math.max(4, it.progress * 100)}%` }} />
                  </span>
                )}
                {it.status === 'done' && <span className="upload-item__state">Listo</span>}
                {it.status === 'error' && <span className="upload-item__state">{it.error}</span>}
              </li>
            ))}
          </ul>
          {finished && (
            <button type="button" className="link-button uploads__clear" onClick={clearFinished}>
              Limpiar
            </button>
          )}
        </div>
      )}
    </section>
  );
}
