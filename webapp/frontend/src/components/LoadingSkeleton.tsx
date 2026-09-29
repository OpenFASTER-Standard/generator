import { Skeleton } from "@openfaster-standard/ui"

// A small shared loading placeholder -- replaces the bare "Loading..."
// text every view used to render individually. `rows` lets a view hint at
// its own real shape (a table-like view wants a few wider bars) without
// each view reinventing its own skeleton layout.
export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="flex flex-col gap-2">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  )
}
