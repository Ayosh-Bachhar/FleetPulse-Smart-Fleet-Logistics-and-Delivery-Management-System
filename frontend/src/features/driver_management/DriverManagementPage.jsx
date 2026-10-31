import { useEffect, useState } from 'react'

import { useAuth } from '../../context/auth'
import { getVehicles } from '../fleet_management/fleetManagementApi'

import DriverForm from './DriverForm'

import {
  getDrivers,
  getDriver,
  checkDriverCompatibility,
} from './driverManagementApi'


const PAGE_SIZE = 10

const STATUS_LABELS = {
  available: 'Available',
  unavailable: 'Unavailable',
  inactive: 'Inactive',
}

const LICENSE_LABELS = {
  light: 'Light',
  medium: 'Medium',
  heavy: 'Heavy',
}


function DriverManagementPage() {
  const { user } = useAuth()

  const canManage = (
    user?.role === 'admin'
    || user?.role === 'dispatcher'
  )

  const [drivers, setDrivers] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [classFilter, setClassFilter] = useState('')

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [creating, setCreating] = useState(false)
  const [editingDriver, setEditingDriver] = useState(null)
  const [selectedDriver, setSelectedDriver] = useState(null)

  const [selectedVehicleId, setSelectedVehicleId] = useState('')
  const [compatibility, setCompatibility] = useState(null)
  const [checking, setChecking] = useState(false)

  const [reloadKey, setReloadKey] = useState(0)


  useEffect(() => {
    if (!canManage) return

    const controller = new AbortController()

    async function loadDrivers() {
      setLoading(true)
      setError('')

      try {
        const data = await getDrivers(
          {
            search: search || undefined,
            status: statusFilter || undefined,
            license_class: classFilter || undefined,
            page,
            page_size: PAGE_SIZE,
          },
          controller.signal
        )

        if (!controller.signal.aborted) {
          setDrivers(data.items)
          setTotal(data.total)
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err.response?.status === 403
              ? 'You are not authorized to view drivers.'
              : 'Unable to load driver records.'
          )
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadDrivers()
    return () => controller.abort()
  }, [
    canManage,
    search,
    statusFilter,
    classFilter,
    page,
    reloadKey,
  ])


  useEffect(() => {
    if (!canManage) return

    const controller = new AbortController()

    async function loadVehicles() {
      try {
        const data = await getVehicles(
          { page_size: 100 },
          controller.signal
        )

        if (!controller.signal.aborted) {
          setVehicles(data.items)
        }
      } catch {
        if (!controller.signal.aborted) {
          setVehicles([])
        }
      }
    }

    loadVehicles()
    return () => controller.abort()
  }, [canManage, reloadKey])


  function handleSearch(event) {
    event.preventDefault()
    setPage(1)
    setSearch(searchInput.trim())
  }


  function handleSaved() {
    setCreating(false)
    setEditingDriver(null)
    setSelectedDriver(null)
    setSuccess('Driver information saved successfully.')
    setReloadKey((previous) => previous + 1)
  }


  function handleAdd() {
    setCreating(true)
    setEditingDriver(null)
    setSelectedDriver(null)
    setCompatibility(null)
    setError('')
    setSuccess('')
  }


  function handleEdit(driver) {
    setEditingDriver(driver)
    setCreating(false)
    setSelectedDriver(null)
    setCompatibility(null)
    setError('')
    setSuccess('')
  }


  async function handleView(driverId) {
    setError('')
    setSelectedDriver(null)
    setCompatibility(null)
    setSelectedVehicleId('')

    try {
      const driver = await getDriver(driverId)

      setSelectedDriver(driver)
      setCreating(false)
      setEditingDriver(null)
    } catch {
      setError('Unable to load driver details.')
    }
  }


  async function handleCompatibility(event) {
    event.preventDefault()

    if (!selectedDriver || !selectedVehicleId) {
      return
    }

    setChecking(true)
    setCompatibility(null)
    setError('')

    try {
      const result = await checkDriverCompatibility(
        selectedDriver.id,
        selectedVehicleId
      )

      setCompatibility(result)
    } catch {
      setError('Unable to check driver and vehicle compatibility.')
    } finally {
      setChecking(false)
    }
  }


  function handleStatusFilter(event) {
    setStatusFilter(event.target.value)
    setPage(1)
  }


  function handleClassFilter(event) {
    setClassFilter(event.target.value)
    setPage(1)
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
          Driver Management is available only
          to Admin and Dispatcher accounts.
        </p>
      </section>
    )
  }


  return (
    <section className="driver-page">
      <div className="driver-header">
        <div>
          <p className="workspace-eyebrow">
            DRIVER OPERATIONS
          </p>

          <h1 className="workspace-heading">
            Driver Management
          </h1>

          <p className="workspace-description">
            Manage drivers, license classes, expiry dates,
            and vehicle eligibility.
          </p>
        </div>

        <button
          className="button button-primary"
          type="button"
          onClick={handleAdd}
        >
          + Add driver
        </button>
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

      {(creating || editingDriver) && (
        <DriverForm
          key={editingDriver?.id || 'new'}
          driver={editingDriver}
          onSaved={handleSaved}
          onCancel={() => {
            setCreating(false)
            setEditingDriver(null)
          }}
        />
      )}

      <div className="fleet-panel">
        <div className="fleet-panel-header">
          <div>
            <h2>Driver records</h2>
            <p>
              {total} matching driver{total === 1 ? '' : 's'}
            </p>
          </div>
        </div>

        <div className="driver-toolbar">
          <form
            className="fleet-search"
            onSubmit={handleSearch}
          >
            <input
              type="search"
              className="form-input"
              aria-label="Search drivers"
              placeholder="Search name, license, or phone..."
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

          <select
            className="form-input driver-filter"
            aria-label="Filter driver status"
            value={statusFilter}
            onChange={handleStatusFilter}
          >
            <option value="">All statuses</option>
            <option value="available">Available</option>
            <option value="unavailable">Unavailable</option>
            <option value="inactive">Inactive</option>
          </select>

          <select
            className="form-input driver-filter"
            aria-label="Filter license class"
            value={classFilter}
            onChange={handleClassFilter}
          >
            <option value="">All licenses</option>
            <option value="light">Light</option>
            <option value="medium">Medium</option>
            <option value="heavy">Heavy</option>
          </select>
        </div>

        <div className="fleet-table-container">
          <table className="fleet-table">
            <thead>
              <tr>
                <th>Driver</th>
                <th>License</th>
                <th>Class</th>
                <th>Expiry</th>
                <th>Status</th>
                <th>Eligibility</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="fleet-empty">
                    Loading drivers...
                  </td>
                </tr>
              ) : drivers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="fleet-empty">
                    No drivers found.
                  </td>
                </tr>
              ) : (
                drivers.map((driver) => (
                  <tr key={driver.id}>
                    <td>
                      <strong>{driver.full_name}</strong>
                    </td>

                    <td>{driver.license_number}</td>

                    <td>
                      {LICENSE_LABELS[driver.license_class]}
                    </td>

                    <td>{driver.license_expiry}</td>

                    <td>
                      <span
                        className={
                          `fleet-status driver-status-${driver.status}`
                        }
                      >
                        {STATUS_LABELS[driver.status]}
                      </span>
                    </td>

                    <td>
                      <span
                        className={
                          driver.is_available
                            ? 'driver-eligible'
                            : 'driver-ineligible'
                        }
                      >
                        {driver.is_available
                          ? 'Eligible'
                          : driver.license_valid
                            ? 'Unavailable'
                            : 'Expired license'}
                      </span>
                    </td>

                    <td>
                      <div className="fleet-actions">
                        <button
                          type="button"
                          onClick={() => handleView(driver.id)}
                        >
                          View
                        </button>

                        <button
                          type="button"
                          onClick={() => handleEdit(driver)}
                        >
                          Edit
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
      </div>

      {selectedDriver && (
        <div className="fleet-panel">
          <div className="fleet-panel-header">
            <div>
              <h2>Driver details</h2>
              <p>{selectedDriver.full_name}</p>
            </div>

            <button
              className="button button-outline"
              type="button"
              onClick={() => setSelectedDriver(null)}
            >
              Close
            </button>
          </div>

          <div className="fleet-details">
            <div>
              <span>Full name</span>
              <strong>{selectedDriver.full_name}</strong>
            </div>

            <div>
              <span>Phone number</span>
              <strong>{selectedDriver.phone || 'Not set'}</strong>
            </div>

            <div>
              <span>License number</span>
              <strong>{selectedDriver.license_number}</strong>
            </div>

            <div>
              <span>License class</span>
              <strong>
                {LICENSE_LABELS[selectedDriver.license_class]}
              </strong>
            </div>

            <div>
              <span>License expiry</span>
              <strong>{selectedDriver.license_expiry}</strong>
            </div>

            <div>
              <span>License validity</span>
              <strong>
                {selectedDriver.license_valid
                  ? 'Valid'
                  : 'Expired'}
              </strong>
            </div>

            <div>
              <span>Driver status</span>
              <strong>
                {STATUS_LABELS[selectedDriver.status]}
              </strong>
            </div>

            <div>
              <span>Linked user</span>
              <strong>
                {selectedDriver.linked_user_email || 'Not linked'}
              </strong>
            </div>

            <div className="driver-form-full">
              <span>Permitted vehicle types</span>
              <strong>
                {selectedDriver.allowed_vehicle_types.join(', ')}
              </strong>
            </div>
          </div>

          <div className="driver-compatibility">
            <h3>Vehicle compatibility check</h3>

            <p>
              Select a vehicle from Fleet Management to check
              license class, expiry, and availability.
            </p>

            <form
              className="driver-check-form"
              onSubmit={handleCompatibility}
            >
              <select
                className="form-input"
                aria-label="Select a vehicle"
                value={selectedVehicleId}
                onChange={(event) => {
                  setSelectedVehicleId(event.target.value)
                  setCompatibility(null)
                }}
                required
              >
                <option value="">Select vehicle</option>

                {vehicles.map((vehicle) => (
                  <option
                    key={vehicle.id}
                    value={vehicle.id}
                  >
                    {vehicle.registration_number}
                    {' — '}
                    {vehicle.vehicle_type}
                    {' ('}
                    {vehicle.status}
                    {')'}
                  </option>
                ))}
              </select>

              <button
                className="button button-primary"
                type="submit"
                disabled={checking || !selectedVehicleId}
              >
                {checking
                  ? 'Checking...'
                  : 'Check compatibility'}
              </button>
            </form>

            {vehicles.length === 0 && (
              <p className="driver-field-hint">
                No vehicles are currently loaded for checking.
              </p>
            )}

            {compatibility && (
              <div
                className={
                  compatibility.eligible_for_dispatch
                    ? 'driver-result driver-result-ok'
                    : 'driver-result driver-result-blocked'
                }
                role="status"
              >
                <strong>
                  {compatibility.eligible_for_dispatch
                    ? 'Compatible and currently eligible'
                    : 'Not currently eligible'}
                </strong>

                <p>{compatibility.reason}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

export default DriverManagementPage