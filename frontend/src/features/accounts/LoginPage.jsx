import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/auth'
import LogoutButton from './LogoutButton'

function LoginPage() {
  const { user, authLoading, login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login({
        email: email.trim().toLowerCase(),
        password,
      })

      setPassword('')
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Invalid email or password.')
      } else if (err.response?.status === 422) {
        setError('Please enter valid login details.')
      } else {
        setError('Unable to log in. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    width: '100%',
    padding: '10px',
    marginTop: '5px',
    boxSizing: 'border-box',
  }

  return (
    <main style={{
      maxWidth: '440px',
      margin: '40px auto',
      padding: '20px',
    }}>
      <h1>FleetPulse</h1>
      <h2>User Login</h2>

      {authLoading ? (
        <p>Checking your session...</p>
      ) : user ? (
        <section role="status">
          <h3>Login Successful!</h3>
          <p>Welcome, {user.full_name}!</p>
          <p>Email: {user.email}</p>
          <p>Role: {user.role}</p>
          <p>Your session is active.</p>

          <LogoutButton />
          <p style={{ marginTop: '20px' }}>
            <Link to="/">Back to Home</Link>
          </p>
        </section>
      ) : (
        <>
          <form
            onSubmit={handleSubmit}
            style={{
              display: 'grid',
              gap: '15px',
              textAlign: 'left',
            }}
          >
            <label>
              Email Address
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
                style={inputStyle}
              />
            </label>

            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
                style={inputStyle}
              />
            </label>

            <button
              type="submit"
              disabled={loading}
              style={{ padding: '12px' }}
            >
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>

          <p style={{ marginTop: '15px' }}>
            <Link to="/forgot-password">Forgot Password?</Link>
          </p>

          {error && (
            <p role="alert" style={{ color: '#dc2626' }}>
              {error}
            </p>
          )}

          <p>
            Don't have an account?{' '}
            <Link to="/register">Register</Link>
          </p>

          <Link to="/">Back to Home</Link>
        </>
      )}
    </main>
  )
}

export default LoginPage