import type { ReactNode } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useFocus } from "@/lib/focus"

const MODES: { key: string; label: string }[] = [
  { key: "graph", label: "Graph" },
  { key: "living-text", label: "Living Text" },
  { key: "synced-panes", label: "Synced Panes" },
  { key: "runs", label: "Runs" },
]

interface ModeSwitcherProps {
  search: string
  onSearchChange: (value: string) => void
  reviewer: string
  onReviewerChange: (name: string) => void
  pendingCount: number
  children: ReactNode
}

export function ModeSwitcher({ search, onSearchChange, reviewer, onReviewerChange, pendingCount, children }: ModeSwitcherProps) {
  const { mode, subject, setFocus } = useFocus()

  return (
    <TooltipProvider>
      <div className="flex flex-col min-h-screen">
        <nav className="sticky top-0 z-10 flex items-center gap-4 border-b bg-background px-4 py-3">
          {/* Switching modes must keep the same focused subject -- this is
              the DoD's own "mode-switch-preserves-focus" requirement (Task
              6's shared focus model). Passing only `{ mode: value }` here
              dropped `subject` entirely on every tab click, silently
              resetting focus back to "nothing selected" no matter what was
              focused before -- confirmed live via this plan's own E2E
              suite (clicking "Graph" after focusing a Living Text entry
              landed on bare "/graph", not "/graph/<subject>"). Predicate/
              lang are deliberately NOT carried over: they're a Living-Text-
              specific (field, language) pair with no meaning in Graph/
              Synced-Panes/Runs, so dropping them when leaving living-text
              avoids stale, meaningless segments in those modes' URLs. */}
          <Tabs value={mode} onValueChange={(value) => setFocus({ mode: value, subject: subject ?? undefined })}>
            <TabsList>
              {MODES.map((modeOption) => (
                <TabsTrigger key={modeOption.key} value={modeOption.key}>
                  {modeOption.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          {pendingCount > 0 && (
            <button onClick={() => setFocus({ mode: "graph" })} className="flex items-center gap-1 text-xs">
              <Badge variant="destructive">{pendingCount}</Badge> pending
            </button>
          )}
          <Input
            placeholder="Filter by name..."
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            className="ml-auto max-w-64"
          />
          <Input
            placeholder="Reviewing as..."
            value={reviewer}
            onChange={(event) => onReviewerChange(event.target.value)}
            aria-label="Reviewing as"
            className="w-40"
          />
        </nav>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </TooltipProvider>
  )
}
