import { useEffect, useState } from "react"
import { PageShell } from "@/components/PageShell"
import { StructureView } from "@/components/StructureView"
import { apiGet } from "@/lib/api"
import type { DeclarationsResponse, StructureResponse } from "@/lib/api"

export default function App() {
  const [activeTab, setActiveTab] = useState("structure")
  const [search, setSearch] = useState("")
  const [structure, setStructure] = useState<StructureResponse | null>(null)
  const [declarations, setDeclarations] = useState<DeclarationsResponse | null>(null)

  useEffect(() => {
    apiGet<StructureResponse>("/structure").then(setStructure)
    apiGet<DeclarationsResponse>("/declarations").then(setDeclarations)
  }, [])

  return (
    <PageShell activeTab={activeTab} onTabChange={setActiveTab} search={search} onSearchChange={setSearch}>
      {activeTab === "structure" && structure && declarations && (
        <StructureView structure={structure} declarations={declarations} search={search} />
      )}
      {activeTab !== "structure" && (
        <p className="text-muted-foreground">{activeTab} page -- wired up in later tasks.</p>
      )}
    </PageShell>
  )
}
