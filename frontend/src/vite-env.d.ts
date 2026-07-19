/// <reference types="vite/client" />

/**
 * Typed build-time environment.
 *
 * Declaring the vars we read means a typo in `import.meta.env.VITE_API_BSE_URL`
 * is a compile error rather than a silent undefined at runtime.
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
