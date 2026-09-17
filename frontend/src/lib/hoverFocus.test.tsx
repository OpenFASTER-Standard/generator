import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { HoverFocusProvider, useHoverFocus } from "@/lib/hoverFocus"

function Probe() {
  const { hovered, setHovered } = useHoverFocus()
  return (
    <div>
      <span data-testid="hovered">{hovered ?? "none"}</span>
      <button onClick={() => setHovered("urn:x")}>hover</button>
      <button onClick={() => setHovered(null)}>unhover</button>
    </div>
  )
}

describe("useHoverFocus", () => {
  it("starts as null and updates without touching any router state", async () => {
    render(
      <HoverFocusProvider>
        <Probe />
      </HoverFocusProvider>,
    )

    expect(screen.getByTestId("hovered").textContent).toBe("none")
    await userEvent.click(screen.getByRole("button", { name: "hover" }))
    expect(screen.getByTestId("hovered").textContent).toBe("urn:x")
    await userEvent.click(screen.getByRole("button", { name: "unhover" }))
    expect(screen.getByTestId("hovered").textContent).toBe("none")
  })
})
