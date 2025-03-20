# RAG Quality Monitor — frontend

React 18 + TypeScript (strict) + Vite dashboard for the RAG Quality Monitor API.

## Scripts

| command | what it does |
| --- | --- |
| `npm run dev` | Vite dev server on <http://127.0.0.1:5173> with `/api` and `/health` proxied to the backend |
| `npm run build` | `tsc -b` (strict type check) followed by `vite build` |
| `npm run preview` | serves the production build with the same proxy |
| `npm test` | Vitest unit tests for the pure helpers in `src/lib` |
| `npm run typecheck` | type check only |
| `npm run e2e` | Playwright browser tests (starts the dev server automatically) |

## API base URL resolution

`src/api.ts` resolves the base URL once at module load:

1. `VITE_API_BASE` is set to a non-empty value → used verbatim (absolute URL).
2. Otherwise → same-origin relative `/api` paths.

Same-origin is the default for both shipped setups: the Vite dev server
proxies `/api` to the backend, and the production Docker image serves the SPA
from nginx, which proxies `/api` to the backend container. Set
`VITE_API_BASE` only when the API is served from a different host.

The dev/preview **proxy target** can be overridden with `VITE_API_TARGET`
(default `http://127.0.0.1:8000`). In the container image the proxy is
configured by `deploy/nginx.conf.template` through `RQM_BACKEND_HOST` and
`RQM_BACKEND_PORT`.

## Structure

```
src/
  api.ts              typed API client (one function per backend endpoint)
  types.ts            re-exports of the TypeScript mirrors of the backend contract
  model/domain.ts     persisted domain entities (projects, apps, runs, results …)
  model/api.ts        composite API payloads (overview, compare, drift, system …)
  main.tsx            router + theme provider entry point
  lib/                pure helpers (formatting, badges, errors, downloads, JSON)
    lib.test.ts       Vitest unit tests
  components/         shared UI (layout, tables, drawer, editors, charts)
  pages/              one file per route
  styles/             CSS custom properties + component/layout/page styles
  theme/              light/dark ThemeProvider (localStorage + OS preference)
e2e/
  dashboard.spec.ts   Playwright smoke tests for the main routes
  smoke.spec.ts       Playwright check that every route renders without crashing
```

## Routes

`/` overview · `/runs` · `/runs/new` · `/runs/:id` · `/applications` · `/datasets` ·
`/metrics` · `/compare` · `/regressions` · `/drift` · `/gates` · `/providers` ·
`/evidence` · `/reports` · `/system`

## Conventions

- A metric value of `null` is rendered as `—`; a metric computed over `n === 0`
  samples is additionally flagged as *no evidence* so a zero is never mistaken
  for a measurement.
- Every backend failure surfaces the FastAPI `detail` message (see
  `src/lib/errors.ts`).
- Demo projects are marked with a `DEMO` badge everywhere a project is shown.
