import type { SourceFileInfo } from "@/lib/api"

// The real, permanent GitHub path for a source file, not the local
// filesystem path this box happens to have it checked out at (which
// means nothing off this box, and leaks this deployment's own layout).
// Falls back to the raw path for the rare file with no public source
// (github_url_for on the backend returns null for anything outside the
// one real corpus repo this deployment knows about).
export function repoRelativePath(file: SourceFileInfo): string {
  if (!file.githubUrl) return file.path
  const marker = "/blob/main/"
  const index = file.githubUrl.indexOf(marker)
  return index === -1 ? file.path : file.githubUrl.slice(index + marker.length)
}
