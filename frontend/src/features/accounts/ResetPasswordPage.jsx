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

      // Remove the single-use token from the address bar.
      window.history.replaceState(
        window.history.state,
        '',
        '/reset-password'
      )
    } catch (err) {
      if (err.response?.status === 400) {
        setError('This reset link is invalid, expired, or already used.')
      } else if (err.response?.status === 422) {
        setError('Please check your password details.')
      } else {
        setError('Unable to reset password. Please try again.')
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
      <h2>Reset Password</h2>

      {success ? (
        <section role="status">
          <h3>Password Reset Successful!</h3>

          <p>
            Your password has been updated successfully.
            Please log in with your new password.
          </p>

          <p style={{ marginTop: '20px' }}>
            <a href="/login">Go to Login</a>
          </p>
        </section>
      ) : !token || token.length < 32 ? (
        <section role="alert">
          <p style={{ color: '#dc2626' }}>
            Invalid password reset link.
          </p>

          <p style={{ marginTop: '20px' }}>
            <Link to="/forgot-password">
              Request a New Reset Link
            </Link>
          </p>
        </section>
      ) : (
        <>
          <p style={{ marginBottom: '20px' }}>
            Enter your new password below.
          </p>

          <form
            onSubmit={handleSubmit}
            style={{
              display: 'grid',
              gap: '15px',
              textAlign: 'left',
            }}
          >
            <label>
              New Password

              <input
                type="password"
                value={newPassword}
                onChange={(event) =>
                  setNewPassword(event.target.value)
                }
                minLength={8}
                autoComplete="new-password"
                required
                style={inputStyle}
              />
            </label>

            <label>
              Confirm New Password

              <input
                type="password"
                value={confirmPassword}
                onChange={(event) =>
                  setConfirmPassword(event.target.value)
                }
                minLength={8}
                autoComplete="new-password"
                required
                style={inputStyle}
              />
            </label>

            <button
              type="submit"
              disabled={loading}
              style={{ padding: '12px' }}
            >
              {loading ? 'Resetting...' : 'Reset Password'}
            </button>
          </form>

          {error && (
            <p role="alert" style={{
              color: '#dc2626',
              marginTop: '15px',
            }}>
              {error}
            </p>
          )}
        </>
      )}
    </main>
  )
}

export default ResetPasswordPage