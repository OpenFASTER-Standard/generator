import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { LoadingSkeleton } from "./LoadingSkeleton"

describe("LoadingSkeleton", () => {
  it("renders a real accessible loading status", () => {
    render(<LoadingSkeleton />)
    expect(screen.getByRole("status", { name: /loading/i })).toBeInTheDocument()
  })

  it("renders the requested number of placeholder rows", () => {
    const { container } = render(<LoadingSkeleton rows={5} />)
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(5)
  })
})
