/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Client-side size limit, must match MAX_UPLOAD_MB in the API. */
  readonly VITE_MAX_UPLOAD_MB?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
