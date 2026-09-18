import { useEffect, useState } from "react"
import { apiGet } from "@/lib/api"
import { repoRelativePath } from "@/lib/sourceFileLabel"
import type { SourceFileInfo } from "@/lib/api"

// A flat, one-glimpse list of every real source file this run touches --
// not just the root XSD path (which defines nothing on its own; the
// corpus is split across 13 real XSD files plus the annex PDF, see
// citations/source_files.py's own docstring). Each links to the real
// GitHub path, not this box's local filesystem layout, which means
// nothing off this box.
export function SourcesView() {
  const [files, setFiles] = useState<SourceFileInfo[] | undefined>(undefined)

  useEffect(() => {
    apiGet<SourceFileInfo[]>("/sources/files").then(setFiles)
  }, [])

  if (files === undefined) {
    return <p className="text-sm text-muted-foreground">Loading sources…</p>
  }

  return (
    <div>
      <h3 className="mb-4 text-lg font-semibold">All source files ({files.length})</h3>
      <ul className="space-y-2">
        {files.map((file) => (
          <li key={file.path} className="flex items-center gap-3 rounded border p-3">
            <span className="rounded bg-muted px-2 py-0.5 text-xs font-medium uppercase text-muted-foreground">
              {file.kind}
            </span>
            {file.githubUrl ? (
              <a
                href={file.githubUrl}
                target="_blank"
                rel="noreferrer"
                className="text-sm underline decoration-dotted underline-offset-2 hover:decoration-solid"
              >
                {repoRelativePath(file)}
              </a>
            ) : (
              <span className="text-sm">{file.path}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
