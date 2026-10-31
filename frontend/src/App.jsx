import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import apiClient from './api/apiClient'

function App() {
  const [status, setStatus] = useState('Checking backend connection...')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    async function checkBackend() {
      try {
        const response = await apiClient.get('/api/v1/health', {
          signal: controller.signal,
        })

        if (response.data.status === 'healthy') {
          setStatus('Connected successfully')
          setMessage(response.data.message)
        } else {
          setStatus('Unexpected backend response')
        }
      } catch (error) {
        if (error.code === 'ERR_CANCELED') return

        setStatus('Connection failed')
        setMessage('Unable to communicate with the FastAPI backend.')
        console.error('Backend connection error:', error)
      }
    }

    checkBackend()

    return () => controller.abort()
  }, [])

  const connectionState = status === 'Connected successfully'
    ? 'ok'
    : status === 'Connection failed' || status === 'Unexpected backend response'
      ? 'error'
      : ''

  return (
    <>
      <header className="site-header">
        <Link to="/" className="brand">
          <span className="brand-symbol">F</span>
          FleetPulse
        </Link>

        <nav className="header-links" aria-label="Main navigation">
          <Link to="/login">Log in</Link>
          <Link to="/register" className="button button-primary">
            Get started
          </Link>
        </nav>
      </header>

      <main className="home-main">
        <section className="home-hero">
          <p className="eyebrow">Smart fleet management</p>

          <h1 className="display-title">
            A simpler way to manage your fleet.
          </h1>

          <p className="lead">
            FleetPulse is a smart fleet logistics and delivery
            management system designed to bring your operations
            together in one place.
          </p>

          <div className="hero-actions">
            <Link to="/register" className="button button-primary">
              Create an account
            </Link>

            <Link to="/login" className="button button-outline">
              Log in
            </Link>
          </div>
        </section>

        <section
          className="status-card"
          aria-label="Backend connection status"
        >
          <h2>System connection</h2>

          <div className="status-line" role="status">
            <span
              className={`status-dot ${connectionState}`}
              aria-hidden="true"
            />
            <span>{status}</span>
          </div>

          {message && (
            <p className="status-message">{message}</p>
          )}
        </section>
      </main>
    </>
  )
}

export default App