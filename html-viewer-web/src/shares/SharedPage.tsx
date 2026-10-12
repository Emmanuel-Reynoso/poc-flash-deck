import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { formatDate } from '../shared/format';
import { HtmlFrame } from '../shared/ui/HtmlFrame';
import { sharesApi } from './api';

/** Anonymous view through a public, expiring share link. */
export function SharedPage() {
  // Two routes land here: /s/{user}/{name}-{token} and the older /share/{token}.
  const { token = '', handle, slugAndToken = '' } = useParams();
  const { data, error, isPending } = useQuery({
    queryKey: handle ? ['shared', handle, slugAndToken] : ['shared', token],
    queryFn: () => (handle ? sharesApi.resolveReadable(handle, slugAndToken) : sharesApi.resolve(token)),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });

  return (
    <div className="viewer">
      <div className="viewer__bar">
        <span className="brand brand--small">Visor HTML</span>
        {data && (
          <>
            <div className="viewer__title">
              <strong>{data.file.title}</strong>
              <span className="muted small">
                Compartido por {data.file.ownerName} · {formatDate(data.file.updatedAt)}
              </span>
            </div>
            <a className="btn btn--ghost" href={data.downloadUrl}>
              Descargar
            </a>
          </>
        )}
      </div>
      {isPending && <p className="muted pad">Abriendo…</p>}
      {error && (
        <div className="empty">
          <p>Este enlace no existe o ya venció.</p>
          <p className="muted">Pedile a quien te lo compartió que genere uno nuevo.</p>
        </div>
      )}
      {data && <HtmlFrame src={data.viewUrl} title={data.file.title} />}
    </div>
  );
}
