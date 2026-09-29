import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, within, fireEvent, waitFor } from "@testing-library/react"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { AddCitationView } from "./AddCitationView"
import * as api from "../api"

const candidates = {
  "Family-A": {
    candidates: [
      { tag: "xs:element", name: "Foo", xpath: "//Foo" },
      { tag: "xs:element", name: "Bar", xpath: "//Bar" },
    ],
    excluded: [],
  },
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe("AddCitationView", () => {
  it("filters a family's candidates by the filter input", async () => {
    vi.spyOn(api, "fetchCandidates").mockResolvedValue(candidates as any)
    render(
      <MemoryRouter>
        <AddCitationView />
      </MemoryRouter>
    )

    fireEvent.click(await screen.findByText(/Family-A/))
    expect(await screen.findByText("Foo")).toBeInTheDocument()
    expect(screen.getByText("Bar")).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText(/filter/i), { target: { value: "foo" } })
    expect(screen.getByText("Foo")).toBeInTheDocument()
    expect(screen.queryByText("Bar")).not.toBeInTheDocument()
  })

  it("submits a citation and navigates to the resulting page", async () => {
    vi.spyOn(api, "fetchCandidates").mockResolvedValue(candidates as any)
    vi.spyOn(api, "submitCitation").mockResolvedValue({ fact_key: "new-key", revision: {} as any })
    render(
      <MemoryRouter initialEntries={["/add"]}>
        <Routes>
          <Route path="/add" element={<AddCitationView />} />
          <Route path="/pages/:factKey" element={<div>landed on page detail</div>} />
        </Routes>
      </MemoryRouter>
    )

    fireEvent.click(await screen.findByText(/Family-A/))
    const fooRow = (await screen.findByText("Foo")).closest("tr")!
    fireEvent.click(within(fooRow).getByText("Cite this"))
    fireEvent.change(screen.getByLabelText(/Fact key/i), { target: { value: "new-key" } })
    fireEvent.change(screen.getByLabelText(/Author/i), { target: { value: "me" } })
    fireEvent.click(screen.getByText("Submit citation"))

    await waitFor(() =>
      expect(api.submitCitation).toHaveBeenCalledWith(
        expect.objectContaining({ family: "Family-A", xpath: "//Foo", fact_key: "new-key", author: "me" })
      )
    )
    expect(await screen.findByText("landed on page detail")).toBeInTheDocument()
  })

  it("submits exactly once even if the submit button is clicked twice rapidly", async () => {
    vi.spyOn(api, "fetchCandidates").mockResolvedValue(candidates as any)
    let resolveSubmit: (v: { fact_key: string; revision: any }) => void
    vi.spyOn(api, "submitCitation").mockReturnValue(
      new Promise((resolve) => {
        resolveSubmit = resolve
      })
    )
    render(
      <MemoryRouter>
        <AddCitationView />
      </MemoryRouter>
    )

    fireEvent.click(await screen.findByText(/Family-A/))
    const fooRow = (await screen.findByText("Foo")).closest("tr")!
    fireEvent.click(within(fooRow).getByText("Cite this"))
    fireEvent.change(screen.getByLabelText(/Fact key/i), { target: { value: "new-key" } })
    fireEvent.change(screen.getByLabelText(/Author/i), { target: { value: "me" } })

    fireEvent.click(screen.getByText("Submit citation"))
    fireEvent.click(screen.getByText("Submit citation"))

    resolveSubmit!({ fact_key: "new-key", revision: {} as any })
    await waitFor(() => expect(api.submitCitation).toHaveBeenCalledTimes(1))
  })

  it("surfaces excluded (ambiguous) candidates instead of silently dropping them", async () => {
    vi.spyOn(api, "fetchCandidates").mockResolvedValue({
      "Family-A": {
        candidates: [{ tag: "xs:element", name: "Foo", xpath: "//Foo" }],
        excluded: [{ tag: "xs:element", name: "Decoy", xpath: "//Decoy", match_count: 2 }],
      },
    } as any)
    render(
      <MemoryRouter>
        <AddCitationView />
      </MemoryRouter>
    )

    fireEvent.click(await screen.findByText(/Family-A/))
    expect(await screen.findByText(/1 construct could not be given an unambiguous path/i)).toBeInTheDocument()
  })
})
