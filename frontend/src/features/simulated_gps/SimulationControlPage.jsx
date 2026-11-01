import { useEffect, useState } from 'react'

import { useAuth } from '../../context/auth'

import {
  getGpsTrips,
  getGpsPosition,
  startGpsSimulation,
  pauseGpsSimulation,
  resetGpsSimulation,
} from './simulatedGpsApi'


const STATUS_LABELS = {
  not_started: 'Not started',
  idle: 'Ready',
  running: 'Running',
  paused: 'Paused',
  finished: 'Route finished',
  stopped: 'Stopped',
}


function errorMessage(error, fallback) {
  const detail = error.response?.data?.detail

  return typeof detail === 'string'
    ? detail
    : fallback
}


function formatDateTime(value) {
  if (!value) return '—'

  return new Date(value).toLocaleString()
}


function GPSStat({ label, value }) {
  return (
    <div className="gps-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}


function SimulationControlPage() {
  const { user } = useAuth()

  const canView = (
    user?.role === 'admin'
    || user?.role === 'dispatcher'
    || user?.role === 'driver'
  )

  const canManage = user?.role === 'dispatcher'

  const [trips, setTrips] = useState([])
  const [tripId, setTripId] = useState('')

  const [position, setPosition] = useState(null)
  const [speedKmh, setSpeedKmh] = useState(30)

  const [loadingTrips, setLoadingTrips] = useState(true)
  const [loadingPosition, setLoadingPosition] = useState(false)
  const [busy, setBusy] = useState(false)

  const [error, setError] = useState('')
  const [message, setMessage] = useState('')


  useEffect(() => {
    if (!canView) return

    const controller = new AbortController()

    async function loadTrips() {
      setLoadingTrips(true)

      try {
        const result = await getGpsTrips(
          { page_size: 100 },
          controller.signal
        )

        if (!controller.signal.aborted) {
          setTrips(result.items)
        }

      } catch {
        if (!controller.signal.aborted) {
          setError('Unable to load GPS trips.')
        }

      } finally {
        if (!controller.signal.aborted) {
          setLoadingTrips(false)
        }
      }
    }

    loadTrips()

    return () => controller.abort()
  }, [canView])


  useEffect(() => {
    if (!canView || !tripId) return

    let active = true

    const controller = new AbortController()

    async function refreshPosition() {
      try {
        const result = await getGpsPosition(
          tripId,
          controller.signal
        )

        if (active) {
          setPosition(result)
          setLoadingPosition(false)
        }

      } catch (err) {
        if (active) {
          setError(
            errorMessage(
              err,
              'Unable to read GPS position.'
            )
          )

          setLoadingPosition(false)
        }
      }
    }

    setLoadingPosition(true)

    refreshPosition()

    // Browser only reads updates. The backend
    // performs the movement every five seconds.
    const interval = window.setInterval(
      refreshPosition,
      5000
    )

    return () => {
      active = false
      controller.abort()
      window.clearInterval(interval)
    }
  }, [canView, tripId])


  const selectedTrip = trips.find(
    (trip) => trip.id === tripId
  )

  const isDispatched = (
    selectedTrip?.trip_status === 'dispatched'
    && position?.trip_status === 'dispatched'
  )

  const isRunning = position?.status === 'running'

  const canStart = (
    canManage
    && isDispatched
    && selectedTrip?.route_available
    && position
    && !isRunning
  )


  async function runAction(action) {
    if (!tripId || !canManage || busy) return

    setBusy(true)
    setError('')
    setMessage('')

    try {
      let result

      if (action === 'start') {
        result = await startGpsSimulation(
          tripId,
          speedKmh
        )

      } else if (action === 'pause') {
        result = await pauseGpsSimulation(
          tripId
        )

      } else {
        result = await resetGpsSimulation(
          tripId
        )
      }

      setPosition(result)

      setMessage(
        action === 'start'
          ? 'GPS simulation started.'
          : action === 'pause'
            ? 'GPS simulation paused.'
            : 'GPS simulation reset.'
      )

    } catch (err) {
      setError(
        errorMessage(
          err,
          `Unable to ${action} the simulation.`
        )
      )

    } finally {
      setBusy(false)
    }
  }


  if (!canView) {
    return (
      <section className="workspace-welcome">
        <h1 className="workspace-heading">
          Access restricted
        </h1>

        <p className="workspace-description">
          Simulated GPS is available to
          Admin, Dispatcher and Driver accounts.
        </p>
      </section>
    )
  }


  return (
    <section className="gps-page">
      <header>
        <p className="workspace-eyebrow">
          DELIVERY OPERATIONS
        </p>

        <h1 className="workspace-heading">
          Simulated GPS
        </h1>

        <p className="workspace-description">
          Simulate vehicle movement along saved
          F12 and F13 route geometry. Position
          updates are generated every five seconds
          by the backend.
        </p>
      </header>

      {error && (
        <p
          className="notice notice-error"
          role="alert"
        >
          {error}
        </p>
      )}

      {message && (
        <p
          className="notice notice-success"
          role="status"
        >
          {message}
        </p>
      )}

      <section className="fleet-panel">
        <div className="fleet-panel-header">
          <div>
            <h2>Select a trip</h2>

            <p>
              Choose a trip with a saved route.
              The optimized F13 route is used
              automatically when available.
            </p>
          </div>
        </div>

        <label className="field">
          Trip

          <select
            className="form-input"
            value={tripId}
            disabled={loadingTrips || busy}
            onChange={(event) => {
              setTripId(event.target.value)
              setPosition(null)
              setError('')
              setMessage('')
            }}
          >
            <option value="">
              {loadingTrips
                ? 'Loading trips...'
                : 'Select a trip'}
            </option>

            {trips.map((trip) => (
              <option
                key={trip.id}
                value={trip.id}
              >
                {trip.id.slice(-8).toUpperCase()}
                {' — '}
                {trip.vehicle_registration}
                {' — '}
                {trip.trip_status}
                {!trip.route_available
                  ? ' — No route'
                  : ''}
              </option>
            ))}
          </select>
        </label>

        {selectedTrip && (
          <div className="gps-trip-summary">
            <GPSStat
              label="Vehicle"
              value={selectedTrip.vehicle_registration}
            />

            <GPSStat
              label="Driver"
              value={selectedTrip.driver_name}
            />

            <GPSStat
              label="Assigned orders"
              value={selectedTrip.order_count}
            />

            <GPSStat
              label="Route"
              value={
                selectedTrip.route_available
                  ? 'Available'
                  : 'Calculate F12 first'
              }
            />
          </div>
        )}

        {canManage && selectedTrip && (
          <div className="gps-controls">
            <label className="field">
              Simulation speed

              <select
                className="form-input"
                value={speedKmh}
                disabled={busy || isRunning}
                onChange={(event) => {
                  setSpeedKmh(Number(event.target.value))
                }}
              >
                <option value={10}>10 km/h</option>
                <option value={20}>20 km/h</option>
                <option value={30}>30 km/h</option>
                <option value={40}>40 km/h</option>
                <option value={60}>60 km/h</option>
              </select>
            </label>

            <div className="gps-control-buttons">
              <button
                type="button"
                className="button button-primary"
                disabled={
                  busy
                  || loadingPosition
                  || !canStart
                }
                onClick={() => runAction('start')}
              >
                {position?.status === 'paused'
                  ? 'Resume simulation'
                  : 'Start simulation'}
              </button>

              <button
                type="button"
                className="button button-outline"
                disabled={busy || !isRunning}
                onClick={() => runAction('pause')}
              >
                Pause
              </button>

              <button
                type="button"
                className="button button-outline"
                disabled={
                  busy
                  || !isDispatched
                  || !position
                }
                onClick={() => runAction('reset')}
              >
                Reset
              </button>
            </div>
          </div>
        )}
      </section>

      {loadingPosition && (
        <div className="fleet-panel">
          Loading saved GPS position...
        </div>
      )}

      {position && (
        <section className="fleet-panel">
          <div className="fleet-panel-header">
            <div>
              <h2>Vehicle position</h2>

              <p>
                Simulated coordinates — not actual GPS
                hardware data.
              </p>
            </div>

            <span
              className={`gps-status gps-status-${position.status}`}
            >
              {STATUS_LABELS[position.status]}
            </span>
          </div>

          <div className="gps-progress-header">
            <span>Route progress</span>

            <strong>
              {position.progress_percent.toFixed(2)}%
            </strong>
          </div>

          <div
            className="gps-progress-track"
            role="progressbar"
            aria-label="Route progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={position.progress_percent}
          >
            <div
              className="gps-progress-fill"
              style={{
                width: `${position.progress_percent}%`,
              }}
            />
          </div>

          <div className="gps-position-stats">
            <GPSStat
              label="Latitude"
              value={position.latitude.toFixed(6)}
            />

            <GPSStat
              label="Longitude"
              value={position.longitude.toFixed(6)}
            />

            <GPSStat
              label="Simulation speed"
              value={`${position.speed_kmh} km/h`}
            />

            <GPSStat
              label="Route distance"
              value={`${position.route_distance_km} km`}
            />

            <GPSStat
              label="Simulated progress"
              value={`${position.travelled_route_km} km`}
            />

            <GPSStat
              label="Remaining route"
              value={`${position.remaining_route_km} km`}
            />

            <GPSStat
              label="GPS updates"
              value={position.tick_count}
            />

            <GPSStat
              label="Last updated"
              value={formatDateTime(position.updated_at)}
            />
          </div>

          {position.status === 'finished' && (
            <p className="gps-information">
              The simulated vehicle reached the last
              route coordinate. The F11 trip is still
              managed separately through Dispatch Planning.
            </p>
          )}

          {position.status === 'stopped' && (
            <p className="gps-information">
              Movement has stopped because the trip ended
              or the saved route changed.
            </p>
          )}

          <p className="gps-information">
            The simulation uses F12/F13 geometry for
            movement. F4 maintenance mileage and F5
            actual trip mileage are not modified.
            A map view will be provided by F16.
          </p>
        </section>
      )}
    </section>
  )
}

export default SimulationControlPage