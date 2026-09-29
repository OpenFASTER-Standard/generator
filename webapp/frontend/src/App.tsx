import { Routes, Route } from "react-router-dom"
import { IndexView } from "./views/IndexView"
import { PageDetailView } from "./views/PageDetailView"
import { AddCitationView } from "./views/AddCitationView"
import { ReviewView } from "./views/ReviewView"

export function App() {
  return (
    <Routes>
      <Route path="/" element={<IndexView />} />
      <Route path="/pages/:factKey" element={<PageDetailView />} />
      <Route path="/add" element={<AddCitationView />} />
      <Route path="/review" element={<ReviewView />} />
    </Routes>
  )
}
