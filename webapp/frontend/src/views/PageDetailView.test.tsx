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
        kind: "citation",
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
        kind: "citation",
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

  it("badges a review-kind revision distinctly from a citation revision", async () => {
    vi.spyOn(api, "fetchPage").mockResolvedValue({
      fact_key: "k",
      current: {
        revision_id: "r1",
        reference: { subject_document: { family: "Fam" }, selector: { type: "XPathSelector" }, reference_id: "id" },
        author: "a1",
        comment: "first",
        is_correction: false,
        created_at: "2026-01-01T00:00:00Z",
        kind: "citation",
      },
      history: [
        {
          revision_id: "r1",
          reference: {},
          author: "a1",
          comment: "first",
          is_correction: false,
          created_at: "2026-01-01T00:00:00Z",
          kind: "citation",
        },
        {
          revision_id: "r2",
          reference: {},
          author: "reviewer",
          comment: "Review (approved): fine",
          is_correction: false,
          created_at: "2026-01-02T00:00:00Z",
          kind: "review",
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
    expect(rows[1]).toHaveTextContent("Review")
    expect(rows[2]).not.toHaveTextContent("Review")
  })

  it("does not crash when a page has no citation revision (current is null)", async () => {
    vi.spyOn(api, "fetchPage").mockResolvedValue({
      fact_key: "k",
      current: null,
      history: [
        {
          revision_id: "r1",
          reference: {},
          author: "reviewer",
          comment: "Review (approved): fine",
          is_correction: false,
          created_at: "2026-01-01T00:00:00Z",
          kind: "review",
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

    expect(await screen.findByText("k")).toBeInTheDocument()
  })

  it("shows an error alert when fetching the page fails", async () => {
    vi.spyOn(api, "fetchPage").mockRejectedValue(new Error("boom"))

    render(
      <MemoryRouter initialEntries={["/pages/k"]}>
        <Routes>
          <Route path="/pages/:factKey" element={<PageDetailView />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load this page.*boom/i)
  })
})
