import { useEffect, useState } from 'react'

import { useAuth } from '../../context/auth'

import { getDrivers } from '../driver_management/driverManagementApi'
import { getVehicles } from '../fleet_management/fleetManagementApi'

import ShiftForm from './ShiftForm'

import {
  getShifts,
  getShift,
  updateShift,
} from './shiftRosterApi'


const PAGE_SIZE = 10

const STATUS_LABELS = {
  scheduled: 'Scheduled',
  completed: 'Completed',
  cancelled: 'Cancelled',
}


function formatDateTime(value) {
  if (!value) return '—'

  return new Date(value).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}


function ShiftRosterPage() {
  const { user } = useAuth()

  const canManage = (
    user?.role === 'admin'
    || user?.role === 'dispatcher'
  )

  const [shifts, setShifts] = useState([])
  const [drivers, setDrivers] = useState([])
  const [vehicles, setVehicles] = useState([])

  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const [statusFilter, setStatusFilter] = useState('')
  const [driverFilter, setDriverFilter] = useState('')
  const [vehicleFilter, setVehicleFilter] = useState('')

  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [warning, setWarning] = useState('')

  const [creating, setCreating] = useState(false)
  const [editingShift, setEditingShift] = useState(null)
  const [selectedShift, setSelectedShift] = useState(null)

  const [reloadKey, setReloadKey] = useState(0)


  useEffect(() => {
    if (!canManage) return

    const controller = new AbortController()

    async function loadResources() {
      try {
        const [driverData, vehicleData] = await Promise.all([
          getDrivers(
            { page_size: 100 },
            controller.signal
          ),
          getVehicles(
            { page_size: 100 },
            controller.signal
          ),
        ])

        if (!controller.signal.aborted) {
          setDrivers(driverData.items)
          setVehicles(vehicleData.items)
        }
      } catch {
        if (!controller.signal.aborted) {
          setError(
            'Unable to load drivers or vehicles.'
          )
        }
      }
    }

    loadResources()

    return () => controller.abort()
  }, [canManage, reloadKey])


  useEffect(() => {
    if (!canManage) return

    const controller = new AbortController()

    async function loadShifts() {
      setLoading(true)
      setError('')

      try {
        const data = await getShifts(
          {
            status: statusFilter || undefined,
            driver_id: driverFilter || undefined,
            vehicle_id: vehicleFilter || undefined,
            page,
            page_size: PAGE_SIZE,
          },
          controller.signal
        )

        if (!controller.signal.aborted) {
          setShifts(data.items)
          setTotal(data.total)
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err.response?.status === 403
              ? 'You are not authorized to view shifts.'
              : 'Unable to load shift records.'
          )
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadShifts()

    return () => controller.abort()
  }, [
    canManage,
    statusFilter,
    driverFilter,
    vehicleFilter,
    page,
    reloadKey,
  ])


  function handleAdd() {
    setCreating(true)
    setEditingShift(null)
    setSelectedShift(null)

    setError('')
    setSuccess('')
    setWarning('')
  }


  function handleEdit(shift) {
    if (shift.status !== 'scheduled') return

    setCreating(false)
    setEditingShift(shift)
    setSelectedShift(null)

    setError('')
    setSuccess('')
    setWarning('')
  }


  function handleCancelForm() {
    setCreating(false)
    setEditingShift(null)
  }


  function handleSaved(shift) {
    setCreating(false)
    setEditingShift(null)

    setSuccess('Shift saved successfully.')
    setWarning(shift.holiday_notice || '')

    setSelectedShift(shift)

    setReloadKey((previous) => previous + 1)
  }


  async function handleView(shiftId) {
    setError('')

    try {
      const shift = await getShift(shiftId)

      setSelectedShift(shift)
      setCreating(false)
      setEditingShift(null)
    } catch {
      setError('Unable to load shift details.')
    }
  }


  async function handleStatusChange(shift, newStatus) {
    if (shift.status !== 'scheduled') return

    const action = (
      newStatus === 'completed'
        ? 'complete'
        : 'cancel'
    )

    const confirmed = window.confirm(
      `Are you sure you want to ${action} this shift?`
    )

    if (!confirmed) return

    setBusy(true)
    setError('')
    setSuccess('')
    setWarning('')

    try {
      const updated = await updateShift(
        shift.id,
        { status: newStatus }
      )

      setSuccess(
        `Shift marked as ${newStatus}.`
      )

      setSelectedShift(updated)
      setCreating(false)
      setEditingShift(null)

      setReloadKey((previous) => previous + 1)
    } catch (err) {
      const detail = err.response?.data?.detail

      setError(
        typeof detail === 'string'
          ? detail
          : 'Unable to update shift status.'
      )
    } finally {
      setBusy(false)
    }
  }


  const totalPages = Math.max(
    1,
    Math.ceil(total / PAGE_SIZE)
  )


  if (!canManage) {
    return (
      <section className="workspace-welcome">
        <h1 className="workspace-heading">
          Access restricted
        </h1>

        <p className="workspace-description">
          Shift Roster is available only to
          Admin and Dispatcher accounts.
        </p>
      </section>
    )
  }


  return (
    <section className="shift-page">
      <div className="shift-header">
        <div>
          <p className="workspace-eyebrow">
            WORKFORCE SCHEDULING
          </p>

          <h1 className="workspace-heading">
            Shift Roster
          </h1>

          <p className="workspace-description">
            Schedule qualified drivers and available
            vehicles without overlapping assignments.
          </p>
        </div>

        <button
          className="button button-primary"
          type="button"
          onClick={handleAdd}
        >
          + Schedule shift
        </button>
      </div>

      {success && (
        <p
          className="notice notice-success"
          role="status"
        >
          {success}
        </p>
      )}

      {warning && (
        <div
          className="shift-holiday-info"
          role="status"
        >
          {warning}
        </div>
      )}

      {error && (
        <p
          className="notice notice-error"
          role="alert"
        >
          {error}
        </p>
      )}

      {(creating || editingShift) && (
        <ShiftForm
          key={editingShift?.id || 'new'}
          shift={editingShift}
          drivers={drivers}
          vehicles={vehicles}
          onSaved={handleSaved}
          onCancel={handleCancelForm}
        />
      )}

      <div className="fleet-panel">
        <div className="fleet-panel-header">
          <div>
            <h2>Scheduled shifts</h2>

            <p>
              {total} matching shift{total === 1 ? '' : 's'}
            </p>
          </div>
        </div>

        <div className="shift-toolbar">
          <select
            className="form-input shift-filter"
            aria-label="Filter shift status"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value)
              setPage(1)
            }}
          >
            <option value="">All statuses</option>
            <option value="scheduled">Scheduled</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>

          <select
            className="form-input shift-filter"
            aria-label="Filter by driver"
            value={driverFilter}
            onChange={(event) => {
              setDriverFilter(event.target.value)
              setPage(1)
            }}
          >
            <option value="">All drivers</option>

            {drivers.map((driver) => (
              <option
                key={driver.id}
                value={driver.id}
              >
                {driver.full_name}
              </option>
            ))}
          </select>

          <select
            className="form-input shift-filter"
            aria-label="Filter by vehicle"
            value={vehicleFilter}
            onChange={(event) => {
              setVehicleFilter(event.target.value)
              setPage(1)
            }}
          >
            <option value="">All vehicles</option>

            {vehicles.map((vehicle) => (
              <option
                key={vehicle.id}
                value={vehicle.id}
              >
                {vehicle.registration_number}
              </option>
            ))}
          </select>
        </div>

        <div className="fleet-table-container">
          <table className="fleet-table shift-table">
            <thead>
              <tr>
                <th>Driver</th>
                <th>Vehicle</th>
                <th>Start</th>
                <th>End</th>
                <th>Status</th>
                <th>Holiday</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td
                    colSpan={7}
                    className="fleet-empty"
                  >
                    Loading shifts...
                  </td>
                </tr>
              ) : shifts.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="fleet-empty"
                  >
                    No shifts found.
                  </td>
                </tr>
              ) : (
                shifts.map((shift) => (
                  <tr key={shift.id}>
                    <td>
                      <strong>
                        {shift.driver_name}
                      </strong>
                    </td>

                    <td>
                      {shift.vehicle_registration}
                    </td>

                    <td>
                      {formatDateTime(shift.start_at)}
                    </td>

                    <td>
                      {formatDateTime(shift.end_at)}
                    </td>

                    <td>
                      <span
                        className={
                          `fleet-status shift-status-${shift.status}`
                        }
                      >
                        {STATUS_LABELS[shift.status]}
                      </span>
                    </td>

                    <td>
                      {shift.holiday_names.length > 0 ? (
                        <span className="shift-holiday-label">
                          Holiday warning
                        </span>
                      ) : (
                        <span className="shift-holiday-none">
                          {[
                            'sample',
                            'mixed',
                            'unavailable',
                            'stale-cache',
                          ].includes(shift.holiday_source)
                            ? 'Limited data'
                            : 'None'}
                        </span>
                      )}
                    </td>

                    <td>
                      <div className="fleet-actions shift-actions">
                        <button
                          type="button"
                          onClick={() => handleView(shift.id)}
                        >
                          View
                        </button>

                        {shift.status === 'scheduled' && (
                          <>
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => handleEdit(shift)}
                            >
                              Edit
                            </button>

                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => {
                                handleStatusChange(
                                  shift,
                                  'completed'
                                )
                              }}
                            >
                              Complete
                            </button>

                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => {
                                handleStatusChange(
                                  shift,
                                  'cancelled'
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
              onClick={() => {
                setPage((previous) => previous - 1)
              }}
            >
              Previous
            </button>

            <button
              className="button button-outline"
              type="button"
              disabled={loading || page >= totalPages}
              onClick={() => {
                setPage((previous) => previous + 1)
              }}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {selectedShift && (
        <div className="fleet-panel">
          <div className="fleet-panel-header">
            <div>
              <h2>Shift details</h2>

              <p>
                {selectedShift.driver_name}
                {' — '}
                {selectedShift.vehicle_registration}
              </p>
            </div>

            <button
              className="button button-outline"
              type="button"
              onClick={() => setSelectedShift(null)}
            >
              Close
            </button>
          </div>

          <div className="fleet-details">
            <div>
              <span>Driver</span>
              <strong>
                {selectedShift.driver_name}
              </strong>
            </div>

            <div>
              <span>Vehicle</span>
              <strong>
                {selectedShift.vehicle_registration}
              </strong>
            </div>

            <div>
              <span>Vehicle type</span>
              <strong>
                {selectedShift.vehicle_type}
              </strong>
            </div>

            <div>
              <span>Shift status</span>
              <strong>
                {STATUS_LABELS[selectedShift.status]}
              </strong>
            </div>

            <div>
              <span>Start time</span>
              <strong>
                {formatDateTime(selectedShift.start_at)}
              </strong>
            </div>

            <div>
              <span>End time</span>
              <strong>
                {formatDateTime(selectedShift.end_at)}
              </strong>
            </div>

            <div>
              <span>Created at</span>
              <strong>
                {formatDateTime(selectedShift.created_at)}
              </strong>
            </div>

            <div>
              <span>Last updated</span>
              <strong>
                {formatDateTime(selectedShift.updated_at)}
              </strong>
            </div>
          </div>

          <div className="shift-detail-holiday">
            <h3>Public holiday information</h3>

            <p>
              {selectedShift.holiday_notice}
            </p>

            <span>
              Source: {selectedShift.holiday_source}
            </span>
          </div>
        </div>
      )}
    </section>
  )
}

export default ShiftRosterPage