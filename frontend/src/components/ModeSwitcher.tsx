import { useEffect, useState } from "react"
import type { ReactNode } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { apiGet } from "@/lib/api"
import { useFocus } from "@/lib/focus"

const MODES: { key: string; label: string }[] = [
  { key: "graph", label: "Graph" },
  { key: "living-text", label: "Living Text" },
  { key: "synced-panes", label: "Synced Panes" },
  { key: "runs", label: "Runs" },
]

const REVIEWERS = ["julian", "someone-else"]

interface ModeSwitcherProps {
  search: string
  onSearchChange: (value: string) => void
  reviewer: string
  onReviewerChange: (name: string) => void
  children: ReactNode
}

export function ModeSwitcher({ search, onSearchChange, reviewer, onReviewerChange, children }: ModeSwitcherProps) {
  const { mode, setFocus } = useFocus()
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    apiGet<unknown[]>("/corrections/pending").then((rows) => setPendingCount(rows.length))
  }, [])

  return (
    <TooltipProvider>
      <div className="flex flex-col min-h-screen">
        <nav className="sticky top-0 z-10 flex items-center gap-4 border-b bg-background px-4 py-3">
          <Tabs value={mode} onValueChange={(value) => setFocus({ mode: value })}>
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
          <Select value={reviewer} onValueChange={(value) => value && onReviewerChange(value)}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Reviewing as..." />
            </SelectTrigger>
            <SelectContent>
              {REVIEWERS.map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </nav>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </TooltipProvider>
  )
}
