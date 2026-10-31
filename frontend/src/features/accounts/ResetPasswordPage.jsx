import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { completePasswordReset } from './passwordResetApi'

function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()

    setError('')

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    if (newPassword.length < 8) {
      setError('Password must contain at least 8 characters.')
      return
    }

    if (new TextEncoder().encode(newPassword).length > 72) {
      setError('Password must not exceed 72 bytes.')
      return
    }

    setLoading(true)

    try {
      await completePasswordReset(token, newPassword)

      setSuccess(true)
      setNewPassword('')
      setConfirmPassword('')

      window.history.replaceState(
        window.history.state,
        '',
        '/reset-password'
      )
    } catch (err) {
      if (err.response?.status === 400) {
        setError(
          'This reset link is invalid, expired, or already used.'
        )
      } else if (err.response?.status === 422) {
        setError('Please check your password details.')
      } else {
        setError(
          'Unable to reset password. Please try again.'
        )
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
          <h1 className="page-title">Reset password</h1>

          {success ? (
            <section role="status">
              <p className="notice notice-success">
                Your password has been updated successfully.
              </p>

              <p className="auth-footer">
                <Link to="/login" className="text-link">
                  Go to login
                </Link>
              </p>
            </section>
          ) : !token || token.length < 32 ? (
            <section role="alert">
              <p className="notice notice-error">
                Invalid password reset link.
              </p>

              <p className="auth-footer">
                <Link
                  to="/forgot-password"
                  className="text-link"
                >
                  Request a new reset link
                </Link>
              </p>
            </section>
          ) : (
            <>
              <p className="page-subtitle">
                Choose a new password for your account.
              </p>

              <form
                className="form-stack"
                onSubmit={handleSubmit}
              >
                <label className="field">
                  New password
                  <input
                    className="form-input"
                    type="password"
                    value={newPassword}
                    onChange={(event) =>
                      setNewPassword(event.target.value)
                    }
                    minLength={8}
                    autoComplete="new-password"
                    required
                  />

                  <span className="form-helper">
                    At least 8 characters.
                  </span>
                </label>

                <label className="field">
                  Confirm new password
                  <input
                    className="form-input"
                    type="password"
                    value={confirmPassword}
                    onChange={(event) =>
                      setConfirmPassword(event.target.value)
                    }
                    minLength={8}
                    autoComplete="new-password"
                    required
                  />
                </label>

                <div className="form-actions">
                  <button
                    className="button button-primary button-block"
                    type="submit"
                    disabled={loading}
                  >
                    {loading
                      ? 'Resetting...'
                      : 'Reset password'}
                  </button>
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
            </>
          )}
        </section>
      </main>
    </>
  )
}

export default ResetPasswordPage