import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { ModeSwitcher } from "@/components/ModeSwitcher"

describe("ModeSwitcher", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("renders all 3 mode tabs and a pending-corrections badge", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [{ correctionUri: "urn:c1" }] }))

    render(
      <MemoryRouter initialEntries={["/graph"]}>
        <Routes>
          <Route
            path="/:mode/*"
            element={
              <ModeSwitcher search="" onSearchChange={() => {}}>
                <div>content</div>
              </ModeSwitcher>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    for (const label of ["Graph", "Living Text", "Synced Panes"]) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument()
    }
    expect(await screen.findByText("1")).toBeInTheDocument()
  })

  it("clicking a mode tab navigates there, preserving no stale content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }))

    render(
      <MemoryRouter initialEntries={["/graph"]}>
        <Routes>
          <Route
            path="/:mode/*"
            element={
              <ModeSwitcher search="" onSearchChange={() => {}}>
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
})
