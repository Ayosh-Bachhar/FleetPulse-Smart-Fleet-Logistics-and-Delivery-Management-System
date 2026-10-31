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
          <h1 className="page-title">Create an account</h1>

          <p className="page-subtitle">
            Get started with FleetPulse.
          </p>

          <form
            className="form-stack"
            onSubmit={handleSubmit}
          >
            <label className="field">
              Full name
              <input
                className="form-input"
                type="text"
                name="full_name"
                value={form.full_name}
                onChange={handleChange}
                minLength={2}
                maxLength={100}
                autoComplete="name"
                placeholder="Your full name"
                required
              />
            </label>

            <label className="field">
              Email address
              <input
                className="form-input"
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
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
                name="password"
                value={form.password}
                onChange={handleChange}
                minLength={8}
                autoComplete="new-password"
                required
              />

              <span className="form-helper">
                At least 8 characters.
              </span>
            </label>

            <label className="field">
              Confirm password
              <input
                className="form-input"
                type="password"
                name="confirm_password"
                value={form.confirm_password}
                onChange={handleChange}
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
                  ? 'Creating account...'
                  : 'Create account'}
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
              {success}{' '}
              <Link to="/login">Log in</Link>
            </p>
          )}

          <p className="auth-footer">
            Already have an account?{' '}
            <Link to="/login" className="text-link">
              Log in
            </Link>
          </p>
        </section>
      </main>
    </>
  )
}

export default RegisterPage