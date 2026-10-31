import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/auth'

function ProtectedRoute() {
  const { user, authLoading } = useAuth()

  if (authLoading) {
    return (
      <main className="workspace-loading" role="status">
        Checking your session...
      </main>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}

export default ProtectedRoute