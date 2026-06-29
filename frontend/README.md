# frontend

Vue 3 + Vite + TypeScript SPA — Pinia, Vue Router, Tailwind CSS v4, Vitest.
Wrapped by Capacitor for the iOS app in a later slice.

```bash
pnpm install
pnpm dev        # http://localhost:5173 (proxies /api → backend on :8000)
pnpm test       # Vitest
pnpm typecheck  # vue-tsc
pnpm build      # type-check + production build
```

Run the backend (`uvicorn app.main:app --reload`) alongside `pnpm dev`; the Vite
dev server proxies `/api/*` to it (stripping the prefix).

Structure: `lib/api.ts` (fetch wrapper), `stores/auth.ts` (Pinia auth + JWT),
`router/` (auth-guarded routes), `views/`, `components/`. Tests are co-located
`*.spec.ts`. ESLint not yet configured (deferred).
