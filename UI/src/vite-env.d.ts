/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Base URL of the FastAPI backend. Injected at build time from
   * `.env.production` / `.env.development` / shell env vars.
   *
   * Must NOT include a trailing slash. The client appends the path itself.
   */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}