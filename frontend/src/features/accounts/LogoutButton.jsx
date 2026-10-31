import { useState } from 'react'
import { useAuth } from '../../context/auth'

function LogoutButton() {
  const { logout } = useAuth()

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleLogout() {
    setLoading(true)
    setError('')

    try {
      await logout()
    } catch {
      setError('Logout failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button
        className="button button-outline"
        type="button"
        onClick={handleLogout}
        disabled={loading}
      >
        {loading ? 'Logging out...' : 'Log out'}
      </button>

      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}
    </>
  )
}

export default LogoutButton