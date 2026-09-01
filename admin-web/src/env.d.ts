interface ImportMetaEnv { readonly VITE_API_URL?: string }
interface ImportMeta { readonly env: ImportMetaEnv }
declare module "react-dom/client" {
  import type { ReactNode } from "react";
  export function createRoot(container: Element | DocumentFragment): { render(children: ReactNode): void };
}
declare module "vite" { export function defineConfig(config: unknown): unknown; }
declare module "@vitejs/plugin-react" { export default function react(): unknown; }
