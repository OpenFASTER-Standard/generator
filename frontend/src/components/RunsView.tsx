import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { apiGet } from "@/lib/api"
import type { RunDiffResponse, RunSummary } from "@/lib/api"

interface RunsViewProps {
  runs: RunSummary[]
}

export function RunsView({ runs }: RunsViewProps) {
  const [runA, setRunA] = useState(runs[0]?.runId ?? "")
  const [runB, setRunB] = useState(runs[runs.length - 1]?.runId ?? "")
  const [diff, setDiff] = useState<RunDiffResponse | null>(null)

  async function loadDiff() {
    setDiff(await apiGet<RunDiffResponse>(`/runs/${runA}/diff/${runB}`))
  }

  return (
    <div>
      <Table className="mb-4">
        <TableHeader>
          <TableRow>
            <TableHead>Run</TableHead>
            <TableHead>Created</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => (
            <TableRow key={run.runId}>
              <TableCell>{run.runId}</TableCell>
              <TableCell>{run.createdAt}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex items-center gap-2">
        <Select value={runA} onValueChange={(value) => value && setRunA(value)}>
          <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            {runs.map((run) => <SelectItem key={run.runId} value={run.runId}>{run.runId}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={runB} onValueChange={(value) => value && setRunB(value)}>
          <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            {runs.map((run) => <SelectItem key={run.runId} value={run.runId}>{run.runId}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button onClick={loadDiff}>Diff</Button>
      </div>
      {diff && (
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <h4 className="font-semibold">Removed</h4>
            {diff.removed.map((row, index) => <div key={index}>{row.join(" ")}</div>)}
          </div>
          <div>
            <h4 className="font-semibold">Added</h4>
            {diff.added.map((row, index) => <div key={index}>{row.join(" ")}</div>)}
          </div>
        </div>
      )}
    </div>
  )
}
