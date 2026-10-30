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
    <div style={{ marginTop: '20px' }}>
      <button
        type="button"
        onClick={handleLogout}
        disabled={loading}
        style={{
          padding: '10px 20px',
          cursor: loading ? 'wait' : 'pointer',
        }}
      >
        {loading ? 'Logging out...' : 'Logout'}
      </button>

      {error && (
        <p
          role="alert"
          style={{
            color: '#dc2626',
            marginTop: '10px',
          }}
        >
          {error}
        </p>
      )}
    </div>
  )
}

export default LogoutButton