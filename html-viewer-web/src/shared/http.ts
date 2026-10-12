import { redirectToLogin } from '../auth/api';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string };
}

/** JSON fetch against the API behind Static Web Apps (same origin, cookie auth). */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/${path}`, {
    ...init,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });

  if (res.status === 401 && !path.startsWith('public/')) {
    redirectToLogin();
    throw new ApiError(401, 'unauthorized', 'La sesión expiró.');
  }
  if (res.status === 204) return undefined as T;

  const body = (await res.json().catch(() => null)) as (T & ErrorBody) | null;
  if (!res.ok) {
    throw new ApiError(res.status, body?.error?.code ?? 'http_error', body?.error?.message ?? `Error ${res.status}`);
  }
  return body as T;
}

export const jsonBody = (value: unknown): RequestInit => ({ body: JSON.stringify(value) });
