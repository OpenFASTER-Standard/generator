import { useCallback, useEffect, useState } from "react"
import { AuditView } from "@/components/AuditView"
import { CorrectionsView } from "@/components/CorrectionsView"
import { DocumentationView } from "@/components/DocumentationView"
import { PageShell } from "@/components/PageShell"
import { StructureView } from "@/components/StructureView"
import { apiGet } from "@/lib/api"
import { useReviewer } from "@/lib/reviewer"
import type { AuditResponse, DeclarationsResponse, DocumentationResponse, StructureResponse } from "@/lib/api"

interface PendingCorrection {
  correctionUri: string
  targetSubject: string
  proposedValue: string
  proposer: string
}

export default function App() {
  const [activeTab, setActiveTab] = useState("structure")
  const [search, setSearch] = useState("")
  const [reviewer] = useReviewer()

  const [structure, setStructure] = useState<StructureResponse | null>(null)
  const [declarations, setDeclarations] = useState<DeclarationsResponse | null>(null)
  const [documentation, setDocumentation] = useState<DocumentationResponse | null>(null)
  const [audit, setAudit] = useState<AuditResponse | null>(null)
  const [pending, setPending] = useState<PendingCorrection[]>([])

  const refreshPending = useCallback(() => {
    apiGet<PendingCorrection[]>("/corrections/pending").then(setPending)
  }, [])

  useEffect(() => {
    apiGet<StructureResponse>("/structure").then(setStructure)
    apiGet<DeclarationsResponse>("/declarations").then(setDeclarations)
    apiGet<DocumentationResponse>("/documentation").then(setDocumentation)
    apiGet<AuditResponse>("/audit").then(setAudit)
    refreshPending()
  }, [refreshPending])

  return (
    <PageShell activeTab={activeTab} onTabChange={setActiveTab} search={search} onSearchChange={setSearch}>
      {activeTab === "structure" && structure && declarations && (
        <StructureView structure={structure} declarations={declarations} search={search} />
      )}
      {activeTab === "documentation" && documentation && (
        <DocumentationView documentation={documentation} search={search} />
      )}
      {activeTab === "audit" && audit && <AuditView audit={audit} />}
      {activeTab === "corrections" && (
        <CorrectionsView pending={pending} reviewer={reviewer} onDecided={refreshPending} />
      )}
      {activeTab !== "structure" && activeTab !== "documentation" && activeTab !== "audit" && activeTab !== "corrections" && (
        <p className="text-muted-foreground">{activeTab} page -- wired up in later tasks.</p>
      )}
    </PageShell>
  )
}
