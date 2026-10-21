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
        if (error.code === 'ERR_CANCELED') {
          return
        }

        setStatus('Connection failed')
        setMessage('Unable to communicate with the FastAPI backend.')
        console.error('Backend connection error:', error)
      }
    }

    checkBackend()

    return () => controller.abort()
  }, [])

  return (
    <main>
      <h1>FleetPulse</h1>
      <h2>Smart Fleet Logistics and Delivery Management System</h2>

      <h3>Frontend and Backend Connection Test</h3>

      <p>
        <strong>Status:</strong> {status}
      </p>

      <p>{message}</p>
    </main>
  )
}

export default App