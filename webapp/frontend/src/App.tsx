import { Routes, Route, Link, Outlet } from "react-router-dom"
import { IndexView } from "./views/IndexView"
import { PageDetailView } from "./views/PageDetailView"
import { AddCitationView } from "./views/AddCitationView"
import { ReviewView } from "./views/ReviewView"

function Layout() {
  return (
    <div>
      <nav>
        <Link to="/">Pages</Link>
        <Link to="/add">Add citation</Link>
        <Link to="/review">Review</Link>
      </nav>
      <Outlet />
    </div>
  )
}

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<IndexView />} />
        <Route path="/pages/:factKey" element={<PageDetailView />} />
        <Route path="/add" element={<AddCitationView />} />
        <Route path="/review" element={<ReviewView />} />
      </Route>
    </Routes>
  )
}
