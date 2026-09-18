import { describe, expect, it } from "vitest"
import { layoutTreemap } from "@/lib/treemap"

describe("layoutTreemap", () => {
  it("conserves total area exactly, for a real skewed distribution", () => {
    const items = [
      { id: "a", value: 2656 },
      { id: "b", value: 2902 },
      { id: "c", value: 671 },
    ]
    const rect = { x: 0, y: 0, width: 800, height: 400 }

    const rects = layoutTreemap(items, rect)

    const totalArea = rects.reduce((sum, r) => sum + r.width * r.height, 0)
    expect(totalArea).toBeCloseTo(rect.width * rect.height, 5)
  })

  it("gives every rect a positive width and height", () => {
    const items = Array.from({ length: 20 }, (_, i) => ({ id: `p${i}`, value: 40 - i }))
    const rects = layoutTreemap(items, { x: 0, y: 0, width: 500, height: 300 })

    expect(rects).toHaveLength(20)
    for (const r of rects) {
      expect(r.width).toBeGreaterThan(0)
      expect(r.height).toBeGreaterThan(0)
    }
  })

  it("filters out zero-value items instead of producing a zero-area rect", () => {
    const items = [
      { id: "a", value: 10 },
      { id: "b", value: 0 },
    ]
    const rects = layoutTreemap(items, { x: 0, y: 0, width: 100, height: 100 })

    expect(rects.map((r) => r.id)).toEqual(["a"])
  })

  it("gives a single item the entire rect", () => {
    const rects = layoutTreemap([{ id: "only", value: 5 }], { x: 10, y: 20, width: 100, height: 50 })

    expect(rects).toEqual([{ id: "only", value: 5, x: 10, y: 20, width: 100, height: 50 }])
  })

  it("returns an empty layout for an empty or all-zero input", () => {
    expect(layoutTreemap([], { x: 0, y: 0, width: 100, height: 100 })).toEqual([])
    expect(layoutTreemap([{ id: "a", value: 0 }], { x: 0, y: 0, width: 100, height: 100 })).toEqual([])
  })

  it("splits proportionally to value for a simple two-item case", () => {
    const rects = layoutTreemap(
      [
        { id: "big", value: 75 },
        { id: "small", value: 25 },
      ],
      { x: 0, y: 0, width: 100, height: 100 },
    )

    const big = rects.find((r) => r.id === "big")!
    const small = rects.find((r) => r.id === "small")!
    expect(big.width * big.height).toBeCloseTo(7500, 5)
    expect(small.width * small.height).toBeCloseTo(2500, 5)
  })
})
