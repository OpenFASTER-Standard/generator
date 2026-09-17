import type { ReactNode } from "react"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useReviewer } from "@/lib/reviewer"

const TABS: { key: string; label: string }[] = [
  { key: "structure", label: "Structure" },
  { key: "documentation", label: "Documentation" },
  { key: "audit", label: "Audit" },
  { key: "corrections", label: "Corrections" },
  { key: "runs", label: "Runs" },
]

// A small, fixed reviewer list -- appropriate for this project's real
// scale (an internal review team, not public signup). Add a name here
// when a new reviewer joins.
const REVIEWERS = ["julian", "someone-else"]

interface PageShellProps {
  activeTab: string
  onTabChange: (tab: string) => void
  search: string
  onSearchChange: (value: string) => void
  children: ReactNode
}

export function PageShell({ activeTab, onTabChange, search, onSearchChange, children }: PageShellProps) {
  const [reviewer, setReviewer] = useReviewer()

  return (
    <TooltipProvider>
      <div className="flex flex-col min-h-screen">
        <nav className="sticky top-0 z-10 flex items-center gap-4 border-b bg-background px-4 py-3">
          <Tabs value={activeTab} onValueChange={(value) => onTabChange(value)}>
            <TabsList>
              {TABS.map((tab) => (
                <TabsTrigger key={tab.key} value={tab.key}>
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <Input
            placeholder="Filter by name..."
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            className="ml-auto max-w-64"
          />
          <Select value={reviewer} onValueChange={(value) => value && setReviewer(value)}>
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
