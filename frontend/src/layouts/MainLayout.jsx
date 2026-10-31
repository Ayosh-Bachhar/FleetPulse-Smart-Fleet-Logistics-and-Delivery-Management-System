import { Outlet } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import Navbar from '../components/Navbar'

function MainLayout() {
  return (
    <div className="workspace-shell">
      <Sidebar />

      <div className="workspace-page">
        <Navbar />

        <main className="workspace-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default MainLayout