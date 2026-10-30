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
    <main style={{
      maxWidth: '440px',
      margin: '40px auto',
      padding: '20px',
    }}>
      <h1>FleetPulse</h1>
      <h2>Forgot Password</h2>

      <p style={{ marginBottom: '20px' }}>
        Enter your registered email address to request
        a password reset link.
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
          Email Address

          <input
            type="email"
            value={email}
            onChange={(event) =>
              setEmail(event.target.value)
            }
            autoComplete="email"
            required
            style={{
              width: '100%',
              padding: '10px',
              marginTop: '5px',
              boxSizing: 'border-box',
            }}
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          style={{ padding: '12px' }}
        >
          {loading ? 'Sending...' : 'Send Reset Link'}
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

      {success && (
        <p role="status" style={{
          color: '#16803c',
          marginTop: '15px',
        }}>
          {success}
        </p>
      )}

      <p style={{ marginTop: '20px' }}>
        <Link to="/login">Back to Login</Link>
      </p>
    </main>
  )
}

export default ForgotPasswordPage