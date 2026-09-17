import type { ReactNode } from "react"
import type { SourceLocator } from "@/lib/sourceLocator"

export interface SourcePlugin<L extends SourceLocator = SourceLocator> {
  kind: L["kind"]
  /** A small, precise citation for one exact fact -- a cropped image, a fragment. */
  renderLocator(locator: L): ReactNode
  /** The entire source document; clicking anywhere calls onLocatorClick with
   * a locator at this plugin's own real granularity (page-level for PDF,
   * whole-component for XSD -- there is no finer-grained data to click into). */
  renderWhole(locator: L, onLocatorClick: (locator: L) => void): ReactNode
}
