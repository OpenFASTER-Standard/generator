import cytoscape from "cytoscape"
import { useEffect, useRef } from "react"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"

interface LineageGraphProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subject: string
  predicate: string
  sourceUri: string | null
}

export function LineageGraph({ open, onOpenChange, subject, predicate, sourceUri }: LineageGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open || !containerRef.current) return

    const cy = cytoscape({
      container: containerRef.current,
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

    return () => cy.destroy()
  }, [open, subject, predicate, sourceUri])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[480px]">
        <SheetHeader>
          <SheetTitle>Lineage</SheetTitle>
        </SheetHeader>
        <div ref={containerRef} data-testid="lineage-graph-container" className="h-96 w-full" />
      </SheetContent>
    </Sheet>
  )
}
