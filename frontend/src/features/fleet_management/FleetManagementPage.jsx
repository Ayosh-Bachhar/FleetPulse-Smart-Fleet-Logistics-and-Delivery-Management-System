import { useEffect, useState } from 'react'
import { useAuth } from '../../context/auth'

import VehicleForm from './VehicleForm'

import {
  getVehicles,
  getVehicle,
} from './fleetManagementApi'


const PAGE_SIZE = 10

const STATUS_LABELS = {
  available: 'Available',
  in_use: 'In use',
  maintenance: 'Maintenance',
  inactive: 'Inactive',
}


function FleetManagementPage() {
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
  const [statusFilter, setStatusFilter] = useState('')

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [creating, setCreating] = useState(false)
  const [editingVehicle, setEditingVehicle] = useState(null)
  const [selectedVehicle, setSelectedVehicle] = useState(null)

  const [reloadKey, setReloadKey] = useState(0)


  useEffect(() => {
    if (!canManage) {
      return
    }

    const controller = new AbortController()

    async function loadVehicles() {
      setLoading(true)
      setError('')

      try {
        const data = await getVehicles(
          {
            search: search || undefined,
            status: statusFilter || undefined,
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
          if (err.response?.status === 403) {
            setError('You do not have permission to view the fleet.')
          } else {
            setError('Unable to load vehicles.')
          }
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadVehicles()

    return () => controller.abort()
  }, [canManage, search, statusFilter, page, reloadKey])


  function handleSearch(event) {
    event.preventDefault()
    setPage(1)
    setSearch(searchInput.trim())
  }


  function handleSaved() {
    setCreating(false)
    setEditingVehicle(null)
    setSelectedVehicle(null)
    setSuccess('Vehicle information saved successfully.')
    setReloadKey((previous) => previous + 1)
  }


  function handleAdd() {
    setCreating(true)
    setEditingVehicle(null)
    setSelectedVehicle(null)
    setError('')
    setSuccess('')
  }


  function handleEdit(vehicle) {
    setEditingVehicle(vehicle)
    setCreating(false)
    setSelectedVehicle(null)
    setError('')
    setSuccess('')
  }


  async function handleView(vehicleId) {
    setError('')
    setSelectedVehicle(null)

    try {
      const vehicle = await getVehicle(vehicleId)

      setSelectedVehicle(vehicle)
      setCreating(false)
      setEditingVehicle(null)
    } catch {
      setError('Unable to load vehicle details.')
    }
  }


  function handleCancel() {
    setCreating(false)
    setEditingVehicle(null)
  }


  function changeStatusFilter(event) {
    setStatusFilter(event.target.value)
    setPage(1)
    setSuccess('')
  }


  function formatDate(value) {
    if (!value) {
      return '—'
    }

    return new Date(value).toLocaleDateString()
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
          Fleet Management is available only to
          Admin and Dispatcher accounts.
        </p>
      </section>
    )
  }


  return (
    <section className="fleet-page">
      <div className="fleet-header">
        <div>
          <p className="workspace-eyebrow">
            FLEET OPERATIONS
          </p>

          <h1 className="workspace-heading">
            Fleet Management
          </h1>

          <p className="workspace-description">
            Manage vehicles, capacities, fuel types,
            and operational availability.
          </p>
        </div>

        <button
          type="button"
          className="button button-primary"
          onClick={handleAdd}
        >
          + Add vehicle
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

      {(creating || editingVehicle) && (
        <VehicleForm
          key={editingVehicle?.id || 'new'}
          vehicle={editingVehicle}
          onSaved={handleSaved}
          onCancel={handleCancel}
        />
      )}

      <div className="fleet-panel">
        <div className="fleet-panel-header">
          <div>
            <h2>Vehicle records</h2>
            <p>
              {total} matching vehicle{total === 1 ? '' : 's'}
            </p>
          </div>
        </div>

        <div className="fleet-toolbar">
          <form
            className="fleet-search"
            onSubmit={handleSearch}
          >
            <input
              type="search"
              className="form-input"
              placeholder="Search registration, type, or fuel..."
              aria-label="Search vehicles"
              value={searchInput}
              onChange={(event) => {
                setSearchInput(event.target.value)
              }}
            />

            <button
              type="submit"
              className="button button-outline"
            >
              Search
            </button>
          </form>

          <select
            className="form-input fleet-filter"
            aria-label="Filter vehicle status"
            value={statusFilter}
            onChange={changeStatusFilter}
          >
            <option value="">All statuses</option>
            <option value="available">Available</option>
            <option value="in_use">In use</option>
            <option value="maintenance">Maintenance</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>

        <div className="fleet-table-container">
          <table className="fleet-table">
            <thead>
              <tr>
                <th>Registration</th>
                <th>Type</th>
                <th>Weight (kg)</th>
                <th>Volume (m³)</th>
                <th>Fuel</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="fleet-empty">
                    Loading vehicles...
                  </td>
                </tr>
              ) : vehicles.length === 0 ? (
                <tr>
                  <td colSpan={7} className="fleet-empty">
                    No vehicles found.
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

                    <td>{vehicle.capacity_kg}</td>

                    <td>
                      {vehicle.volume_capacity_m3 ?? 'Not set'}
                    </td>

                    <td>{vehicle.fuel_type || 'Not set'}</td>

                    <td>
                      <span
                        className={
                          `fleet-status fleet-status-${vehicle.status}`
                        }
                      >
                        {STATUS_LABELS[vehicle.status]
                          || vehicle.status}
                      </span>
                    </td>

                    <td>
                      <div className="fleet-actions">
                        <button
                          type="button"
                          onClick={() => handleView(vehicle.id)}
                        >
                          View
                        </button>

                        <button
                          type="button"
                          onClick={() => handleEdit(vehicle)}
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
              type="button"
              className="button button-outline"
              disabled={loading || page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>

            <button
              type="button"
              className="button button-outline"
              disabled={loading || page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {selectedVehicle && (
        <div className="fleet-panel">
          <div className="fleet-panel-header">
            <div>
              <h2>Vehicle details</h2>
              <p>{selectedVehicle.registration_number}</p>
            </div>

            <button
              type="button"
              className="button button-outline"
              onClick={() => setSelectedVehicle(null)}
            >
              Close
            </button>
          </div>

          <div className="fleet-details">
            <div>
              <span>Registration</span>
              <strong>
                {selectedVehicle.registration_number}
              </strong>
            </div>

            <div>
              <span>Vehicle type</span>
              <strong>{selectedVehicle.vehicle_type}</strong>
            </div>

            <div>
              <span>Weight capacity</span>
              <strong>
                {selectedVehicle.capacity_kg} kg
              </strong>
            </div>

            <div>
              <span>Volume capacity</span>
              <strong>
                {selectedVehicle.volume_capacity_m3 == null
                  ? 'Not set'
                  : `${selectedVehicle.volume_capacity_m3} m³`}
              </strong>
            </div>

            <div>
              <span>Fuel type</span>
              <strong>
                {selectedVehicle.fuel_type || 'Not set'}
              </strong>
            </div>

            <div>
              <span>Status</span>
              <strong>
                {STATUS_LABELS[selectedVehicle.status]}
              </strong>
            </div>

            <div>
              <span>Available</span>
              <strong>
                {selectedVehicle.is_available ? 'Yes' : 'No'}
              </strong>
            </div>

            <div>
              <span>Created</span>
              <strong>
                {formatDate(selectedVehicle.created_at)}
              </strong>
            </div>

            <div>
              <span>Last updated</span>
              <strong>
                {formatDate(selectedVehicle.updated_at)}
              </strong>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export default FleetManagementPage