import { ApiError } from './http';

const BY_CODE: Record<string, string> = {
  unsupported_type: 'Solo se aceptan archivos .html o .htm.',
  payload_too_large: 'El archivo supera el tamaño máximo permitido.',
  upload_missing: 'El archivo no terminó de subirse. Probá de nuevo.',
  not_found: 'No existe o no tenés acceso.',
  slug_taken: 'Ya tenés otro archivo con ese nombre de enlace.',
  invalid_slug: 'El nombre del enlace tiene que tener letras o números.',
  label_exists: 'Ya tenés una etiqueta con ese nombre.',
  label_limit: 'Llegaste al máximo de etiquetas.',
  label_not_found: 'Esa etiqueta ya no existe.',
  unauthorized: 'Tu sesión expiró. Volvé a ingresar.',
};

/** Spanish, user-facing text for any error thrown by the API layer. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return BY_CODE[err.code] ?? 'Algo salió mal. Probá de nuevo en un momento.';
  if (err instanceof Error && /network/i.test(err.message)) return 'Problema de conexión. Revisá tu red.';
  return 'Algo salió mal. Probá de nuevo en un momento.';
}
