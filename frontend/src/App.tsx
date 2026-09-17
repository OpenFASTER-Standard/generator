import { useCallback, useEffect, useState } from "react"
import { HashRouter, Navigate, Route, Routes } from "react-router-dom"
import { GraphView } from "@/components/GraphView"
import { HoverFocusProvider } from "@/lib/hoverFocus"
import { LivingTextView } from "@/components/LivingTextView"
import type { PendingCorrection } from "@/components/InlineCorrection"
import { ModeSwitcher } from "@/components/ModeSwitcher"
import { RunsView } from "@/components/RunsView"
import { SyncedPanesView } from "@/components/SyncedPanesView"
import { apiGet } from "@/lib/api"
import { useReviewer } from "@/lib/reviewer"
import type {
  AuditResponse, DocumentationResponse, RunSummary, StructureResponse,
} from "@/lib/api"

export default function App() {
  const [search, setSearch] = useState("")
  const [reviewer, setReviewer] = useReviewer()

  const [structure, setStructure] = useState<StructureResponse | null>(null)
  const [documentation, setDocumentation] = useState<DocumentationResponse | null>(null)
  const [audit, setAudit] = useState<AuditResponse | null>(null)
  const [pending, setPending] = useState<PendingCorrection[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])

  const refreshPending = useCallback(() => {
    apiGet<PendingCorrection[]>("/corrections/pending").then(setPending)
  }, [])

  useEffect(() => {
    apiGet<StructureResponse>("/structure").then(setStructure)
    apiGet<DocumentationResponse>("/documentation").then(setDocumentation)
    apiGet<AuditResponse>("/audit").then(setAudit)
    apiGet<RunSummary[]>("/runs").then(setRuns)
    refreshPending()
  }, [refreshPending])

  const latestRun = runs[runs.length - 1]

  return (
    <HashRouter>
      <HoverFocusProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/graph" replace />} />
          <Route
            path="/:mode/*"
            element={
              <ModeSwitcher search={search} onSearchChange={setSearch} reviewer={reviewer} onReviewerChange={setReviewer}>
                <Routes>
                  <Route
                    path="graph/:subject?"
                    element={
                      structure && documentation && audit ? (
                        <GraphView structure={structure} documentation={documentation} audit={audit} pending={pending} search={search} />
                      ) : null
                    }
                  />
                  <Route
                    path="living-text/:subject?/:predicate?/:lang?"
                    element={
                      documentation ? (
                        <LivingTextView documentation={documentation} pending={pending} reviewer={reviewer} search={search} onDecided={refreshPending} />
                      ) : null
                    }
                  />
                  <Route
                    path="synced-panes"
                    element={
                      latestRun ? <SyncedPanesView pdfPath={latestRun.pdfPath} xsdPaths={[latestRun.xsdPath]} /> : null
                    }
                  />
                  <Route path="runs" element={<RunsView runs={runs} />} />
                </Routes>
              </ModeSwitcher>
            }
          />
        </Routes>
      </HoverFocusProvider>
    </HashRouter>
  )
}
