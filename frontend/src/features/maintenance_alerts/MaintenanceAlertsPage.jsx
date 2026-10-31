import { useEffect, useState } from 'react'

import { useAuth } from '../../context/auth'

import MaintenanceAlertCard from './MaintenanceAlertCard'

import {
  getMaintenanceList,
  getMaintenance,
  getMaintenanceHistory,
  addVehicleDistance,
  changeServiceInterval,
  completeVehicleService,
} from './maintenanceAlertsApi'


const PAGE_SIZE = 10

const EVENT_LABELS = {
  distance_added: 'Distance recorded',
  interval_changed: 'Service interval changed',
  service_completed: 'Service completed',
}

const ACTION_LABELS = {
  distance: 'Record simulated distance',
  interval: 'Change service interval',
  service: 'Complete vehicle service',
}


function formatDate(value) {
  if (!value) return '—'

  return new Date(value).toLocaleString()
}


function MaintenanceAlertsPage() {
  const { user } = useAuth()

  const canManage = (
    user?.role === 'admin'
    || user?.role === 'dispatcher'
  )

  const [vehicles, setVehicles] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [onlyAttention, setOnlyAttention] = useState(false)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [selectedVehicle, setSelectedVehicle] = useState(null)
  const [history, setHistory] = useState([])
  const [action, setAction] = useState(null)

  const [distance, setDistance] = useState('')
  const [interval, setIntervalValue] = useState('')
  const [notes, setNotes] = useState('')

  const [reloadKey, setReloadKey] = useState(0)


  useEffect(() => {
    if (!canManage) return

    const controller = new AbortController()

    async function loadMaintenance() {
      setLoading(true)
      setError('')

      try {
        const data = await getMaintenanceList(
          {
            search: search || undefined,
            only_attention: onlyAttention,
            page,
            page_size: PAGE_SIZE,
          },
          controller.signal
        )

        if (!controller.signal.aborted) {
          setVehicles(data.items)
          setTotal(data.total)
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err.response?.status === 403
              ? 'You do not have permission to manage maintenance.'
              : 'Unable to load maintenance records.'
          )
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadMaintenance()

    return () => controller.abort()
  }, [
    canManage,
    search,
    onlyAttention,
    page,
    reloadKey,
  ])


  function handleSearch(event) {
    event.preventDefault()
    setPage(1)
    setSearch(searchInput.trim())
  }


  function refresh() {
    setReloadKey((previous) => previous + 1)
  }


  async function handleView(vehicleId) {
    setError('')
    setAction(null)
    setSelectedVehicle(null)
    setHistory([])

    try {
      const [vehicle, records] = await Promise.all([
        getMaintenance(vehicleId),
        getMaintenanceHistory(vehicleId),
      ])

      setSelectedVehicle(vehicle)
      setHistory(records.items)
    } catch {
      setError('Unable to load maintenance details.')
    }
  }


  function handleAction(type, vehicle) {
    setAction({ type, vehicle })
    setSelectedVehicle(null)
    setHistory([])

    setDistance('')
    setIntervalValue(String(vehicle.service_interval_km))
    setNotes('')

    setError('')
    setSuccess('')
  }


  function handleCancelAction() {
    setAction(null)
  }


  function getErrorMessage(err) {
    const detail = err.response?.data?.detail

    if (typeof detail === 'string') {
      return detail
    }

    if (err.response?.status === 403) {
      return 'You are not authorized to perform this action.'
    }

    if (err.response?.status === 422) {
      return 'Please check the entered values.'
    }

    return 'Unable to update vehicle maintenance.'
  }


  async function handleSubmit(event) {
    event.preventDefault()

    if (!action) return

    setError('')
    setSuccess('')

    const vehicleId = action.vehicle.id
    const cleanNotes = notes.trim()

    let payload

    if (action.type === 'distance') {
      const value = Number(distance)

      if (
        !Number.isFinite(value)
        || value <= 0
        || value > 10000
      ) {
        setError('Enter a distance between 0 and 10,000 km.')
        return
      }

      payload = {
        distance_km: value,
        notes: cleanNotes || null,
      }
    } else if (action.type === 'interval') {
      const value = Number(interval)

      if (
        !Number.isFinite(value)
        || value <= 0
        || value > 100000
      ) {
        setError(
          'Enter a service interval between 0 and 100,000 km.'
        )
        return
      }

      payload = {
        service_interval_km: value,
        notes: cleanNotes || null,
      }
    } else {
      if (cleanNotes.length < 3) {
        setError('Provide a service note of at least 3 characters.')
        return
      }

      payload = {
        notes: cleanNotes,
      }
    }

    setSaving(true)

    try {
      let updated

      if (action.type === 'distance') {
        updated = await addVehicleDistance(
          vehicleId,
          payload
        )
      } else if (action.type === 'interval') {
        updated = await changeServiceInterval(
          vehicleId,
          payload
        )
      } else {
        updated = await completeVehicleService(
          vehicleId,
          payload
        )
      }

      setSelectedVehicle(updated)
      setAction(null)

      try {
        const records = await getMaintenanceHistory(vehicleId)
        setHistory(records.items)
      } catch {
        setHistory([])
      }

      setSuccess(
        updated.maintenance_due
          ? 'Maintenance required. The vehicle is blocked from dispatch.'
          : 'Maintenance information updated successfully.'
      )

      refresh()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
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
          Maintenance Alerts is available only to
          Admin and Dispatcher accounts.
        </p>
      </section>
    )
  }


  return (
    <section className="maintenance-page">
      <div className="maintenance-header">
        <div>
          <p className="workspace-eyebrow">
            VEHICLE MAINTENANCE
          </p>

          <h1 className="workspace-heading">
            Maintenance Alerts
          </h1>

          <p className="workspace-description">
            Monitor simulated mileage, schedule service,
            and keep unsafe vehicles off delivery trips.
          </p>
        </div>
      </div>

      {success && (
        <p className="notice notice-success" role="status">
          {success}
        </p>
      )}

      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}

      {action && (
        <section className="fleet-panel">
          <div className="fleet-panel-header">
            <div>
              <h2>{ACTION_LABELS[action.type]}</h2>

              <p>
                Vehicle: {action.vehicle.registration_number}
              </p>
            </div>
          </div>

          <form
            className="fleet-form"
            onSubmit={handleSubmit}
          >
            {action.type === 'distance' && (
              <label className="field">
                Simulated distance travelled (km)

                <input
                  className="form-input"
                  type="number"
                  min="0.001"
                  max="10000"
                  step="any"
                  value={distance}
                  onChange={(event) => {
                    setDistance(event.target.value)
                  }}
                  placeholder="e.g. 250"
                  required
                />
              </label>
            )}

            {action.type === 'interval' && (
              <label className="field">
                Service interval (km)

                <input
                  className="form-input"
                  type="number"
                  min="0.001"
                  max="100000"
                  step="any"
                  value={interval}
                  onChange={(event) => {
                    setIntervalValue(event.target.value)
                  }}
                  required
                />
              </label>
            )}

            <label className="field">
              {action.type === 'service'
                ? 'Service completion notes'
                : 'Notes (optional)'}

              <textarea
                className="form-input maintenance-notes"
                value={notes}
                onChange={(event) => {
                  setNotes(event.target.value)
                }}
                maxLength={500}
                placeholder={
                  action.type === 'service'
                    ? 'Describe the completed maintenance work'
                    : 'Additional information'
                }
                required={action.type === 'service'}
              />
            </label>

            {action.type === 'service' && (
              <p className="maintenance-form-hint">
                Completing service resets the service mileage
                baseline. An inactive vehicle remains inactive.
              </p>
            )}

            <div className="fleet-form-actions">
              <button
                type="button"
                className="button button-outline"
                onClick={handleCancelAction}
                disabled={saving}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="button button-primary"
                disabled={saving}
              >
                {saving
                  ? 'Saving...'
                  : action.type === 'service'
                    ? 'Confirm service completed'
                    : 'Save changes'}
              </button>
            </div>
          </form>
        </section>
      )}

      <section className="fleet-panel">
        <div className="fleet-panel-header">
          <div>
            <h2>Vehicle service monitoring</h2>

            <p>
              {total} matching vehicle{total === 1 ? '' : 's'}
            </p>
          </div>
        </div>

        <div className="maintenance-toolbar">
          <form
            className="fleet-search"
            onSubmit={handleSearch}
          >
            <input
              className="form-input"
              type="search"
              aria-label="Search vehicles for maintenance"
              placeholder="Search registration or vehicle type..."
              value={searchInput}
              onChange={(event) => {
                setSearchInput(event.target.value)
              }}
            />

            <button
              className="button button-outline"
              type="submit"
            >
              Search
            </button>
          </form>

          <label className="maintenance-filter-label">
            <input
              type="checkbox"
              checked={onlyAttention}
              onChange={(event) => {
                setOnlyAttention(event.target.checked)
                setPage(1)
              }}
            />

            Needs attention only
          </label>
        </div>

        <div className="fleet-table-container">
          <table className="fleet-table maintenance-table">
            <thead>
              <tr>
                <th>Registration</th>
                <th>Vehicle type</th>
                <th>Odometer (km)</th>
                <th>Since service (km)</th>
                <th>Interval (km)</th>
                <th>Service state</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="fleet-empty">
                    Loading maintenance records...
                  </td>
                </tr>
              ) : vehicles.length === 0 ? (
                <tr>
                  <td colSpan={7} className="fleet-empty">
                    No matching vehicles found.
                  </td>
                </tr>
              ) : (
                vehicles.map((vehicle) => (
                  <tr key={vehicle.id}>
                    <td>
                      <strong>
                        {vehicle.registration_number}
                      </strong>
                    </td>

                    <td>{vehicle.vehicle_type}</td>

                    <td>
                      {vehicle.odometer_km.toLocaleString()}
                    </td>

                    <td>
                      {vehicle.kilometers_since_service.toLocaleString()}
                    </td>

                    <td>
                      {vehicle.service_interval_km.toLocaleString()}
                    </td>

                    <td>
                      <span
                        className={
                          vehicle.needs_attention
                            ? 'maintenance-state is-due'
                            : 'maintenance-state is-normal'
                        }
                      >
                        {vehicle.maintenance_due
                          ? 'Service due'
                          : vehicle.status === 'maintenance'
                            ? 'Under maintenance'
                            : 'Monitored'}
                      </span>
                    </td>

                    <td>
                      <div className="fleet-actions maintenance-actions">
                        <button
                          type="button"
                          onClick={() => handleView(vehicle.id)}
                        >
                          View
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            handleAction('distance', vehicle)
                          }}
                        >
                          + km
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            handleAction('service', vehicle)
                          }}
                          disabled={vehicle.status === 'in_use'}
                        >
                          Service
                        </button>
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
      </section>

      {selectedVehicle && (
        <>
          <MaintenanceAlertCard
            vehicle={selectedVehicle}
            onAction={handleAction}
            onClose={() => {
              setSelectedVehicle(null)
              setHistory([])
            }}
          />

          <section className="fleet-panel">
            <div className="fleet-panel-header">
              <div>
                <h2>Maintenance history</h2>

                <p>
                  Latest 20 recorded actions for
                  {' '}
                  {selectedVehicle.registration_number}
                </p>
              </div>
            </div>

            <div className="fleet-table-container">
              <table className="fleet-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Action</th>
                    <th>Distance (km)</th>
                    <th>Odometer (km)</th>
                    <th>Notes</th>
                  </tr>
                </thead>

                <tbody>
                  {history.length === 0 ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="fleet-empty"
                      >
                        No maintenance history recorded.
                      </td>
                    </tr>
                  ) : (
                    history.map((record) => (
                      <tr key={record.id}>
                        <td>
                          {formatDate(record.created_at)}
                        </td>

                        <td>
                          {EVENT_LABELS[record.event_type]
                            || record.event_type}

                          {record.maintenance_triggered && (
                            <span className="maintenance-trigger-text">
                              Service threshold reached
                            </span>
                          )}
                        </td>

                        <td>{record.distance_km}</td>

                        <td>{record.odometer_km}</td>

                        <td>{record.notes || '—'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </section>
  )
}

export default MaintenanceAlertsPage