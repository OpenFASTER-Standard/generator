import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { PageDetailView } from "./PageDetailView"
import * as api from "../api"

describe("PageDetailView", () => {
  it("renders the summary line and history table, newest revision first", async () => {
    vi.spyOn(api, "fetchPage").mockResolvedValue({
      fact_key: "k",
      current: {
        revision_id: "r2",
        reference: { subject_document: { family: "Fam" }, selector: { type: "XPathSelector" }, reference_id: "id" },
        author: "a2",
        comment: "second",
        is_correction: true,
        created_at: "2026-01-02T00:00:00Z",
      },
      history: [
        {
          revision_id: "r1",
          reference: {},
          author: "a1",
          comment: "first",
          is_correction: false,
          created_at: "2026-01-01T00:00:00Z",
        },
        {
          revision_id: "r2",
          reference: {},
          author: "a2",
          comment: "second",
          is_correction: true,
          created_at: "2026-01-02T00:00:00Z",
        },
      ],
    } as any)

    render(
      <MemoryRouter initialEntries={["/pages/k"]}>
        <Routes>
          <Route path="/pages/:factKey" element={<PageDetailView />} />
        </Routes>
      </MemoryRouter>
    )

    const rows = await screen.findAllByRole("row")
    // rows[0] is the header row (When/Author/Comment); data rows follow.
    expect(rows[1]).toHaveTextContent("second")
    expect(rows[1]).toHaveTextContent("Correction")
    expect(rows[2]).toHaveTextContent("first")
    expect(rows[2]).not.toHaveTextContent("Correction")
  })

  it("links back to the pages index", async () => {
    vi.spyOn(api, "fetchPage").mockResolvedValue({
      fact_key: "k",
      current: {
        revision_id: "r1",
        reference: { subject_document: { family: "Fam" }, selector: { type: "XPathSelector" }, reference_id: "id" },
        author: "a1",
        comment: "first",
        is_correction: false,
        created_at: "2026-01-01T00:00:00Z",
      },
      history: [],
    } as any)

    render(
      <MemoryRouter initialEntries={["/pages/k"]}>
        <Routes>
          <Route path="/pages/:factKey" element={<PageDetailView />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByRole("link", { name: /back to pages/i })).toHaveAttribute("href", "/")
  })
})
