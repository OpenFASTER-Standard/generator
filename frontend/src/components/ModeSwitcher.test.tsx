import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"
import { ModeSwitcher } from "@/components/ModeSwitcher"

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}</div>
}

describe("ModeSwitcher", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("renders all mode tabs and a pending-corrections badge", async () => {
    render(
      <MemoryRouter initialEntries={["/graph"]}>
        <Routes>
          <Route
            path="/:mode/*"
            element={
              <ModeSwitcher search="" onSearchChange={() => {}} reviewer="julian" onReviewerChange={() => {}} pendingCount={1}>
                <div>content</div>
              </ModeSwitcher>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    for (const label of ["Graph", "Living Text", "Synced Panes", "Sources", "Triples", "Runs"]) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument()
    }
    expect(await screen.findByText("1")).toBeInTheDocument()
  })

  // Regression test: the "Reviewing as" field used to be a fixed 2-option
  // dropdown (`["julian", "someone-else"]`) -- a hardcoded guest list that
  // makes no sense for a real maker-checker workflow with more than one
  // real reviewer. It's a free-text field now so any real name works
  // without needing to be baked into the source.
  it("lets you type any reviewer name into the free-text 'Reviewing as' field", async () => {
    const onReviewerChange = vi.fn()
    render(
      <MemoryRouter initialEntries={["/graph"]}>
        <Routes>
          <Route
            path="/:mode/*"
            element={
              <ModeSwitcher search="" onSearchChange={() => {}} reviewer="" onReviewerChange={onReviewerChange} pendingCount={0}>
                <div>content</div>
              </ModeSwitcher>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    await userEvent.type(screen.getByLabelText("Reviewing as"), "a")

    expect(onReviewerChange).toHaveBeenCalledWith("a")
  })

  it("clicking a mode tab navigates there, preserving no stale content", async () => {
    render(
      <MemoryRouter initialEntries={["/graph"]}>
        <Routes>
          <Route
            path="/:mode/*"
            element={
              <ModeSwitcher search="" onSearchChange={() => {}} reviewer="julian" onReviewerChange={() => {}} pendingCount={0}>
                <div>content</div>
              </ModeSwitcher>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole("tab", { name: "Living Text" }))
    // The underlying @base-ui/react Tabs primitive marks the active tab via
    // `aria-selected`/`data-active`, not `data-selected` (that attribute is
    // reserved for Select/Combobox items in this library) -- confirmed by
    // inspecting the rendered DOM.
    expect(screen.getByRole("tab", { name: "Living Text" })).toHaveAttribute("aria-selected", "true")
  })

  // Regression test for a real bug this plan's Task 16 E2E suite caught
  // live: switching modes via these header tabs used to call
  // `setFocus({ mode: value })`, dropping the currently focused `subject`
  // entirely -- defeating the DoD's own "mode-switch-preserves-focus"
  // requirement (a click-to-pin focus was silently lost the moment you
  // switched tabs). Uses the app's own real route shape
  // (`/:mode/:subject?/:predicate?/:lang?`, see App.tsx/lib/focus.ts)
  // rather than the old `/:mode/*` shape this file's other two tests still
  // use for their own narrower purposes -- that flat pattern is what
  // actually carries `subject` across a mode switch.
  it("clicking a mode tab preserves the currently focused subject", async () => {
    render(
      <MemoryRouter initialEntries={["/living-text/urn%3Asubject-1"]}>
        <Routes>
          <Route
            path="/:mode/:subject?/:predicate?/:lang?"
            element={
              <ModeSwitcher search="" onSearchChange={() => {}} reviewer="julian" onReviewerChange={() => {}} pendingCount={0}>
                <LocationProbe />
              </ModeSwitcher>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId("location").textContent).toBe("/living-text/urn%3Asubject-1")

    await userEvent.click(screen.getByRole("tab", { name: "Graph" }))

    expect(screen.getByTestId("location").textContent).toBe("/graph/urn%3Asubject-1")
  })
})
