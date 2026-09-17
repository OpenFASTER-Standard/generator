import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { useFocus } from "@/lib/focus"

function Probe() {
  const focus = useFocus()
  return (
    <div>
      <span data-testid="mode">{focus.mode}</span>
      <span data-testid="subject">{focus.subject ?? "none"}</span>
      <button onClick={() => focus.setFocus({ mode: "living-text", subject: "urn:new" })}>
        go
      </button>
    </div>
  )
}

describe("useFocus", () => {
  it("reads mode and subject from the URL", () => {
    render(
      <MemoryRouter initialEntries={["/graph/urn:s"]}>
        <Routes>
          <Route path="/:mode/:subject?/:predicate?/:lang?" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId("mode").textContent).toBe("graph")
    expect(screen.getByTestId("subject").textContent).toBe("urn:s")
  })

  it("setFocus navigates to the new URL, updating what useFocus reads", async () => {
    render(
      <MemoryRouter initialEntries={["/graph/urn:s"]}>
        <Routes>
          <Route path="/:mode/:subject?/:predicate?/:lang?" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole("button", { name: "go" }))

    expect(screen.getByTestId("mode").textContent).toBe("living-text")
    expect(screen.getByTestId("subject").textContent).toBe("urn:new")
  })

  it("subject is null when the URL has no subject segment", () => {
    render(
      <MemoryRouter initialEntries={["/graph"]}>
        <Routes>
          <Route path="/:mode/:subject?/:predicate?/:lang?" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId("subject").textContent).toBe("none")
  })
})
