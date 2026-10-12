const API_HEALTH = 'http://localhost:7071/api/public/health';

/** Fails fast, with a useful message, when the API is not running. */
export default async function globalSetup() {
  const ok = await fetch(API_HEALTH).then((r) => r.ok).catch(() => false);
  if (!ok) {
    throw new Error(`La API no responde en ${API_HEALTH}. Levantala antes: en html-viewer-api, ./start.sh`);
  }
}
