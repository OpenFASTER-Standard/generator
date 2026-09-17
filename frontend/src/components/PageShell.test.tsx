import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { PageShell } from "@/components/PageShell"

describe("PageShell", () => {
  it("renders all 5 nav tabs and calls onTabChange when one is clicked", async () => {
    const onTabChange = vi.fn()
    render(
      <PageShell activeTab="structure" onTabChange={onTabChange} search="" onSearchChange={() => {}}>
        <div>content</div>
      </PageShell>,
    )

    for (const label of ["Structure", "Documentation", "Audit", "Corrections", "Runs"]) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument()
    }

    await userEvent.click(screen.getByRole("tab", { name: "Documentation" }))
    expect(onTabChange).toHaveBeenCalledWith("documentation")
  })

  it("renders its children", () => {
    render(
      <PageShell activeTab="structure" onTabChange={() => {}} search="" onSearchChange={() => {}}>
        <div>real content</div>
      </PageShell>,
    )
    expect(screen.getByText("real content")).toBeInTheDocument()
  })
})
