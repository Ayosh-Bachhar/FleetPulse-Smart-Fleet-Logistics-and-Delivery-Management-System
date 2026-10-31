import { useState } from 'react'

import { createDispatch } from './dispatchPlanningApi'


function formatDateTime(value) {
  return new Date(value).toLocaleString()
}


function DispatchPlanner({
  shifts = [],
  drivers = [],
  vehicles = [],
  orders = [],
  onDispatched,
  onCancel,
}) {
  const [shiftId, setShiftId] = useState('')
  const [orderIds, setOrderIds] = useState([])

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')


  const selectedShift = shifts.find(
    (item) => item.id === shiftId
  )

  const selectedDriver = drivers.find(
    (item) => item.id === selectedShift?.driver_id
  )

  const selectedVehicle = vehicles.find(
    (item) => item.id === selectedShift?.vehicle_id
  )

  const selectedOrders = orders.filter(
    (order) => orderIds.includes(order.id)
  )

  const totalWeight = selectedOrders.reduce(
    (sum, order) => sum + order.weight_kg,
    0
  )

  const totalVolume = selectedOrders.reduce(
    (sum, order) => sum + order.volume_m3,
    0
  )

  const weightExceeded = (
    selectedVehicle
    && totalWeight > selectedVehicle.capacity_kg
  )

  const volumeMissing = (
    selectedVehicle
    && selectedVehicle.volume_capacity_m3 == null
  )

  const volumeExceeded = (
    selectedVehicle
    && !volumeMissing
    && totalVolume > selectedVehicle.volume_capacity_m3
  )


  function toggleOrder(orderId) {
    setOrderIds((previous) => (
      previous.includes(orderId)
        ? previous.filter((id) => id !== orderId)
        : [...previous, orderId]
    ))

    setError('')
  }


  async function handleSubmit(event) {
    event.preventDefault()
    setError('')

    if (!shiftId) {
      setError('Select a scheduled shift.')
      return
    }

    if (orderIds.length === 0) {
      setError('Select at least one order.')
      return
    }

    if (
      weightExceeded
      || volumeExceeded
      || volumeMissing
    ) {
      setError(
        'Vehicle capacity is missing or exceeded.'
      )
      return
    }

    setSaving(true)

    try {
      const trip = await createDispatch({
        shift_id: shiftId,
        order_ids: orderIds,
      })

      onDispatched(trip)
    } catch (err) {
      const detail = err.response?.data?.detail

      if (typeof detail === 'string') {
        setError(detail)
      } else if (err.response?.status === 409) {
        setError(
          'Dispatch conflict. Reload and try again.'
        )
      } else if (err.response?.status === 422) {
        setError('Check the selected resources and orders.')
      } else {
        setError('Unable to dispatch the trip.')
      }
    } finally {
      setSaving(false)
    }
  }


  return (
    <section className="fleet-panel">
      <div className="fleet-panel-header">
        <div>
          <h2>Create dispatch</h2>

          <p>
            Select a scheduled shift and group eligible
            warehouse orders into one trip.
          </p>
        </div>
      </div>

      <form
        className="fleet-form"
        onSubmit={handleSubmit}
      >
        <label className="field">
          Scheduled shift

          <select
            className="form-input"
            value={shiftId}
            onChange={(event) => {
              setShiftId(event.target.value)
              setError('')
            }}
            required
          >
            <option value="">Select a shift</option>

            {shifts.map((shift) => (
              <option
                key={shift.id}
                value={shift.id}
              >
                {shift.driver_name}
                {' — '}
                {shift.vehicle_registration}
                {' — '}
                {formatDateTime(shift.start_at)}
              </option>
            ))}
          </select>
        </label>

        {selectedShift && (
          <div className="dispatch-resource-summary">
            <div>
              <span>Driver</span>

              <strong>
                {selectedDriver?.full_name
                  || selectedShift.driver_name}
              </strong>
            </div>

            <div>
              <span>Vehicle</span>

              <strong>
                {selectedVehicle?.registration_number
                  || selectedShift.vehicle_registration}
              </strong>
            </div>

            <div>
              <span>Vehicle weight capacity</span>

              <strong>
                {selectedVehicle?.capacity_kg ?? 'Unknown'} kg
              </strong>
            </div>

            <div>
              <span>Vehicle volume capacity</span>

              <strong>
                {selectedVehicle?.volume_capacity_m3 ?? 'Not set'} m³
              </strong>
            </div>

            <div>
              <span>Shift starts</span>

              <strong>
                {formatDateTime(selectedShift.start_at)}
              </strong>
            </div>

            <div>
              <span>Shift ends</span>

              <strong>
                {formatDateTime(selectedShift.end_at)}
              </strong>
            </div>
          </div>
        )}

        <div className="dispatch-orders-heading">
          <div>
            <h3>Eligible warehouse orders</h3>

            <p>
              Select up to 20 orders per trip.
            </p>
          </div>

          <strong>
            {orderIds.length} selected
          </strong>
        </div>

        <div className="dispatch-order-list">
          {orders.length === 0 ? (
            <p className="dispatch-empty">
              No eligible Warehouse orders found.
              Run the demo-order seeder or create orders
              through F6 when available.
            </p>
          ) : (
            orders.map((order) => (
              <label
                className="dispatch-order-option"
                key={order.id}
              >
                <input
                  type="checkbox"
                  checked={orderIds.includes(order.id)}
                  disabled={
                    !orderIds.includes(order.id)
                    && orderIds.length >= 20
                  }
                  onChange={() => toggleOrder(order.id)}
                />

                <span className="dispatch-order-content">
                  <strong>{order.reference_code}</strong>

                  <small>
                    {order.pickup_address}
                    {' → '}
                    {order.delivery_address}
                  </small>

                  <small>
                    {order.weight_kg} kg
                    {' | '}
                    {order.volume_m3} m³
                    {order.is_rush ? ' | Rush' : ''}
                  </small>
                </span>
              </label>
            ))
          )}
        </div>

        <div className="dispatch-load-summary">
          <div>
            <span>Total selected weight</span>

            <strong>
              {totalWeight.toFixed(2)} kg
            </strong>
          </div>

          <div>
            <span>Total selected volume</span>

            <strong>
              {totalVolume.toFixed(3)} m³
            </strong>
          </div>
        </div>

        {(weightExceeded || volumeExceeded || volumeMissing) && (
          <p
            className="notice notice-error"
            role="alert"
          >
            The selected vehicle cannot carry this load.
            Check its capacity in Fleet Management.
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
            disabled={
              saving
              || shifts.length === 0
              || orders.length === 0
              || weightExceeded
              || volumeExceeded
              || volumeMissing
            }
          >
            {saving
              ? 'Dispatching...'
              : 'Dispatch trip'}
          </button>
        </div>
      </form>
    </section>
  )
}

export default DispatchPlanner