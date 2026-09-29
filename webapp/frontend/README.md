# MiKaDiv-FM References webapp frontend

A Vite + React + TypeScript single-page app serving `generator`'s references
catalog: browsing pages and their revision history, browsing citable
candidates and submitting new citations, and the drift-review pipeline. See
`docs/specs/2026-09-29-webapp-react-rebuild-design.md`.

Built entirely from `@openfaster-standard/ui` (the shared OpenFASTER
component library) plus React Router for client-side routing. `webapp/app.py`
(FastAPI) serves this build's output (`../frontend_dist/`, see
`vite.config.ts`) and the `/api/*` endpoints it calls.

## Commands

- `npm run dev` -- Vite dev server with hot reload.
- `npm run build` -- typechecks (`tsc -b`) then builds to `../frontend_dist/`.
- `npm test` -- runs the Vitest suite (`src/**/*.test.tsx`).
- `npm run lint` -- oxlint.
