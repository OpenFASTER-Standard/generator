import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { IndexView } from "./IndexView"
import * as api from "../api"

describe("IndexView", () => {
  it("renders every page's fact_key, family, and a correction badge where is_correction is true", async () => {
    vi.spyOn(api, "fetchPages").mockResolvedValue({
      "key-a": {
        revision_count: 1,
        current: {
          revision_id: "r1",
          reference: { subject_document: { family: "Fam" }, selector: { type: "XPathSelector" }, reference_id: "id1" },
          author: "a",
          comment: "c",
          is_correction: false,
          created_at: "2026-01-01T00:00:00Z",
        },
      },
      "key-b": {
        revision_count: 2,
        current: {
          revision_id: "r2",
          reference: { subject_document: { family: "Fam" }, selector: { type: "XPathSelector" }, reference_id: "id2" },
          author: "a",
          comment: "c",
          is_correction: true,
          created_at: "2026-01-02T00:00:00Z",
        },
      },
    } as any)

    render(
      <MemoryRouter>
        <IndexView />
      </MemoryRouter>
    )

    expect(await screen.findByText("key-a")).toBeInTheDocument()
    expect(await screen.findByText("key-b")).toBeInTheDocument()
    expect(screen.getByText("key-b").closest("tr")).toHaveTextContent("Correction")
    expect(screen.getByText("key-a").closest("tr")).not.toHaveTextContent("Correction")
  })

  it("shows an empty state when there are no pages", async () => {
    vi.spyOn(api, "fetchPages").mockResolvedValue({})

    render(
      <MemoryRouter>
        <IndexView />
      </MemoryRouter>
    )

    expect(await screen.findByText(/no pages yet/i)).toBeInTheDocument()
  })

  it("shows an error alert when fetching pages fails", async () => {
    vi.spyOn(api, "fetchPages").mockRejectedValue(new Error("boom"))

    render(
      <MemoryRouter>
        <IndexView />
      </MemoryRouter>
    )

    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load the page index.*boom/i)
  })
})
