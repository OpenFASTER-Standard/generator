import { useEffect, useState } from "react"
import { DocumentationView } from "@/components/DocumentationView"
import { PageShell } from "@/components/PageShell"
import { StructureView } from "@/components/StructureView"
import { apiGet } from "@/lib/api"
import type { DeclarationsResponse, DocumentationResponse, StructureResponse } from "@/lib/api"

export default function App() {
  const [activeTab, setActiveTab] = useState("structure")
  const [search, setSearch] = useState("")
  const [structure, setStructure] = useState<StructureResponse | null>(null)
  const [declarations, setDeclarations] = useState<DeclarationsResponse | null>(null)
  const [documentation, setDocumentation] = useState<DocumentationResponse | null>(null)

  useEffect(() => {
    apiGet<StructureResponse>("/structure").then(setStructure)
    apiGet<DeclarationsResponse>("/declarations").then(setDeclarations)
    apiGet<DocumentationResponse>("/documentation").then(setDocumentation)
  }, [])

  return (
    <PageShell activeTab={activeTab} onTabChange={setActiveTab} search={search} onSearchChange={setSearch}>
      {activeTab === "structure" && structure && declarations && (
        <StructureView structure={structure} declarations={declarations} search={search} />
      )}
      {activeTab === "documentation" && documentation && (
        <DocumentationView documentation={documentation} search={search} />
      )}
      {activeTab !== "structure" && activeTab !== "documentation" && (
        <p className="text-muted-foreground">{activeTab} page -- wired up in later tasks.</p>
      )}
    </PageShell>
  )
}
