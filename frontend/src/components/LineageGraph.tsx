import cytoscape from "cytoscape"
import { useCallback, useRef } from "react"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"

interface LineageGraphProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subject: string
  predicate: string
  sourceUri: string | null
}

export function LineageGraph({ open, onOpenChange, subject, predicate, sourceUri }: LineageGraphProps) {
  const cyRef = useRef<cytoscape.Core | null>(null)

  // A ref callback, not a useEffect keyed on `open`: Base UI's Sheet does
  // not keep its content mounted while closed, so the container <div>
  // does not exist in the DOM at all until Base UI itself mounts it --
  // confirmed live in a real browser, a useEffect guarded on
  // `containerRef.current` silently no-op'd every time (no error, no
  // canvas, nothing) because the ref was still null at the moment the
  // effect ran. A ref callback instead fires exactly when React actually
  // attaches (or detaches) the node, regardless of Base UI's own
  // mount/animation timing, and React re-invokes it (detach then
  // reattach) whenever its identity changes -- which the dependency
  // array below causes on any real subject/predicate/sourceUri change.
  const setContainer = useCallback(
    (node: HTMLDivElement | null) => {
      cyRef.current?.destroy()
      cyRef.current = null
      if (!node) return
      cyRef.current = cytoscape({
        container: node,
        elements: [
          { data: { id: "source", label: sourceUri ?? "unknown source" } },
          { data: { id: "current", label: `${subject} / ${predicate}` } },
          { data: { id: "edge", source: "source", target: "current", label: "wasDerivedFrom" } },
        ],
        style: [
          { selector: "node", style: { label: "data(label)", "font-size": 10, "background-color": "#0b5fff" } },
          { selector: "edge", style: { label: "data(label)", "font-size": 8, "curve-style": "bezier", "target-arrow-shape": "triangle" } },
        ],
        layout: { name: "breadthfirst", directed: true },
      })
    },
    [subject, predicate, sourceUri],
  )

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[480px]">
        <SheetHeader>
          <SheetTitle>Lineage</SheetTitle>
        </SheetHeader>
        <div ref={setContainer} data-testid="lineage-graph-container" className="h-96 w-full" />
      </SheetContent>
    </Sheet>
  )
}
