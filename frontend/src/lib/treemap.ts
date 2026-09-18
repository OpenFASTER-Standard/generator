// A "binary treemap" layout: recursively split the (already
// value-sorted) item list at whichever point balances the two halves'
// sums most evenly, alternating a vertical/horizontal cut with the
// rect's own longer side each time. Simpler than the classic
// "squarified" algorithm (which optimizes each row's aspect ratio) but
// exactly area-conserving by construction and easy to verify correct --
// a real property this module's own tests check directly, not just eyeballed.
export interface TreemapItem {
  id: string
  value: number
}

export interface TreemapRect extends TreemapItem {
  x: number
  y: number
  width: number
  height: number
}

interface Rect {
  x: number
  y: number
  width: number
  height: number
}

function bestSplitIndex(items: TreemapItem[]): number {
  const total = items.reduce((sum, item) => sum + item.value, 0)
  let cumulative = 0
  let splitIndex = 1
  let bestDiff = Infinity
  for (let i = 1; i < items.length; i++) {
    cumulative += items[i - 1].value
    const diff = Math.abs(cumulative - (total - cumulative))
    if (diff < bestDiff) {
      bestDiff = diff
      splitIndex = i
    }
  }
  return splitIndex
}

export function layoutTreemap(items: TreemapItem[], rect: Rect): TreemapRect[] {
  const real = items.filter((item) => item.value > 0)
  if (real.length === 0) return []
  if (real.length === 1) return [{ ...real[0], ...rect }]

  const splitIndex = bestSplitIndex(real)
  const left = real.slice(0, splitIndex)
  const right = real.slice(splitIndex)
  const leftSum = left.reduce((sum, item) => sum + item.value, 0)
  const total = real.reduce((sum, item) => sum + item.value, 0)
  const fraction = leftSum / total

  if (rect.width >= rect.height) {
    const leftWidth = rect.width * fraction
    return [
      ...layoutTreemap(left, { x: rect.x, y: rect.y, width: leftWidth, height: rect.height }),
      ...layoutTreemap(right, { x: rect.x + leftWidth, y: rect.y, width: rect.width - leftWidth, height: rect.height }),
    ]
  }

  const topHeight = rect.height * fraction
  return [
    ...layoutTreemap(left, { x: rect.x, y: rect.y, width: rect.width, height: topHeight }),
    ...layoutTreemap(right, { x: rect.x, y: rect.y + topHeight, width: rect.width, height: rect.height - topHeight }),
  ]
}
