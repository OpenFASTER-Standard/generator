import { createContext, useContext, useMemo, useState } from "react"
import type { ReactNode } from "react"

interface HoverFocusValue {
  hovered: string | null
  setHovered: (subject: string | null) => void
}

const HoverFocusContext = createContext<HoverFocusValue | null>(null)

export function HoverFocusProvider({ children }: { children: ReactNode }) {
  const [hovered, setHovered] = useState<string | null>(null)
  const value = useMemo(() => ({ hovered, setHovered }), [hovered])
  return <HoverFocusContext.Provider value={value}>{children}</HoverFocusContext.Provider>
}

export function useHoverFocus(): HoverFocusValue {
  const context = useContext(HoverFocusContext)
  if (!context) {
    throw new Error("useHoverFocus must be used inside a HoverFocusProvider")
  }
  return context
}
