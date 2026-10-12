import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useCopy } from '../shared/clipboard';
import { formatDate } from '../shared/format';
import { errorMessage } from '../shared/messages';
import { HtmlFrame } from '../shared/ui/HtmlFrame';
import { filesApi } from './api';

export function ViewerPage() {
  // Two routes land here: /u/{user}/{name} and the older /view/{ownerId}/{fileId}.
  const { ownerId = '', fileId = '', handle, slug = '' } = useParams();
  const { copy, copied } = useCopy();

  // The SAS URL is only needed for the initial load of the iframe; refetching
  // would hand back a new URL and reload the page, so the result is pinned.
  const { data, error, isPending } = useQuery({
    queryKey: handle ? ['view', 'u', handle, slug] : ['view', ownerId, fileId],
    queryFn: () => (handle ? filesApi.viewBySlug(handle, slug) : filesApi.view(ownerId, fileId)),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });

  return (
    <div className="viewer">
      <div className="viewer__bar">
        <Link to="/" className="btn btn--ghost">
          ← Mis archivos
        </Link>
        {data && (
          <>
            <div className="viewer__title">
              <strong>{data.file.title}</strong>
              <span className="muted small">
                {data.file.ownerName} · {formatDate(data.file.updatedAt)}
              </span>
            </div>
            <button type="button" className="btn btn--ghost" onClick={() => copy(window.location.href, 'page')}>
              {copied === 'page' ? 'Copiado' : 'Copiar enlace'}
            </button>
            <a className="btn btn--ghost" href={data.downloadUrl}>
              Descargar
            </a>
          </>
        )}
      </div>
      {isPending && <p className="muted pad">Abriendo…</p>}
      {error && <p className="error pad">{errorMessage(error)}</p>}
      {data && <HtmlFrame src={data.viewUrl} title={data.file.title} />}
    </div>
  );
}
