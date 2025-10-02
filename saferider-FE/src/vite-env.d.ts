interface ImportMetaEnv {
  readonly VITE_KAKAO_JS_KEY: string;
  readonly VITE_API_BASE?: string;
}
interface ImportMeta { readonly env: ImportMetaEnv }