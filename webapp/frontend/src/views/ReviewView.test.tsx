import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { ReviewView } from "./ReviewView"
import * as api from "../api"

const reviewData = {
  flagged: {
    "key-a": [{ leaf: { reference_id: "ref1", subject_document: { family: "Fam" } }, drift_kind: "CONTENT", fingerprint: "fp1" }],
  },
  unresolved_families: [],
  excluded_keys: [],
  deserialization_failures: ["corrupt-key"],
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe("ReviewView", () => {
  it("shows a distinct alert for deserialization failures vs unresolved families", async () => {
    vi.spyOn(api, "fetchReview").mockResolvedValue(reviewData as any)
    render(
      <MemoryRouter>
        <ReviewView />
      </MemoryRouter>
    )
    expect(await screen.findByText(/corrupt-key/)).toBeInTheDocument()
    expect(screen.getByText(/corrupt-key/).closest("[role='alert']")).toHaveTextContent(/corrupted|cannot be checked/i)
  })

  it("submits an approve verdict and removes the item from view", async () => {
    vi.spyOn(api, "fetchReview").mockResolvedValue(reviewData as any)
    vi.spyOn(api, "submitReview").mockResolvedValue({ fact_key: "key-a", revision: {} } as any)
    render(
      <MemoryRouter>
        <ReviewView />
      </MemoryRouter>
    )

    fireEvent.click(await screen.findByText(/key-a/))
    fireEvent.click(screen.getByText("Review"))
    fireEvent.change(screen.getByLabelText(/Reviewer/i), { target: { value: "r1" } })
    fireEvent.change(screen.getByLabelText(/Reasoning/i), { target: { value: "fine" } })
    fireEvent.click(screen.getByText("Approve"))

    await waitFor(() =>
      expect(api.submitReview).toHaveBeenCalledWith(
        expect.objectContaining({ fact_key: "key-a", leaf_reference_id: "ref1", verdict: "approved", reviewer: "r1", reasoning: "fine" })
      )
    )
  })
})
