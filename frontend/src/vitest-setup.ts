import "@testing-library/jest-dom/vitest"
import { vi } from "vitest"

// Default global fetch stub. Every existing test that exercises a real
// fetch call already stubs it explicitly per-test via
// vi.stubGlobal("fetch", ...) (see CorrectionsView.test.tsx,
// DocumentationView.test.tsx, ProvenanceMarker.test.tsx, api.test.ts,
// RunsView.test.tsx) and restores it via vi.unstubAllGlobals() afterwards,
// so this default is only ever reached by a test that never mocks fetch at
// all -- e.g. sourcePlugins/conformance.test.tsx, which renders a
// component that fires off an unawaited apiGet() in a useEffect purely as
// a side effect of mounting. Without this, that call falls through to
// Node's real fetch (undici), which -- unlike a real browser -- has no
// page origin to resolve a relative "/api/..." URL against, so it throws
// synchronously inside the returned promise ("Failed to parse URL from
// /api/..."). Because nothing in the test awaits or catches that promise,
// it surfaces as an unhandled rejection, which vitest treats as a real
// failure: the specific test's own assertions still pass, but the whole
// `vitest run` process exits 1 anyway. Confirmed live: `npx vitest run`
// exits 0 on this repo's baseline (no sourcePlugins/) and 1 once
// conformance.test.tsx exists, with an identical "N passed / 0 failed"
// summary in both cases -- the process exit code is the only signal that
// shows the difference.
globalThis.fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) })) as unknown as typeof fetch
