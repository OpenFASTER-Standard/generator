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
  check_failures: [],
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

  it("shows a 4th, distinct alert for pages that failed to check due to an unexpected error", async () => {
    vi.spyOn(api, "fetchReview").mockResolvedValue({
      ...reviewData,
      check_failures: [{ key: "exploding-key", error: "boom" }],
    } as any)
    render(
      <MemoryRouter>
        <ReviewView />
      </MemoryRouter>
    )

    const checkFailureAlert = (await screen.findByText(/exploding-key/)).closest("[role='alert']")
    expect(checkFailureAlert).toHaveTextContent(/unexpected error/i)
  })

  it("submits an approve verdict and removes the item -- and its whole fact_key group, since it was the only leaf -- from view", async () => {
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
    // The actual point of the optimistic-removal logic: the leaf (and,
    // since it was the only one under "key-a", the whole group) is gone
    // from the rendered accordion, not just "the API was called".
    await waitFor(() => expect(screen.queryByText(/key-a/)).not.toBeInTheDocument())
    expect(screen.getByText(/nothing flagged for review/i)).toBeInTheDocument()
  })

  it("removes only the reviewed leaf, keeping its fact_key group, when a second leaf is still pending", async () => {
    const twoLeafData = {
      ...reviewData,
      flagged: {
        "key-a": [
          { leaf: { reference_id: "ref1", subject_document: { family: "Fam" } }, drift_kind: "CONTENT", fingerprint: "fp1" },
          { leaf: { reference_id: "ref2", subject_document: { family: "Fam" } }, drift_kind: "CONTENT", fingerprint: "fp2" },
        ],
      },
    }
    vi.spyOn(api, "fetchReview").mockResolvedValue(twoLeafData as any)
    vi.spyOn(api, "submitReview").mockResolvedValue({ fact_key: "key-a", revision: {} } as any)
    render(
      <MemoryRouter>
        <ReviewView />
      </MemoryRouter>
    )

    fireEvent.click(await screen.findByText(/key-a/))
    const rowsBefore = await screen.findAllByText("Review")
    expect(rowsBefore).toHaveLength(2)

    fireEvent.click(rowsBefore[0])
    fireEvent.change(screen.getByLabelText(/Reviewer/i), { target: { value: "r1" } })
    fireEvent.change(screen.getByLabelText(/Reasoning/i), { target: { value: "fine" } })
    fireEvent.click(screen.getByText("Approve"))

    await waitFor(() =>
      expect(api.submitReview).toHaveBeenCalledWith(expect.objectContaining({ leaf_reference_id: "ref1" }))
    )
    // key-a's group itself is still there (one leaf remains) -- only the
    // reviewed row disappeared.
    expect(screen.getByText(/key-a/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByText("Review")).toHaveLength(1))
  })

  it("a Reject verdict does NOT remove the item -- the server keeps a rejected leaf flagged, since the drift is real and stays open", async () => {
    // Real bug found in a whole-branch review: apply_reviews() (the real
    // server-side filter) deliberately keeps a REJECTED leaf flagged --
    // "this drift is real, it stays open" -- but the UI removed it from
    // local state on ANY successful submit regardless of verdict, so a
    // rejected item vanished as if handled and silently reappeared on the
    // next load. Per this project's own standing rule that every state
    // must have a visible way forward, an item vanishing with no trace is
    // exactly a state with no visible way forward.
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
    fireEvent.change(screen.getByLabelText(/Reasoning/i), { target: { value: "still drifted" } })
    fireEvent.click(screen.getByText("Reject"))

    await waitFor(() =>
      expect(api.submitReview).toHaveBeenCalledWith(expect.objectContaining({ verdict: "rejected" }))
    )
    // Still there -- rejecting keeps the finding open, it doesn't resolve it.
    expect(screen.getByText(/key-a/)).toBeInTheDocument()
    expect(screen.getAllByText("Review")).toHaveLength(1)
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

  it("shows an error alert when fetching the review summary fails", async () => {
    vi.spyOn(api, "fetchReview").mockRejectedValue(new Error("boom"))

    render(
      <MemoryRouter>
        <ReviewView />
      </MemoryRouter>
    )

    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load review data.*boom/i)
  })
})
