import { useNavigate, useParams } from "react-router-dom"

export interface Focus {
  mode: string
  subject: string | null
  predicate: string | null
  lang: string | null
  setFocus: (next: { mode: string; subject?: string; predicate?: string; lang?: string }) => void
}

export function useFocus(): Focus {
  const params = useParams<{ mode: string; subject?: string; predicate?: string; lang?: string }>()
  const navigate = useNavigate()

  function setFocus(next: { mode: string; subject?: string; predicate?: string; lang?: string }) {
    const segments = [next.mode, next.subject, next.predicate, next.lang].filter(
      (segment): segment is string => segment !== undefined,
    )
    navigate(`/${segments.map(encodeURIComponent).join("/")}`)
  }

  return {
    mode: params.mode ?? "graph",
    subject: params.subject ?? null,
    predicate: params.predicate ?? null,
    lang: params.lang ?? null,
    setFocus,
  }
}
