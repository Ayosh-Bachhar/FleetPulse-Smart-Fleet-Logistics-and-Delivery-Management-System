import { useEffect, useState } from 'react'

import { useAuth } from '../../context/auth'

import { getVehicles } from '../fleet_management/fleetManagementApi'
import { getDrivers } from '../driver_management/driverManagementApi'
import { getShifts } from '../shift_roster/shiftRosterApi'

import DispatchPlanner from './DispatchPlanner'

import {
  getTrips,
  getTrip,
  getEligibleOrders,
  completeTrip,
  cancelTrip,
} from './dispatchPlanningApi'


const PAGE_SIZE = 10

const STATUS_LABELS = {
  dispatched: 'Dispatched',
  completed: 'Completed',
  cancelled: 'Cancelled',
}


function formatDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}


function DispatchPlanningPage() {
  const { user } = useAuth()

  const canView = (
    user?.role === 'admin'
    || user?.role === 'dispatcher'
  )

  const canDispatch = user?.role === 'dispatcher'

  const [trips, setTrips] = useState([])
  const [shifts, setShifts] = useState([])
  const [drivers, setDrivers] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [orders, setOrders] = useState([])

  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')

  const [loading, setLoading] = useState(true)
  const [resourcesLoading, setResourcesLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const [showPlanner, setShowPlanner] = useState(false)
  const [selectedTrip, setSelectedTrip] = useState(null)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [reloadKey, setReloadKey] = useState(0)


  useEffect(() => {
    if (!canView) return

    const controller = new AbortController()

    async function loadResources() {
      setResourcesLoading(true)

      try {
        const [
          shiftData,
          driverData,
          vehicleData,
          orderData,
        ] = await Promise.all([
          getShifts(
            {
              status: 'scheduled',
              page_size: 100,
            },
            controller.signal
          ),
          getDrivers(
            { page_size: 100 },
            controller.signal
          ),
          getVehicles(
            { page_size: 100 },
            controller.signal
          ),
          getEligibleOrders(
            { page_size: 100 },
            controller.signal
          ),
        ])

        if (!controller.signal.aborted) {
          setShifts(shiftData.items)
          setDrivers(driverData.items)
          setVehicles(vehicleData.items)
          setOrders(orderData.items)
        }
      } catch {
        if (!controller.signal.aborted) {
          setError(
            'Unable to load shifts, drivers, vehicles, or orders.'
          )
        }
      } finally {
        if (!controller.signal.aborted) {
          setResourcesLoading(false)
        }
      }
    }

    loadResources()

    return () => controller.abort()
  }, [canView, reloadKey])


  useEffect(() => {
    if (!canView) return

    const controller = new AbortController()

    async function loadTrips() {
      setLoading(true)

      try {
        const data = await getTrips(
          {
            status: statusFilter || undefined,
            page,
            page_size: PAGE_SIZE,
          },
          controller.signal
        )

        if (!controller.signal.aborted) {
          setTrips(data.items)
          setTotal(data.total)
        }
      } catch {
        if (!controller.signal.aborted) {
          setError('Unable to load dispatched trips.')
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadTrips()

    return () => controller.abort()
  }, [
    canView,
    statusFilter,
    page,
    reloadKey,
  ])


  function refresh() {
    setReloadKey((previous) => previous + 1)
  }


  function handleDispatched(trip) {
    setShowPlanner(false)
    setSelectedTrip(trip)

    setSuccess('Trip dispatched successfully.')
    setError('')

    refresh()
  }


  async function handleView(tripId) {
    setError('')

    try {
      const trip = await getTrip(tripId)

      setSelectedTrip(trip)
      setShowPlanner(false)
    } catch {
      setError('Unable to load trip details.')
    }
  }


  async function handleTripAction(trip, action) {
    if (!canDispatch || busy) return

    const message = action === 'complete'
      ? 'Mark this trip as operationally completed?'
      : 'Cancel this trip and release its warehouse orders?'

    if (!window.confirm(message)) {
      return
    }

    setBusy(true)
    setError('')
    setSuccess('')

    try {
      const updated = action === 'complete'
        ? await completeTrip(trip.id)
        : await cancelTrip(trip.id)

      setSelectedTrip(updated)

      setSuccess(
        action === 'complete'
          ? 'Trip completed. Its fuel and mileage can be recorded in F5.'
          : 'Trip cancelled and orders released.'
      )

      refresh()
    } catch (err) {
      const detail = err.response?.data?.detail

      setError(
        typeof detail === 'string'
          ? detail
          : 'Unable to update the trip.'
      )
    } finally {
      setBusy(false)
    }
  }


  const totalPages = Math.max(
    1,
    Math.ceil(total / PAGE_SIZE)
  )


  if (!canView) {
    return (
      <section className="workspace-welcome">
        <h1 className="workspace-heading">
          Access restricted
        </h1>

        <p className="workspace-description">
          Dispatch Planning is available only to
          Dispatcher and Admin accounts.
        </p>
      </section>
    )
  }


  return (
    <section className="dispatch-page">
      <div className="fleet-header">
        <div>
          <p className="workspace-eyebrow">
            DELIVERY OPERATIONS
          </p>

          <h1 className="workspace-heading">
            Dispatch Planning
          </h1>

          <p className="workspace-description">
            Group orders into trips with validated drivers,
            vehicles, shifts, and cargo capacities.
          </p>
        </div>

        {canDispatch && (
          <button
            type="button"
            className="button button-primary"
            onClick={() => {
              setShowPlanner(true)
              setSelectedTrip(null)
              setError('')
              setSuccess('')
            }}
          >
            + Create dispatch
          </button>
        )}
      </div>

      {!canDispatch && (
        <div className="dispatch-info">
          Admin accounts can view trips.
          A Dispatcher account is required to create,
          complete, or cancel them.
        </div>
      )}

      {success && (
        <p
          className="notice notice-success"
          role="status"
        >
          {success}
        </p>
      )}

      {error && (
        <p
          className="notice notice-error"
          role="alert"
        >
          {error}
        </p>
      )}

      {showPlanner && canDispatch && (
        resourcesLoading ? (
          <div className="fleet-panel">
            Loading dispatch resources...
          </div>
        ) : (
          <DispatchPlanner
            shifts={shifts}
            drivers={drivers}
            vehicles={vehicles}
            orders={orders}
            onDispatched={handleDispatched}
            onCancel={() => setShowPlanner(false)}
          />
        )
      )}

      <div className="fleet-panel">
        <div className="fleet-panel-header">
          <div>
            <h2>Trip records</h2>

            <p>
              {total} matching trip{total === 1 ? '' : 's'}
            </p>
          </div>
        </div>

        <div className="dispatch-toolbar">
          <select
            className="form-input"
            aria-label="Filter trip status"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value)
              setPage(1)
            }}
          >
            <option value="">All statuses</option>
            <option value="dispatched">Dispatched</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <div className="fleet-table-container">
          <table className="fleet-table dispatch-table">
            <thead>
              <tr>
                <th>Trip</th>
                <th>Driver</th>
                <th>Vehicle</th>
                <th>Orders</th>
                <th>Weight</th>
                <th>Volume</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td
                    colSpan={8}
                    className="fleet-empty"
                  >
                    Loading trips...
                  </td>
                </tr>
              ) : trips.length === 0 ? (
                <tr>
                  <td
                    colSpan={8}
                    className="fleet-empty"
                  >
                    No trips found.
                  </td>
                </tr>
              ) : (
                trips.map((trip) => (
                  <tr key={trip.id}>
                    <td>
                      <strong>
                        {trip.id.slice(-8).toUpperCase()}
                      </strong>
                    </td>

                    <td>{trip.driver_name}</td>

                    <td>
                      {trip.vehicle_registration}
                    </td>

                    <td>{trip.order_count}</td>

                    <td>
                      {trip.total_weight_kg} kg
                    </td>

                    <td>
                      {trip.total_volume_m3} m³
                    </td>

                    <td>
                      <span
                        className={
                          `fleet-status dispatch-status-${trip.status}`
                        }
                      >
                        {STATUS_LABELS[trip.status]}
                      </span>
                    </td>

                    <td>
                      <div className="fleet-actions dispatch-actions">
                        <button
                          type="button"
                          onClick={() => handleView(trip.id)}
                        >
                          View
                        </button>

                        {canDispatch
                          && trip.status === 'dispatched'
                          && (
                            <>
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => {
                                  handleTripAction(
                                    trip,
                                    'complete'
                                  )
                                }}
                              >
                                Complete
                              </button>

                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => {
                                  handleTripAction(
                                    trip,
                                    'cancel'
                                  )
                                }}
                              >
                                Cancel
                              </button>
                            </>
                          )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="fleet-pagination">
          <span>
            Page {page} of {totalPages}
          </span>

          <div className="fleet-pagination-buttons">
            <button
              className="button button-outline"
              type="button"
              disabled={loading || page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>

            <button
              className="button button-outline"
              type="button"
              disabled={loading || page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {selectedTrip && (
        <section className="fleet-panel">
          <div className="fleet-panel-header">
            <div>
              <h2>Trip details</h2>

              <p>
                Trip {selectedTrip.id.slice(-8).toUpperCase()}
              </p>
            </div>

            <button
              type="button"
              className="button button-outline"
              onClick={() => setSelectedTrip(null)}
            >
              Close
            </button>
          </div>

          <div className="fleet-details">
            <div>
              <span>Driver</span>
              <strong>{selectedTrip.driver_name}</strong>
            </div>

            <div>
              <span>Vehicle</span>
              <strong>
                {selectedTrip.vehicle_registration}
              </strong>
            </div>

            <div>
              <span>Vehicle type</span>
              <strong>{selectedTrip.vehicle_type}</strong>
            </div>

            <div>
              <span>Trip status</span>
              <strong>
                {STATUS_LABELS[selectedTrip.status]}
              </strong>
            </div>

            <div>
              <span>Start time</span>
              <strong>
                {formatDateTime(selectedTrip.start_at)}
              </strong>
            </div>

            <div>
              <span>End time</span>
              <strong>
                {formatDateTime(selectedTrip.end_at)}
              </strong>
            </div>

            <div>
              <span>Weight</span>
              <strong>
                {selectedTrip.total_weight_kg} kg
              </strong>
            </div>

            <div>
              <span>Volume</span>
              <strong>
                {selectedTrip.total_volume_m3} m³
              </strong>
            </div>

            <div>
              <span>Actual trip distance</span>
              <strong>
                {selectedTrip.actual_distance_km == null
                  ? 'Not yet recorded'
                  : `${selectedTrip.actual_distance_km} km`}
              </strong>
            </div>

            <div>
              <span>Completed at</span>
              <strong>
                {formatDateTime(selectedTrip.completed_at)}
              </strong>
            </div>
          </div>

          <div className="dispatch-trip-orders">
            <h3>Assigned orders</h3>

            {selectedTrip.order_references.map((code) => (
              <span
                key={code}
                className="dispatch-order-chip"
              >
                {code}
              </span>
            ))}
          </div>
        </section>
      )}
    </section>
  )
}

export default DispatchPlanningPage