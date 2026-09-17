import { useState } from "react"

const STORAGE_KEY = "provenance-platform:reviewer"

export function useReviewer(): [string, (name: string) => void] {
  const [reviewer, setReviewerState] = useState(
    () => window.localStorage.getItem(STORAGE_KEY) ?? "",
  )

  function setReviewer(name: string) {
    window.localStorage.setItem(STORAGE_KEY, name)
    setReviewerState(name)
  }

  return [reviewer, setReviewer]
}
