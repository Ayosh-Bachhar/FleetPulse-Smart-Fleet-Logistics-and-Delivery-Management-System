import { useState } from 'react'
import { Link } from 'react-router-dom'

import { requestPasswordReset } from './passwordResetApi'

function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()

    setError('')
    setSuccess('')
    setLoading(true)

    try {
      const result = await requestPasswordReset(
        email.trim().toLowerCase()
      )

      setSuccess(result.message)
      setEmail('')
    } catch (err) {
      if (err.response?.status === 503) {
        setError(
          'Password reset service is temporarily unavailable.'
        )
      } else if (err.response?.status === 422) {
        setError('Please enter a valid email address.')
      } else {
        setError('Unable to process your request. Try again.')
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
          <h1 className="page-title">Forgot password?</h1>

          <p className="page-subtitle">
            Enter your registered email address.
            We'll send you a password reset link.
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

            <div className="form-actions">
              <button
                className="button button-primary button-block"
                type="submit"
                disabled={loading}
              >
                {loading ? 'Sending...' : 'Send reset link'}
              </button>
            </div>
          </form>

          {error && (
            <p className="notice notice-error" role="alert">
              {error}
            </p>
          )}

          {success && (
            <p className="notice notice-success" role="status">
              {success}
            </p>
          )}

          <p className="auth-footer">
            <Link to="/login" className="text-link">
              Back to login
            </Link>
          </p>
        </section>
      </main>
    </>
  )
}

export default ForgotPasswordPage