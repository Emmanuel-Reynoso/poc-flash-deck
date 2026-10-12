import type { ReactNode } from 'react';
import { createContext, useContext, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPrincipal, redirectToLogin } from './api';
import type { ClientPrincipal } from './types';

const PrincipalContext = createContext<ClientPrincipal | null>(null);

export const usePrincipal = () => useContext(PrincipalContext);

/**
 * UX guard: sends anonymous visitors to the Entra ID login.
 * The real access control lives in the API (SWA route rules + handler checks).
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const { data: principal, isPending, isError } = useQuery({
    queryKey: ['principal'],
    queryFn: getPrincipal,
    staleTime: 5 * 60_000,
  });

  const anonymous = !isPending && !isError && !principal;
  useEffect(() => {
    if (anonymous) redirectToLogin();
  }, [anonymous]);

  if (isError) return <p className="error pad">No se pudo verificar la sesión. Recargá la página.</p>;
  if (!principal) return <p className="muted pad">Ingresando…</p>;
  return <PrincipalContext.Provider value={principal}>{children}</PrincipalContext.Provider>;
}
