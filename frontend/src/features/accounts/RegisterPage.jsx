import { useState } from 'react'
import { Link } from 'react-router-dom'
import { registerCustomer } from './registerApi'

function RegisterPage() {
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    confirm_password: '',
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  function handleChange(event) {
    const { name, value } = event.target

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSuccess('')

    if (form.password !== form.confirm_password) {
      setError('Passwords do not match.')
      return
    }

    if (new TextEncoder().encode(form.password).length > 72) {
      setError('Password must not exceed 72 bytes.')
      return
    }

    setLoading(true)

    try {
      const user = await registerCustomer({
        full_name: form.full_name.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
      })

      setSuccess(
        `Account created successfully for ${user.full_name}!`
      )

      setForm({
        full_name: '',
        email: '',
        password: '',
        confirm_password: '',
      })
    } catch (err) {
      if (err.response?.status === 409) {
        setError('This email is already registered.')
      } else if (err.response?.status === 422) {
        setError('Please check your registration details.')
      } else {
        setError('Registration failed. Please try again.')
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
    <main style={{ maxWidth: '440px', margin: '40px auto', padding: '20px' }}>
      <h1>FleetPulse</h1>
      <h2>Create Account</h2>

      <form
        onSubmit={handleSubmit}
        style={{ display: 'grid', gap: '15px', textAlign: 'left' }}
      >
        <label>
          Full Name
          <input
            type="text"
            name="full_name"
            value={form.full_name}
            onChange={handleChange}
            minLength={2}
            maxLength={100}
            autoComplete="name"
            required
            style={inputStyle}
          />
        </label>

        <label>
          Email Address
          <input
            type="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            autoComplete="email"
            required
            style={inputStyle}
          />
        </label>

        <label>
          Password
          <input
            type="password"
            name="password"
            value={form.password}
            onChange={handleChange}
            minLength={8}
            autoComplete="new-password"
            required
            style={inputStyle}
          />
        </label>

        <label>
          Confirm Password
          <input
            type="password"
            name="confirm_password"
            value={form.confirm_password}
            onChange={handleChange}
            minLength={8}
            autoComplete="new-password"
            required
            style={inputStyle}
          />
        </label>

        <button type="submit" disabled={loading} style={{ padding: '12px' }}>
          {loading ? 'Creating Account...' : 'Register'}
        </button>
      </form>

      {error && <p role="alert" style={{ color: '#dc2626', marginTop: '15px' }}>{error}</p>}
      {success && <p role="status" style={{ color: '#16803c', marginTop: '15px' }}>{success}</p>}

      <p style={{ marginTop: '20px' }}>
        <Link to="/">Back to Home</Link>
      </p>
      <p>
        Already have an account? <Link to="/login">Login</Link>
      </p>
    </main>
  )
}

export default RegisterPage