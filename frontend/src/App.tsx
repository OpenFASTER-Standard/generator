import { useCallback, useEffect, useState } from "react"
import { HashRouter, Navigate, Route, Routes } from "react-router-dom"
import { GraphView } from "@/components/GraphView"
import { HoverFocusProvider } from "@/lib/hoverFocus"
import { LivingTextView } from "@/components/LivingTextView"
import type { PendingCorrection } from "@/components/InlineCorrection"
import { useFocus } from "@/lib/focus"
import { ModeSwitcher } from "@/components/ModeSwitcher"
import { RunsView } from "@/components/RunsView"
import { SourcesView } from "@/components/SourcesView"
import { SyncedPanesView } from "@/components/SyncedPanesView"
import { apiGet } from "@/lib/api"
import { useReviewer } from "@/lib/reviewer"
import type {
  AuditResponse, DocumentationResponse, RunSummary, StructureResponse,
} from "@/lib/api"

interface ModeContentProps {
  structure: StructureResponse | null
  documentation: DocumentationResponse | null
  audit: AuditResponse | null
  pending: PendingCorrection[]
  search: string
  reviewer: string
  onDecided: () => void
  runs: RunSummary[]
}

// Selects which view to render for the current mode with a plain switch on
// the `mode` param, not a second, nested <Routes> keyed by mode-prefixed
// paths -- see this file's own git history for why: the outer route below
// already consumes the mode segment into `:mode` and captures every
// remaining segment via `:subject?/:predicate?/:lang?`, so a nested Routes
// matching against that same remainder would need each mode's own name
// repeated a second time in the URL (e.g. "/living-text/living-text/<uri>")
// to ever match -- which no real caller (setFocus, this app's own links, or
// this plan's own E2E suite) ever produces, so nothing behind ModeSwitcher
// rendered for any bare "/graph", "/living-text", etc. URL. Confirmed live
// against the real running app: <main> stayed completely empty at those
// URLs no matter how long the page's own data fetches were given to
// resolve, and only "/living-text/living-text" (the doubled, unintended
// shape) actually rendered LivingTextView.
function ModeContent({
  structure, documentation, audit, pending, search, reviewer, onDecided, runs,
}: ModeContentProps) {
  const { mode } = useFocus()
  switch (mode) {
    case "graph":
      return structure && documentation && audit ? (
        <GraphView structure={structure} documentation={documentation} audit={audit} pending={pending} search={search} />
      ) : null
    case "living-text":
      return documentation ? (
        <LivingTextView documentation={documentation} pending={pending} reviewer={reviewer} search={search} onDecided={onDecided} />
      ) : null
    case "synced-panes":
      return <SyncedPanesView />
    case "sources":
      return <SourcesView />
    case "runs":
      return <RunsView runs={runs} />
    default:
      return null
  }
}

export default function App() {
  const [search, setSearch] = useState("")
  const [reviewer, setReviewer] = useReviewer()

  const [structure, setStructure] = useState<StructureResponse | null>(null)
  const [documentation, setDocumentation] = useState<DocumentationResponse | null>(null)
  const [audit, setAudit] = useState<AuditResponse | null>(null)
  const [pending, setPending] = useState<PendingCorrection[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])

  // Approving/rejecting a correction changes not just the pending queue but
  // also the corrected text itself: /documentation reflects approved
  // corrections, and /audit's issue list can shift too (e.g. an
  // ambiguous/unmatched entry resolving). Refetch all three together so the
  // displayed text/audit state doesn't go stale the moment the pending
  // badge disappears -- previously this only refetched /corrections/pending,
  // leaving on-screen text pinned to whatever it was at initial load until a
  // full page reload.
  const refreshPending = useCallback(() => {
    apiGet<PendingCorrection[]>("/corrections/pending").then(setPending)
    apiGet<DocumentationResponse>("/documentation").then(setDocumentation)
    apiGet<AuditResponse>("/audit").then(setAudit)
  }, [])

  useEffect(() => {
    apiGet<StructureResponse>("/structure").then(setStructure)
    apiGet<RunSummary[]>("/runs").then(setRuns)
    refreshPending()
  }, [refreshPending])

  return (
    <HashRouter>
      <HoverFocusProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/graph" replace />} />
          <Route
            path="/:mode/:subject?/:predicate?/:lang?"
            element={
              <ModeSwitcher
                search={search}
                onSearchChange={setSearch}
                reviewer={reviewer}
                onReviewerChange={setReviewer}
                pendingCount={pending.length}
              >
                <ModeContent
                  structure={structure}
                  documentation={documentation}
                  audit={audit}
                  pending={pending}
                  search={search}
                  reviewer={reviewer}
                  onDecided={refreshPending}
                  runs={runs}
                />
              </ModeSwitcher>
            }
          />
        </Routes>
      </HoverFocusProvider>
    </HashRouter>
  )
}
