/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** e.g. http://localhost:8000/api/v1 (see .env.example). Empty means same-origin. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
