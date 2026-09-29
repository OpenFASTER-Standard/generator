import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { App } from "./App"
import * as api from "./api"

beforeEach(() => {
  vi.restoreAllMocks()
})

describe("App", () => {
  it("renders a persistent nav with links to all three top-level views", async () => {
    vi.spyOn(api, "fetchPages").mockResolvedValue({})

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    )

    expect(screen.getByRole("link", { name: "Pages" })).toHaveAttribute("href", "/")
    expect(screen.getByRole("link", { name: "Add citation" })).toHaveAttribute("href", "/add")
    expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute("href", "/review")
  })
})
