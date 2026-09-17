import { useState } from "react"
import { PageShell } from "@/components/PageShell"

export default function App() {
  const [activeTab, setActiveTab] = useState("structure")
  const [search, setSearch] = useState("")

  return (
    <PageShell activeTab={activeTab} onTabChange={setActiveTab} search={search} onSearchChange={setSearch}>
      <p className="text-muted-foreground">
        {activeTab} page -- wired up in later tasks.
      </p>
    </PageShell>
  )
}
