import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { AuditView } from "@/components/AuditView"
import type { AuditResponse } from "@/lib/api"

const audit: AuditResponse = {
  attachment: { attached: 294, ambiguous: 68, unmatched: 53 },
  coverage: { total: 380, attached: 294, ambiguous: 68, unmatched: 18 },
  issues: [
    { kind: "untranslated", subjectName: "Foo", detail: "identical text", subjectUri: "urn:foo" },
  ],
}

describe("AuditView", () => {
  it("renders both count blocks with their captions and the issue list", () => {
    render(<AuditView audit={audit} />)

    expect(screen.getByText(/attached=294, ambiguous=68, unmatched=53/)).toBeInTheDocument()
    expect(screen.getByText(/total=380/)).toBeInTheDocument()
    expect(screen.getByText(/every named construct in the schema/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Foo" })).toHaveAttribute("href", "#doc:urn:foo")
  })
})
