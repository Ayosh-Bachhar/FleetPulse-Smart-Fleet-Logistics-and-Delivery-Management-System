import { useState } from 'react'

import { createOrder } from './orderIntakeApi'


const INITIAL_FORM = {
  customer_email: '',
  pickup_address: '',
  delivery_address: '',
  weight_kg: '',
  length_cm: '',
  width_cm: '',
  height_cm: '',
  is_rush: false,
}


function getErrorMessage(error) {
  const detail = error.response?.data?.detail

  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg)
      .filter(Boolean)
      .join(' ')
  }

  return 'Unable to place the order. Please try again.'
}


function OrderForm({
  isDispatcher,
  onSaved,
  onCancel,
}) {
  const [form, setForm] = useState(INITIAL_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')


  function handleChange(event) {
    const {
      name,
      type,
      value,
      checked,
    } = event.target

    setForm((previous) => ({
      ...previous,
      [name]: type === 'checkbox'
        ? checked
        : value,
    }))
  }


  const length = Number(form.length_cm)
  const width = Number(form.width_cm)
  const height = Number(form.height_cm)

  const validDimensions = (
    form.length_cm !== ''
    && form.width_cm !== ''
    && form.height_cm !== ''
    && Number.isFinite(length)
    && Number.isFinite(width)
    && Number.isFinite(height)
    && length >= 1
    && width >= 1
    && height >= 1
  )

  const calculatedVolume = validDimensions
    ? (length * width * height) / 1000000
    : null


  async function handleSubmit(event) {
    event.preventDefault()
    setError('')

    const pickup = form.pickup_address.trim()
    const delivery = form.delivery_address.trim()

    if (
      pickup.length < 5
      || delivery.length < 5
    ) {
      setError(
        'Enter valid pickup and delivery addresses.'
      )
      return
    }

    if (
      pickup.toLowerCase()
      === delivery.toLowerCase()
    ) {
      setError(
        'Pickup and delivery addresses must be different.'
      )
      return
    }

    if (!validDimensions) {
      setError(
        'Enter valid package dimensions in centimetres.'
      )
      return
    }

    const weight = Number(form.weight_kg)

    if (
      form.weight_kg === ''
      || !Number.isFinite(weight)
      || weight <= 0
    ) {
      setError('Enter a valid package weight.')
      return
    }

    if (
      isDispatcher
      && !form.customer_email.trim()
    ) {
      setError(
        'Enter the registered customer email.'
      )
      return
    }

    const payload = {
      pickup_address: pickup,
      delivery_address: delivery,
      weight_kg: weight,
      length_cm: length,
      width_cm: width,
      height_cm: height,
      is_rush: form.is_rush,
    }

    if (isDispatcher) {
      payload.customer_email = (
        form.customer_email.trim().toLowerCase()
      )
    }

    setSaving(true)

    try {
      const created = await createOrder(payload)
      onSaved(created)

    } catch (err) {
      setError(getErrorMessage(err))

    } finally {
      setSaving(false)
    }
  }


  return (
    <section className="fleet-panel order-form-panel">
      <div className="fleet-panel-header">
        <div>
          <h2>Place delivery order</h2>

          <p>
            Enter pickup, delivery and package details.
            Volume is calculated automatically.
          </p>
        </div>
      </div>

      {error && (
        <p
          className="notice notice-error"
          role="alert"
        >
          {error}
        </p>
      )}

      <form
        className="order-form"
        onSubmit={handleSubmit}
      >
        {isDispatcher && (
          <label className="field">
            Registered customer email

            <input
              type="email"
              className="form-input"
              name="customer_email"
              placeholder="customer@example.com"
              value={form.customer_email}
              onChange={handleChange}
              required
              maxLength={254}
            />

            <small className="order-field-help">
              The customer must already have a
              FleetPulse Customer account.
            </small>
          </label>
        )}

        <div className="order-form-grid">
          <label className="field">
            Pickup address

            <textarea
              className="form-input order-address-input"
              name="pickup_address"
              value={form.pickup_address}
              onChange={handleChange}
              placeholder="Uttara, Dhaka"
              minLength={5}
              maxLength={500}
              required
              rows={3}
            />
          </label>

          <label className="field">
            Delivery address

            <textarea
              className="form-input order-address-input"
              name="delivery_address"
              value={form.delivery_address}
              onChange={handleChange}
              placeholder="Mirpur, Dhaka"
              minLength={5}
              maxLength={500}
              required
              rows={3}
            />
          </label>
        </div>

        <div className="order-section-heading">
          <h3>Package information</h3>

          <p>
            Dimensions are entered in centimetres.
          </p>
        </div>

        <div className="order-form-grid">
          <label className="field">
            Weight (kg)

            <input
              type="number"
              className="form-input"
              name="weight_kg"
              value={form.weight_kg}
              onChange={handleChange}
              min="0.001"
              max="50000"
              step="any"
              required
              placeholder="25"
            />
          </label>

          <label className="field">
            Length (cm)

            <input
              type="number"
              className="form-input"
              name="length_cm"
              value={form.length_cm}
              onChange={handleChange}
              min="1"
              max="10000"
              step="any"
              required
              placeholder="100"
            />
          </label>

          <label className="field">
            Width (cm)

            <input
              type="number"
              className="form-input"
              name="width_cm"
              value={form.width_cm}
              onChange={handleChange}
              min="1"
              max="10000"
              step="any"
              required
              placeholder="50"
            />
          </label>

          <label className="field">
            Height (cm)

            <input
              type="number"
              className="form-input"
              name="height_cm"
              value={form.height_cm}
              onChange={handleChange}
              min="1"
              max="10000"
              step="any"
              required
              placeholder="50"
            />
          </label>
        </div>

        <div className="order-calculated-volume">
          <span>Calculated package volume</span>

          <strong>
            {calculatedVolume !== null
              ? `${calculatedVolume.toFixed(6)} m³`
              : 'Enter package dimensions'}
          </strong>
        </div>

        <label className="order-rush-option">
          <input
            type="checkbox"
            name="is_rush"
            checked={form.is_rush}
            onChange={handleChange}
          />

          <span>
            <strong>Rush delivery</strong>

            <small>
              Mark this order as urgent.
              Any additional fee will be
              calculated by F8 Pricing Engine.
            </small>
          </span>
        </label>

        <p className="order-form-note">
          New orders start in Placed status.
          Dispatchers will prepare them for
          delivery through F9 Order Lifecycle.
        </p>

        <div className="fleet-form-actions">
          <button
            type="button"
            className="button button-outline"
            onClick={onCancel}
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
              ? 'Placing order...'
              : 'Place order'}
          </button>
        </div>
      </form>
    </section>
  )
}

export default OrderForm