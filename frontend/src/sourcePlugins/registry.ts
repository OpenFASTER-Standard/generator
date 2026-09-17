import { pdfPlugin } from "@/sourcePlugins/pdfPlugin"
import { xsdPlugin } from "@/sourcePlugins/xsdPlugin"
import type { SourceLocator } from "@/lib/sourceLocator"
import type { SourcePlugin } from "@/sourcePlugins/types"

export const PLUGINS: Record<string, SourcePlugin<SourceLocator>> = {
  pdf: pdfPlugin as SourcePlugin<SourceLocator>,
  xsd: xsdPlugin as SourcePlugin<SourceLocator>,
}

export function getPlugin(kind: string): SourcePlugin<SourceLocator> | undefined {
  return PLUGINS[kind]
}
