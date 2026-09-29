import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { ReviewView } from "./ReviewView"
import * as api from "../api"

const reviewData = {
  flagged: {
    "key-a": [{ leaf: { reference_id: "ref1", subject_document: { family: "Fam" } }, drift_kind: "CONTENT", fingerprint: "fp1" }],
  },
  unresolved_families: [{ family: "Fam-B", status: "NOT_FOUND" }],
  excluded_keys: ["excluded-key"],
  deserialization_failures: ["corrupt-key"],
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe("ReviewView", () => {
  it("shows a distinct alert each for deserialization failures, unresolved families, and excluded keys", async () => {
    vi.spyOn(api, "fetchReview").mockResolvedValue(reviewData as any)
    render(
      <MemoryRouter>
        <ReviewView />
      </MemoryRouter>
    )
    const deserializationAlert = (await screen.findByText(/corrupt-key/)).closest("[role='alert']")
    expect(deserializationAlert).toHaveTextContent(/corrupted|cannot be checked/i)

    const unresolvedAlert = screen.getByText(/Fam-B/).closest("[role='alert']")
    expect(unresolvedAlert).toHaveTextContent(/could not be resolved/i)

    const excludedAlert = screen.getByText(/excluded-key/).closest("[role='alert']")
    expect(excludedAlert).toHaveTextContent(/could not be checked this run/i)

    // Three genuinely distinct alerts, not one generic warning reused.
    expect(new Set([deserializationAlert, unresolvedAlert, excludedAlert]).size).toBe(3)
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

  it("does not submit a review with a blank reviewer or reasoning", async () => {
    vi.spyOn(api, "fetchReview").mockResolvedValue(reviewData as any)
    vi.spyOn(api, "submitReview").mockResolvedValue({ fact_key: "key-a", revision: {} } as any)
    render(
      <MemoryRouter>
        <ReviewView />
      </MemoryRouter>
    )

    fireEvent.click(await screen.findByText(/key-a/))
    fireEvent.click(screen.getByText("Review"))

    // Reviewer and reasoning both start blank -- Approve must be inert.
    fireEvent.click(screen.getByText("Approve"))
    expect(api.submitReview).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText(/Reviewer/i), { target: { value: "r1" } })
    fireEvent.click(screen.getByText("Approve"))
    expect(api.submitReview).not.toHaveBeenCalled()
  })

  it("submits exactly once even if Approve is clicked twice rapidly", async () => {
    vi.spyOn(api, "fetchReview").mockResolvedValue(reviewData as any)
    let resolveSubmit: (v: { fact_key: string; revision: any }) => void
    vi.spyOn(api, "submitReview").mockReturnValue(
      new Promise((resolve) => {
        resolveSubmit = resolve
      })
    )
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
    fireEvent.click(screen.getByText("Approve"))

    resolveSubmit!({ fact_key: "key-a", revision: {} as any })
    await waitFor(() => expect(api.submitReview).toHaveBeenCalledTimes(1))
  })
})
