import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { RunsView } from "@/components/RunsView"

const runs = [
  { runId: "run-a", createdAt: "2026-09-15T09:00:00Z", xsdPath: "a.xsd", pdfPath: "a.pdf" },
  { runId: "run-b", createdAt: "2026-09-16T09:00:00Z", xsdPath: "b.xsd", pdfPath: "b.pdf" },
]

describe("RunsView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("lists every real run", () => {
    render(<RunsView runs={runs} />)
    // Scoped to the table specifically: Base UI's Select renders every
    // SelectItem into the DOM even while closed (unlike Radix-style
    // mount-on-open), so a page-wide getByText("run-a") also matches each
    // run's own <SelectItem> in both the "from"/"to" pickers below the
    // table -- a real, confirmed Base UI behavior, not a test bug.
    const table = within(screen.getByRole("table"))
    expect(table.getByText("run-a")).toBeInTheDocument()
    expect(table.getByText("run-b")).toBeInTheDocument()
  })

  it("fetches and shows a diff between two selected runs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ added: [["s", "p", "new"]], removed: [["s", "p", "old"]] }),
      }),
    )

    render(<RunsView runs={runs} />)
    await userEvent.click(screen.getByRole("button", { name: /diff/i }))

    expect(await screen.findByText(/new/)).toBeInTheDocument()
    expect(await screen.findByText(/old/)).toBeInTheDocument()
  })
})
