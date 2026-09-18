import { useEffect, useMemo, useState } from "react"
import { apiGet } from "@/lib/api"
import { layoutTreemap } from "@/lib/treemap"
import type { TripleCategoryCount, TripleCountSummary, TriplePredicateCount } from "@/lib/api"

// Validated categorical palette slots 1-3 (blue/orange/aqua) -- the only
// three that clear this method's own all-pairs CVD/contrast checks
// together (see dataviz skill's palette.md); a treemap can put any two
// tiles side by side, so it's held to the stricter all-pairs bar, not
// the looser adjacent-only one bar/line charts use. A 4th category would
// need a 4th hue this validated set doesn't have room for -- which is
// exactly why "Run metadata" (a real but tiny slice) is folded into
// "Structural schema facts" server-side instead of getting its own.
const CATEGORY_COLOR: Record<TripleCategoryCount["key"], { light: string; dark: string }> = {
  documentation: { light: "#2a78d6", dark: "#3987e5" },
  structural: { light: "#eb6834", dark: "#d95926" },
  provenance: { light: "#1baf7a", dark: "#199e70" },
}

const CATEGORY_ORDER: TripleCategoryCount["key"][] = ["documentation", "structural", "provenance"]

// Relative luminance (sRGB) -- picks readable label ink for a label
// placed directly inside a colored fill, the one case where text is
// allowed to sit on top of a data color (see dataviz skill's own
// marks-and-anatomy.md).
function isDark(hex: string): boolean {
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
  return luminance < 0.55
}

function formatCount(count: number): string {
  return count.toLocaleString()
}

function formatPercent(count: number, total: number): string {
  return `${((count / total) * 100).toFixed(1)}%`
}

interface Tile {
  category: TripleCategoryCount
  predicate: TriplePredicateCount
  x: number
  y: number
  width: number
  height: number
}

const WIDTH = 900
const HEIGHT = 460
const CATEGORY_GAP = 3
const LEAF_GAP = 1

function buildTiles(summary: TripleCountSummary): Tile[] {
  const ordered = [...summary.categories].sort(
    (a, b) => CATEGORY_ORDER.indexOf(a.key) - CATEGORY_ORDER.indexOf(b.key),
  )
  const categoryRects = layoutTreemap(
    ordered.map((c) => ({ id: c.key, value: c.count })),
    { x: CATEGORY_GAP, y: CATEGORY_GAP, width: WIDTH - CATEGORY_GAP * 2, height: HEIGHT - CATEGORY_GAP * 2 },
  )

  const tiles: Tile[] = []
  for (const categoryRect of categoryRects) {
    const category = ordered.find((c) => c.key === categoryRect.id)!
    const inset = {
      x: categoryRect.x + CATEGORY_GAP,
      y: categoryRect.y + CATEGORY_GAP,
      width: Math.max(0, categoryRect.width - CATEGORY_GAP * 2),
      height: Math.max(0, categoryRect.height - CATEGORY_GAP * 2),
    }
    const leafRects = layoutTreemap(
      category.predicates.map((p) => ({ id: p.predicate, value: p.count })),
      inset,
    )
    for (const leafRect of leafRects) {
      const predicate = category.predicates.find((p) => p.predicate === leafRect.id)!
      tiles.push({
        category,
        predicate,
        x: leafRect.x + LEAF_GAP / 2,
        y: leafRect.y + LEAF_GAP / 2,
        width: Math.max(0, leafRect.width - LEAF_GAP),
        height: Math.max(0, leafRect.height - LEAF_GAP),
      })
    }
  }
  return tiles
}

export function TripleCountsView() {
  const [summary, setSummary] = useState<TripleCountSummary | undefined>(undefined)
  const [hovered, setHovered] = useState<Tile | null>(null)
  const [showTable, setShowTable] = useState(false)

  useEffect(() => {
    apiGet<TripleCountSummary>("/triple-counts").then(setSummary)
  }, [])

  const tiles = useMemo(() => (summary ? buildTiles(summary) : []), [summary])

  if (summary === undefined) {
    return <p className="text-sm text-muted-foreground">Loading triple counts…</p>
  }

  const orderedCategories = [...summary.categories].sort(
    (a, b) => CATEGORY_ORDER.indexOf(a.key) - CATEGORY_ORDER.indexOf(b.key),
  )

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">
            {formatCount(summary.total)} triples, by kind of thing
          </h3>
          <p className="text-xs text-muted-foreground">
            Every real predicate this store uses, sized by how many triples use it. Hover a tile for detail.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowTable((value) => !value)}
          className="rounded border px-2 py-1 text-xs"
        >
          {showTable ? "Show treemap" : "Show as table"}
        </button>
      </div>

      <div className="mb-3 flex flex-wrap gap-4">
        {orderedCategories.map((category) => (
          <div key={category.key} className="flex items-center gap-1.5 text-sm">
            <span
              className="inline-block size-3 rounded-sm"
              style={{ backgroundColor: CATEGORY_COLOR[category.key].light }}
            />
            <span>{category.label}</span>
            <span className="text-muted-foreground">
              ({formatCount(category.count)}, {formatPercent(category.count, summary.total)})
            </span>
          </div>
        ))}
      </div>

      {showTable ? (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground">
              <th className="py-1 pr-4 font-medium">Category</th>
              <th className="py-1 pr-4 font-medium">Predicate</th>
              <th className="py-1 pr-4 font-medium">Triples</th>
              <th className="py-1 font-medium">Share of total</th>
            </tr>
          </thead>
          <tbody>
            {orderedCategories.flatMap((category) =>
              category.predicates.map((predicate) => (
                <tr key={predicate.predicate} className="border-b last:border-0">
                  <td className="py-1 pr-4">{category.label}</td>
                  <td className="py-1 pr-4 font-mono text-xs">{predicate.label}</td>
                  <td className="py-1 pr-4">{formatCount(predicate.count)}</td>
                  <td className="py-1">{formatPercent(predicate.count, summary.total)}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      ) : (
        <div className="relative">
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full rounded border" role="img" aria-label="Treemap of triples by predicate">
            {tiles.map((tile) => {
              const fill = CATEGORY_COLOR[tile.category.key].light
              const labelFits = tile.width > 50 && tile.height > 24
              return (
                <g
                  key={tile.predicate.predicate}
                  onMouseEnter={() => setHovered(tile)}
                  onMouseMove={() => setHovered(tile)}
                  onMouseLeave={() => setHovered((current) => (current === tile ? null : current))}
                  className="cursor-default"
                >
                  <rect
                    x={tile.x}
                    y={tile.y}
                    width={tile.width}
                    height={tile.height}
                    fill={fill}
                    opacity={hovered === tile ? 1 : 0.85}
                  />
                  {labelFits && (
                    <text
                      x={tile.x + 4}
                      y={tile.y + 14}
                      fontSize={11}
                      fill={isDark(fill) ? "#ffffff" : "#0b0b0b"}
                      className="pointer-events-none select-none"
                    >
                      {tile.predicate.label}
                    </text>
                  )}
                </g>
              )
            })}
          </svg>
          {hovered && (
            <div
              className="pointer-events-none absolute rounded border bg-popover px-2 py-1 text-xs text-popover-foreground shadow-md"
              style={{
                left: `${((hovered.x + hovered.width / 2) / WIDTH) * 100}%`,
                top: `${(hovered.y / HEIGHT) * 100}%`,
                transform: "translate(-50%, -110%)",
              }}
            >
              <div className="font-semibold">{hovered.predicate.label}</div>
              <div>{hovered.category.label}</div>
              <div>
                {formatCount(hovered.predicate.count)} triples ({formatPercent(hovered.predicate.count, summary.total)})
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
