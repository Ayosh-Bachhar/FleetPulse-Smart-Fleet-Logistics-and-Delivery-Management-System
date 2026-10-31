import { useEffect, useState } from 'react'

import { useAuth } from '../../context/auth'

import { getTrips } from '../dispatch_planning/dispatchPlanningApi'

import {
  getTripRoute,
  calculateTripRoute,
} from './routeDistanceAndTimeApi'

import RouteSummaryPanel from './RouteSummaryPanel'


const STATUS_LABELS = {
  dispatched: 'Dispatched',
  completed: 'Completed',
  cancelled: 'Cancelled',
}


function formatDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}


function RouteDistanceAndTimePage() {
  const { user } = useAuth()

  const canView = (
    user?.role === 'admin'
    || user?.role === 'dispatcher'
  )

  const canCalculate = user?.role === 'dispatcher'

  const [trips, setTrips] = useState([])
  const [selectedTripId, setSelectedTripId] = useState('')

  const [route, setRoute] = useState(null)

  const [loadingTrips, setLoadingTrips] = useState(true)
  const [loadingRoute, setLoadingRoute] = useState(false)
  const [calculating, setCalculating] = useState(false)

  const [refresh, setRefresh] = useState(false)

  const [error, setError] = useState('')
  const [message, setMessage] = useState('')


  useEffect(() => {
    if (!canView) return

    const controller = new AbortController()

    async function loadTrips() {
      setLoadingTrips(true)

      try {
        const data = await getTrips(
          { page_size: 100 },
          controller.signal
        )

        if (!controller.signal.aborted) {
          setTrips(data.items)
        }
      } catch {
        if (!controller.signal.aborted) {
          setError('Unable to load trip records.')
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
    if (!canView || !selectedTripId) {
      return
    }

    let active = true

    async function loadSavedRoute() {
      setLoadingRoute(true)
      setRoute(null)
      setError('')
      setMessage('')

      try {
        const saved = await getTripRoute(
          selectedTripId
        )

        if (active) {
          setRoute(saved)
          setMessage('Saved route loaded.')
        }
      } catch (err) {
        if (active) {
          if (err.response?.status === 404) {
            setMessage(
              'No route has been calculated for this trip.'
            )
          } else {
            setError('Unable to load the saved route.')
          }
        }
      } finally {
        if (active) {
          setLoadingRoute(false)
        }
      }
    }

    loadSavedRoute()

    return () => {
      active = false
    }
  }, [canView, selectedTripId])


  const selectedTrip = trips.find(
    (trip) => trip.id === selectedTripId
  )


  async function handleCalculate() {
    if (
      !canCalculate
      || !selectedTripId
      || selectedTrip?.status === 'cancelled'
    ) {
      return
    }

    setCalculating(true)
    setError('')
    setMessage('')

    try {
      const result = await calculateTripRoute(
        selectedTripId,
        refresh
      )

      setRoute(result)

      setMessage(
        result.from_saved_route
          ? 'The existing route was reused.'
          : 'Route calculated and saved successfully.'
      )
    } catch (err) {
      const detail = err.response?.data?.detail

      setError(
        typeof detail === 'string'
          ? detail
          : err.code === 'ECONNABORTED'
            ? 'Route calculation timed out.'
            : 'Unable to calculate the route.'
      )
    } finally {
      setCalculating(false)
    }
  }


  if (!canView) {
    return (
      <section className="workspace-welcome">
        <h1 className="workspace-heading">
          Access restricted
        </h1>

        <p className="workspace-description">
          Route information is available only to
          Admin and Dispatcher accounts.
        </p>
      </section>
    )
  }


  return (
    <section className="route-page">
      <div>
        <p className="workspace-eyebrow">
          ROUTE OPERATIONS
        </p>

        <h1 className="workspace-heading">
          Route Distance and Time
        </h1>

        <p className="workspace-description">
          Calculate, save and review trip distances,
          travel durations and ordered route stops.
        </p>
      </div>

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
              Choose an existing F11 dispatched or
              completed trip.
            </p>
          </div>
        </div>

        <label className="field">
          Trip

          <select
            className="form-input"
            value={selectedTripId}
            disabled={loadingTrips || calculating}
            onChange={(event) => {
              setSelectedTripId(event.target.value)
              setRoute(null)
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
                {trip.order_count} orders
                {' — '}
                {STATUS_LABELS[trip.status]}
              </option>
            ))}
          </select>
        </label>

        {selectedTrip && (
          <div className="route-trip-preview">
            <div>
              <span>Driver</span>
              <strong>
                {selectedTrip.driver_name}
              </strong>
            </div>

            <div>
              <span>Vehicle</span>
              <strong>
                {selectedTrip.vehicle_registration}
              </strong>
            </div>

            <div>
              <span>Start</span>
              <strong>
                {formatDateTime(selectedTrip.start_at)}
              </strong>
            </div>

            <div>
              <span>Trip status</span>
              <strong>
                {STATUS_LABELS[selectedTrip.status]}
              </strong>
            </div>
          </div>
        )}

        {canCalculate && (
          <div className="route-actions">
            <label className="route-refresh-label">
              <input
                type="checkbox"
                checked={refresh}
                disabled={calculating}
                onChange={(event) => {
                  setRefresh(event.target.checked)
                }}
              />

              Recalculate saved route
            </label>

            <button
              type="button"
              className="button button-primary"
              disabled={
                calculating
                || loadingRoute
                || !selectedTripId
                || selectedTrip?.status === 'cancelled'
              }
              onClick={handleCalculate}
            >
              {calculating
                ? 'Calculating route...'
                : route && !refresh
                  ? 'Reuse saved route'
                  : 'Calculate route'}
            </button>
          </div>
        )}

        {!canCalculate && (
          <p className="route-readonly-note">
            Admin accounts can view saved routes.
            Only Dispatcher accounts can calculate routes.
          </p>
        )}

        {selectedTrip?.status === 'cancelled' && (
          <p className="route-readonly-note">
            Cancelled trips cannot be recalculated.
          </p>
        )}
      </section>

      {loadingRoute && (
        <div className="fleet-panel">
          Loading saved route...
        </div>
      )}

      {route && (
        <RouteSummaryPanel route={route} />
      )}
    </section>
  )
}

export default RouteDistanceAndTimePage