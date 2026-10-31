import { useState } from 'react'

import {
  createShift,
  updateShift,
  checkShiftHolidays,
} from './shiftRosterApi'


function toLocalInput(value) {
  if (!value) return ''

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return ''

  const pad = (number) => String(number).padStart(2, '0')

  return (
    `${date.getFullYear()}-`
    + `${pad(date.getMonth() + 1)}-`
    + `${pad(date.getDate())}T`
    + `${pad(date.getHours())}:`
    + `${pad(date.getMinutes())}`
  )
}


function ShiftForm({
  shift = null,
  drivers = [],
  vehicles = [],
  onSaved,
  onCancel,
}) {
  const isEditing = Boolean(shift)

  const [form, setForm] = useState({
    driver_id: shift?.driver_id || '',
    vehicle_id: shift?.vehicle_id || '',
    start_at: toLocalInput(shift?.start_at),
    end_at: toLocalInput(shift?.end_at),
  })

  const [saving, setSaving] = useState(false)
  const [checking, setChecking] = useState(false)

  const [error, setError] = useState('')
  const [holidayPreview, setHolidayPreview] = useState(null)


  function handleChange(event) {
    const { name, value } = event.target

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }))

    setHolidayPreview(null)
  }


  function validateForm() {
    if (!form.driver_id || !form.vehicle_id) {
      setError('Select both a driver and a vehicle.')
      return null
    }

    if (!form.start_at || !form.end_at) {
      setError('Enter shift start and end times.')
      return null
    }

    const start = new Date(form.start_at)
    const end = new Date(form.end_at)

    if (
      Number.isNaN(start.getTime())
      || Number.isNaN(end.getTime())
    ) {
      setError('Enter valid dates and times.')
      return null
    }

    const duration = end.getTime() - start.getTime()

    if (duration <= 0) {
      setError('End time must be after start time.')
      return null
    }

    if (duration > 24 * 60 * 60 * 1000) {
      setError('A shift cannot exceed 24 hours.')
      return null
    }

    return {
      driver_id: form.driver_id,
      vehicle_id: form.vehicle_id,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
    }
  }


  function getErrorMessage(err) {
    const detail = err.response?.data?.detail

    if (typeof detail === 'string') {
      return detail
    }

    if (err.response?.status === 409) {
      return 'The driver or vehicle has a schedule conflict.'
    }

    if (err.response?.status === 422) {
      return 'Please check the shift information.'
    }

    if (err.response?.status === 403) {
      return 'You are not authorized to manage shifts.'
    }

    return 'Unable to complete the operation.'
  }


  async function handleHolidayCheck() {
    setError('')

    const payload = validateForm()

    if (!payload) return

    setChecking(true)
    setHolidayPreview(null)

    try {
      const result = await checkShiftHolidays(
        payload.start_at,
        payload.end_at
      )

      setHolidayPreview(result)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setChecking(false)
    }
  }


  async function handleSubmit(event) {
    event.preventDefault()
    setError('')

    const payload = validateForm()

    if (!payload) return

    setSaving(true)

    try {
      let saved

      if (isEditing) {
        saved = await updateShift(shift.id, payload)
      } else {
        saved = await createShift(payload)
      }

      onSaved(saved)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }


  return (
    <section className="fleet-panel">
      <div className="fleet-panel-header">
        <div>
          <h2>
            {isEditing ? 'Edit shift' : 'Schedule new shift'}
          </h2>

          <p>
            Assign one qualified driver and one available
            vehicle to a time slot.
          </p>
        </div>
      </div>

      <form
        className="fleet-form"
        onSubmit={handleSubmit}
      >
        <div className="fleet-form-grid">
          <label className="field">
            Driver
            <select
              className="form-input"
              name="driver_id"
              value={form.driver_id}
              onChange={handleChange}
              required
            >
              <option value="">Select driver</option>

              {drivers.map((driver) => (
                <option
                  key={driver.id}
                  value={driver.id}
                >
                  {driver.full_name}
                  {' — '}
                  {driver.license_class}
                  {' ('}
                  {driver.is_available
                    ? 'Eligible'
                    : 'Unavailable'}
                  {')'}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            Vehicle
            <select
              className="form-input"
              name="vehicle_id"
              value={form.vehicle_id}
              onChange={handleChange}
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
          </label>

          <label className="field">
            Shift start
            <input
              className="form-input"
              type="datetime-local"
              name="start_at"
              value={form.start_at}
              onChange={handleChange}
              required
            />
          </label>

          <label className="field">
            Shift end
            <input
              className="form-input"
              type="datetime-local"
              name="end_at"
              value={form.end_at}
              onChange={handleChange}
              required
            />
          </label>
        </div>

        <p className="shift-form-hint">
          Times are entered in your browser's local timezone.
          FleetPulse stores shift times in UTC.
          Maximum duration: 24 hours.
        </p>

        {holidayPreview && (
          <div
            className={
              holidayPreview.is_holiday
                ? 'shift-holiday-warning'
                : 'shift-holiday-info'
            }
            role="status"
          >
            <strong>
              {holidayPreview.is_holiday
                ? 'Public holiday warning'
                : 'Holiday check'}
            </strong>

            <p>{holidayPreview.notice}</p>

            <small>
              Source: {holidayPreview.source}
            </small>
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
            className="button button-outline"
            type="button"
            disabled={checking || saving}
            onClick={handleHolidayCheck}
          >
            {checking
              ? 'Checking...'
              : 'Check holidays'}
          </button>

          <button
            className="button button-primary"
            type="submit"
            disabled={saving || checking}
          >
            {saving
              ? 'Saving...'
              : isEditing
                ? 'Save changes'
                : 'Schedule shift'}
          </button>
        </div>
      </form>
    </section>
  )
}

export default ShiftForm