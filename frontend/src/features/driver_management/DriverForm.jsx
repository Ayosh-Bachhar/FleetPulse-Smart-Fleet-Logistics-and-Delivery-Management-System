import { useState } from 'react'

import {
  createDriver,
  updateDriver,
} from './driverManagementApi'


function DriverForm({
  driver = null,
  onSaved,
  onCancel,
}) {
  const isEditing = Boolean(driver)

  const [form, setForm] = useState({
    full_name: driver?.full_name || '',
    phone: driver?.phone || '',
    license_number: driver?.license_number || '',
    license_class: driver?.license_class || 'light',
    license_expiry: driver?.license_expiry || '',
    status: driver?.status || 'available',
    linked_user_email: driver?.linked_user_email || '',
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
      full_name: form.full_name.trim(),
      phone: form.phone.trim() || null,

      license_number:
        form.license_number.trim().toUpperCase(),

      license_class: form.license_class,
      license_expiry: form.license_expiry,
      status: form.status,

      linked_user_email:
        form.linked_user_email.trim().toLowerCase() || null,
    }

    if (payload.full_name.length < 2) {
      setError('Enter a valid driver name.')
      return
    }

    if (!payload.license_expiry) {
      setError('License expiry date is required.')
      return
    }

    setSaving(true)

    try {
      if (isEditing) {
        await updateDriver(driver.id, payload)
      } else {
        await createDriver(payload)
      }

      onSaved()
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail

      if (status === 409) {
        setError(
          typeof detail === 'string'
            ? detail
            : 'Driver license or linked account already exists.'
        )
      } else if (status === 422) {
        setError(
          typeof detail === 'string'
            ? detail
            : 'Check the license details and linked user email.'
        )
      } else if (status === 403) {
        setError('You are not authorized to save drivers.')
      } else {
        setError('Unable to save driver. Please try again.')
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
            {isEditing ? 'Edit driver' : 'Add new driver'}
          </h2>

          <p>
            Manage personal information, license eligibility,
            and driver availability.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="fleet-form">
        <div className="fleet-form-grid">
          <label className="field">
            Full name
            <input
              className="form-input"
              name="full_name"
              value={form.full_name}
              onChange={handleChange}
              minLength={2}
              maxLength={100}
              placeholder="Driver full name"
              required
            />
          </label>

          <label className="field">
            Phone number (optional)
            <input
              className="form-input"
              name="phone"
              type="tel"
              value={form.phone}
              onChange={handleChange}
              maxLength={20}
              placeholder="+8801700000000"
            />
          </label>

          <label className="field">
            License number
            <input
              className="form-input"
              name="license_number"
              value={form.license_number}
              onChange={handleChange}
              minLength={5}
              maxLength={40}
              placeholder="DL-2026-001"
              required
            />
          </label>

          <label className="field">
            License class
            <select
              className="form-input"
              name="license_class"
              value={form.license_class}
              onChange={handleChange}
            >
              <option value="light">Light</option>
              <option value="medium">Medium</option>
              <option value="heavy">Heavy</option>
            </select>
          </label>

          <label className="field">
            License expiry date
            <input
              className="form-input"
              type="date"
              name="license_expiry"
              value={form.license_expiry}
              onChange={handleChange}
              required
            />
          </label>

          <label className="field">
            Driver status
            <select
              className="form-input"
              name="status"
              value={form.status}
              onChange={handleChange}
            >
              <option value="available">Available</option>
              <option value="unavailable">Unavailable</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>

          <label className="field driver-form-full">
            Linked Driver account email (optional)
            <input
              className="form-input"
              name="linked_user_email"
              type="email"
              value={form.linked_user_email}
              onChange={handleChange}
              placeholder="driver@example.com"
            />

            <span className="driver-field-hint">
              Leave blank for a standalone driver record.
              To link an account, the user must already exist
              with the Driver role.
            </span>
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
                : 'Add driver'}
          </button>
        </div>
      </form>
    </section>
  )
}

export default DriverForm