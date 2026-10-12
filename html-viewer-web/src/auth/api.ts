import type { ClientPrincipal } from './types';

/** Identity from Static Web Apps' built-in auth endpoint. */
export async function getPrincipal(): Promise<ClientPrincipal | null> {
  const res = await fetch('/.auth/me', { credentials: 'same-origin' });
  if (!res.ok) return null;
  const body = (await res.json()) as { clientPrincipal: ClientPrincipal | null };
  return body.clientPrincipal;
}

export function redirectToLogin(returnTo: string = window.location.pathname + window.location.search) {
  window.location.assign(`/.auth/login/aad?post_login_redirect_uri=${encodeURIComponent(returnTo)}`);
}

export const logoutUrl = '/.auth/logout?post_logout_redirect_uri=/';
