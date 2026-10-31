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

  return (
    <>
      <header className="site-header">
        <Link to="/" className="brand">
          <span className="brand-symbol">F</span>
          FleetPulse
        </Link>
      </header>

      <main className="auth-container">
        <section className="auth-card">
          {authLoading ? (
            <p role="status" className="page-subtitle">
              Checking your session...
            </p>
          ) : user ? (
            <>
              <h1 className="page-title">
                Welcome back, {user.full_name}.
              </h1>

              <p className="page-subtitle">
                Your session is active.
              </p>

              <div className="account-details" role="status">
                <span>
                  <strong>Email:</strong> {user.email}
                </span>
                <span>
                  <strong>Role:</strong> {user.role}
                </span>
              </div>

              <LogoutButton />

              <p className="auth-footer">
                <Link to="/" className="text-link">
                  Back to home
                </Link>
              </p>
            </>
          ) : (
            <>
              <h1 className="page-title">Welcome back</h1>

              <p className="page-subtitle">
                Log in to your FleetPulse account.
              </p>

              <form
                className="form-stack"
                onSubmit={handleSubmit}
              >
                <label className="field">
                  Email address
                  <input
                    className="form-input"
                    type="email"
                    value={email}
                    onChange={(event) =>
                      setEmail(event.target.value)
                    }
                    autoComplete="email"
                    placeholder="name@example.com"
                    required
                  />
                </label>

                <label className="field">
                  Password
                  <input
                    className="form-input"
                    type="password"
                    value={password}
                    onChange={(event) =>
                      setPassword(event.target.value)
                    }
                    autoComplete="current-password"
                    required
                  />
                </label>

                <div className="form-actions">
                  <button
                    className="button button-primary button-block"
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? 'Logging in...' : 'Log in'}
                  </button>

                  <div className="form-secondary">
                    <Link
                      className="text-link"
                      to="/forgot-password"
                    >
                      Forgot password?
                    </Link>
                  </div>
                </div>
              </form>

              {error && (
                <p
                  className="notice notice-error"
                  role="alert"
                >
                  {error}
                </p>
              )}

              <p className="auth-footer">
                Don't have an account?{' '}
                <Link to="/register" className="text-link">
                  Register
                </Link>
              </p>
            </>
          )}
        </section>
      </main>
    </>
  )
}

export default LoginPage