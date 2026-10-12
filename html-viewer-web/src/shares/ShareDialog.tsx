import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { viewPath } from '../files/paths';
import type { HtmlFile } from '../files/types';
import { absoluteUrl, useCopy } from '../shared/clipboard';
import { formatDay } from '../shared/format';
import { errorMessage } from '../shared/messages';
import { Dialog } from '../shared/ui/Dialog';
import { sharesApi } from './api';
import { sharePath } from './paths';

const DURATIONS = [
  { days: 1, label: '1 día' },
  { days: 7, label: '7 días' },
  { days: 30, label: '30 días' },
];

export function ShareDialog({ file, onClose }: { file: HtmlFile; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [days, setDays] = useState(7);
  const { copy, copied } = useCopy();
  const key = ['shares', file.id];
  const shareUrl = (token: string) => absoluteUrl(sharePath(file, token));

  const { data: shares, isPending } = useQuery({ queryKey: key, queryFn: () => sharesApi.list(file.id) });

  const create = useMutation({
    mutationFn: () => sharesApi.create(file.id, days),
    onSuccess: async (share) => {
      await queryClient.invalidateQueries({ queryKey: key });
      void copy(shareUrl(share.token), share.token);
    },
  });

  const revoke = useMutation({
    mutationFn: sharesApi.revoke,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const internal = absoluteUrl(viewPath(file));

  return (
    <Dialog title={`Compartir “${file.title}”`} onClose={onClose}>
      <section className="dialog__section">
        <h3>Dentro de la organización</h3>
        <p className="muted">
          {file.visibility === 'org'
            ? 'Cualquier persona de la organización que inicie sesión puede abrirlo con este enlace.'
            : 'Ahora solo vos podés abrirlo. Cambiá la visibilidad a “Organización” en la lista para compartirlo internamente.'}
        </p>
        <div className="copy-row">
          <input readOnly value={internal} onFocus={(e) => e.currentTarget.select()} aria-label="Enlace interno" />
          <button type="button" className="btn" onClick={() => copy(internal, 'internal')}>
            {copied === 'internal' ? 'Copiado' : 'Copiar'}
          </button>
        </div>
      </section>

      <section className="dialog__section">
        <h3>Enlace público con vencimiento</h3>
        <p className="muted">Lo abre cualquiera que tenga el enlace, sin iniciar sesión. Podés revocarlo cuando quieras.</p>
        <div className="copy-row">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Duración">
            {DURATIONS.map((d) => (
              <option key={d.days} value={d.days}>
                Vence en {d.label}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn--primary" disabled={create.isPending} onClick={() => create.mutate()}>
            Crear enlace
          </button>
        </div>
        {create.error && <p className="error">{errorMessage(create.error)}</p>}

        {isPending ? (
          <p className="muted">Cargando…</p>
        ) : shares && shares.length > 0 ? (
          <ul className="shares">
            {shares.map((s) => (
              <li key={s.token}>
                <span className="shares__expiry">Vence el {formatDay(s.expiresAt)}</span>
                <button type="button" className="btn btn--ghost" onClick={() => copy(shareUrl(s.token), s.token)}>
                  {copied === s.token ? 'Copiado' : 'Copiar'}
                </button>
                <button
                  type="button"
                  className="btn btn--ghost btn--danger"
                  disabled={revoke.isPending}
                  onClick={() => revoke.mutate(s.token)}
                >
                  Revocar
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">No hay enlaces públicos activos.</p>
        )}
      </section>
    </Dialog>
  );
}
