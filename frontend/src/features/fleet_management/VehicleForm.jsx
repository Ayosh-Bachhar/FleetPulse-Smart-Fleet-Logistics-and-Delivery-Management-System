import { useState } from 'react'

import {
  createVehicle,
  updateVehicle,
} from './fleetManagementApi'


function VehicleForm({ vehicle = null, onSaved, onCancel }) {
  const isEditing = Boolean(vehicle)

  const [form, setForm] = useState({
    registration_number: vehicle?.registration_number || '',
    vehicle_type: vehicle?.vehicle_type || '',
    capacity_kg: vehicle?.capacity_kg?.toString() || '',
    volume_capacity_m3:
      vehicle?.volume_capacity_m3?.toString() || '',
    fuel_type: vehicle?.fuel_type || '',
    status: vehicle?.status || 'available',
  })

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')


  function handleChange(event) {
    const { name, value } = event.target

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }))
  }


  async function handleSubmit(event) {
    event.preventDefault()
    setError('')

    const payload = {
      registration_number:
        form.registration_number.trim().toUpperCase(),

      vehicle_type: form.vehicle_type.trim(),

      capacity_kg: Number(form.capacity_kg),

      volume_capacity_m3:
        form.volume_capacity_m3.trim()
          ? Number(form.volume_capacity_m3)
          : null,

      fuel_type: form.fuel_type.trim() || null,

      status: form.status,
    }

    if (
      !Number.isFinite(payload.capacity_kg)
      || payload.capacity_kg <= 0
    ) {
      setError('Weight capacity must be greater than zero.')
      return
    }

    if (
      payload.volume_capacity_m3 !== null
      && (
        !Number.isFinite(payload.volume_capacity_m3)
        || payload.volume_capacity_m3 <= 0
      )
    ) {
      setError('Volume capacity must be greater than zero.')
      return
    }

    if (!isEditing && payload.volume_capacity_m3 === null) {
      setError('Volume capacity is required for new vehicles.')
      return
    }

    if (!isEditing && !payload.fuel_type) {
      setError('Fuel type is required for new vehicles.')
      return
    }

    setSaving(true)

    try {
      if (isEditing) {
        await updateVehicle(vehicle.id, payload)
      } else {
        await createVehicle(payload)
      }

      onSaved()
    } catch (err) {
      const status = err.response?.status

      if (status === 409) {
        setError('A vehicle with this registration already exists.')
      } else if (status === 422) {
        setError('Please check the vehicle information.')
      } else if (status === 403) {
        setError('You are not authorized to save vehicles.')
      } else {
        setError('Unable to save vehicle. Please try again.')
      }
    } finally {
      setSaving(false)
    }
  }


  return (
    <section className="fleet-panel">
      <div className="fleet-panel-header">
        <div>
          <h2>
            {isEditing ? 'Edit vehicle' : 'Add new vehicle'}
          </h2>

          <p>
            Enter the vehicle details and operating status.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="fleet-form">
        <div className="fleet-form-grid">
          <label className="field">
            Registration number
            <input
              className="form-input"
              name="registration_number"
              value={form.registration_number}
              onChange={handleChange}
              minLength={3}
              maxLength={32}
              placeholder="FP-TRUCK-005"
              required
            />
          </label>

          <label className="field">
            Vehicle type
            <input
              className="form-input"
              name="vehicle_type"
              value={form.vehicle_type}
              onChange={handleChange}
              placeholder="Truck, Van, Mini Van"
              maxLength={60}
              required
            />
          </label>

          <label className="field">
            Weight capacity (kg)
            <input
              className="form-input"
              name="capacity_kg"
              type="number"
              min="0.001"
              step="any"
              value={form.capacity_kg}
              onChange={handleChange}
              required
            />
          </label>

          <label className="field">
            Volume capacity (m³)
            <input
              className="form-input"
              name="volume_capacity_m3"
              type="number"
              min="0.001"
              step="any"
              value={form.volume_capacity_m3}
              onChange={handleChange}
              placeholder="e.g. 20"
              required={!isEditing}
            />
          </label>

          <label className="field">
            Fuel type
            <input
              className="form-input"
              name="fuel_type"
              value={form.fuel_type}
              onChange={handleChange}
              placeholder="Diesel, Petrol, Electric"
              maxLength={40}
              required={!isEditing}
            />
          </label>

          <label className="field">
            Vehicle status
            <select
              className="form-input"
              name="status"
              value={form.status}
              onChange={handleChange}
            >
              <option value="available">Available</option>
              <option value="in_use">In use</option>
              <option value="maintenance">Maintenance</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
        </div>

        {error && (
          <p className="notice notice-error" role="alert">
            {error}
          </p>
        )}

        <div className="fleet-form-actions">
          <button
            className="button button-outline"
            type="button"
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </button>

          <button
            className="button button-primary"
            type="submit"
            disabled={saving}
          >
            {saving
              ? 'Saving...'
              : isEditing
                ? 'Save changes'
                : 'Add vehicle'}
          </button>
        </div>
      </form>
    </section>
  )
}

export default VehicleForm