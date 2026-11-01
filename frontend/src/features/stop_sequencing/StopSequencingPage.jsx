import { useEffect, useState } from 'react'

import { useAuth } from '../../context/auth'
import { getTrips } from '../dispatch_planning/dispatchPlanningApi'

import {
  getSavedSequence,
  previewSequence,
  applySequence,
} from './stopSequencingApi'

import StopSequencePanel from './StopSequencePanel'


function getErrorMessage(error, fallback) {
  const detail = error.response?.data?.detail

  return typeof detail === 'string'
    ? detail
    : fallback
}


const STATUS_LABELS = {
  dispatched: 'Dispatched',
  completed: 'Completed',
  cancelled: 'Cancelled',
}


function StopSequencingPage() {
  const { user } = useAuth()

  const canView = (
    user?.role === 'admin'
    || user?.role === 'dispatcher'
  )

  const canManage = user?.role === 'dispatcher'

  const [trips, setTrips] = useState([])
  const [tripId, setTripId] = useState('')
  const [sequence, setSequence] = useState(null)

  const [loadingTrips, setLoadingTrips] = useState(true)
  const [loadingSequence, setLoadingSequence] = useState(false)
  const [busy, setBusy] = useState(false)

  const [error, setError] = useState('')
  const [message, setMessage] = useState('')


  useEffect(() => {
    if (!canView) return

    const controller = new AbortController()

    async function loadTrips() {
      setLoadingTrips(true)

      try {
        const result = await getTrips(
          { page_size: 100 },
          controller.signal
        )

        if (!controller.signal.aborted) {
          setTrips(result.items)
        }

      } catch {
        if (!controller.signal.aborted) {
          setError(
            'Unable to load dispatched trips.'
          )
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

    async function loadSavedSequence() {
      setLoadingSequence(true)
      setSequence(null)
      setError('')
      setMessage('')

      try {
        const result = await getSavedSequence(
          tripId
        )

        if (active) {
          setSequence(result)
          setMessage('Saved sequence loaded.')
        }

      } catch (err) {
        if (active) {
          if (err.response?.status === 404) {
            setMessage(
              'No applied sequence found. '
              + 'Preview to optimize this trip.'
            )

          } else {
            setError(
              getErrorMessage(
                err,
                'Unable to load saved sequence.'
              )
            )
          }
        }

      } finally {
        if (active) {
          setLoadingSequence(false)
        }
      }
    }

    loadSavedSequence()

    return () => {
      active = false
    }
  }, [canView, tripId])


  const selectedTrip = trips.find(
    (trip) => trip.id === tripId
  )

  const canPreview = (
    canManage
    && selectedTrip?.status === 'dispatched'
    && !sequence?.is_applied
  )


  async function handlePreview() {
    if (!canPreview || busy) return

    setBusy(true)
    setError('')
    setMessage('')

    try {
      const result = await previewSequence(tripId)

      setSequence(result)

      setMessage(
        'Preview calculated. '
        + 'Your existing route has not changed.'
      )

    } catch (err) {
      setSequence(null)

      setError(
        getErrorMessage(
          err,
          'Unable to calculate the stop sequence.'
        )
      )

    } finally {
      setBusy(false)
    }
  }


  async function handleApply() {
    if (
      !canManage
      || !sequence?.can_apply
      || busy
    ) {
      return
    }

    const confirmed = window.confirm(
      'Apply this stop sequence to the F12 route?'
    )

    if (!confirmed) return

    setBusy(true)
    setError('')
    setMessage('')

    try {
      const result = await applySequence(
        tripId,
        sequence.preview_token
      )

      setSequence(result)

      setMessage(
        'Optimized stop sequence saved successfully.'
      )

    } catch (err) {
      setError(
        getErrorMessage(
          err,
          'Unable to apply optimization. '
          + 'Please preview again.'
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
          Stop Sequencing is available to
          Admin and Dispatcher accounts.
        </p>
      </section>
    )
  }


  return (
    <section className="sequence-page">
      <header>
        <p className="workspace-eyebrow">
          ROUTE OPERATIONS
        </p>

        <h1 className="workspace-heading">
          Stop Sequencing
        </h1>

        <p className="workspace-description">
          Optimize delivery stop order using
          the Nearest-Neighbour Algorithm,
          subject to pickup and vehicle
          capacity constraints.
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
              Create an F11 dispatch and calculate
              its F12 route before optimization.
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
              setSequence(null)
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
          <div className="sequence-trip-info">
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
              <span>Orders</span>
              <strong>
                {selectedTrip.order_count}
              </strong>
            </div>

            <div>
              <span>Status</span>
              <strong>
                {STATUS_LABELS[selectedTrip.status]}
              </strong>
            </div>
          </div>
        )}

        {canManage && (
          <div className="sequence-actions">
            <button
              type="button"
              className="button button-primary"
              disabled={
                !canPreview
                || busy
                || loadingSequence
              }
              onClick={handlePreview}
            >
              {busy
                ? 'Processing...'
                : 'Preview stop sequencing'}
            </button>
          </div>
        )}

        {selectedTrip
          && selectedTrip.status !== 'dispatched'
          && !sequence?.is_applied
          && (
            <p className="sequence-note">
              Only dispatched trips can be optimized.
              Saved results remain viewable later.
            </p>
          )}

        {!canManage && (
          <p className="sequence-note">
            Admin accounts can view applied
            sequences. Dispatcher accounts
            can preview and apply them.
          </p>
        )}
      </section>

      {loadingSequence && (
        <div className="fleet-panel">
          Loading saved sequence...
        </div>
      )}

      {sequence && (
        <StopSequencePanel
          sequence={sequence}
          canManage={canManage}
          applying={busy}
          onApply={handleApply}
        />
      )}
    </section>
  )
}

export default StopSequencingPage