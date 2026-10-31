function MaintenanceAlertCard({
  vehicle,
  onAction,
  onClose,
}) {
  const progress = Math.min(
    100,
    Math.max(0, vehicle.service_progress_percent)
  )

  const statusText = vehicle.maintenance_due
    ? 'Service due'
    : vehicle.status === 'maintenance'
      ? 'Under maintenance'
      : vehicle.status === 'inactive'
        ? 'Inactive'
        : 'Service monitored'

  return (
    <section className="fleet-panel maintenance-details-card">
      <div className="fleet-panel-header">
        <div>
          <h2>{vehicle.registration_number}</h2>
          <p>
            {vehicle.vehicle_type} — Maintenance details
          </p>
        </div>

        <button
          type="button"
          className="button button-outline"
          onClick={onClose}
        >
          Close
        </button>
      </div>

      <div
        className={
          vehicle.needs_attention
            ? 'maintenance-message maintenance-message-warning'
            : 'maintenance-message maintenance-message-ok'
        }
      >
        <strong>{statusText}</strong>

        <p>
          {vehicle.maintenance_due
            ? 'This vehicle has reached its service threshold and cannot be dispatched until service is completed.'
            : vehicle.status === 'maintenance'
              ? 'This vehicle is marked for maintenance and cannot be dispatched.'
              : 'Mileage is being monitored against the configured service interval.'}
        </p>
      </div>

      <div className="maintenance-progress-heading">
        <span>Distance since last service</span>

        <strong>
          {vehicle.kilometers_since_service.toLocaleString()}
          {' / '}
          {vehicle.service_interval_km.toLocaleString()} km
        </strong>
      </div>

      <div className="maintenance-progress-track">
        <div
          className={
            vehicle.needs_attention
              ? 'maintenance-progress-fill is-due'
              : 'maintenance-progress-fill'
          }
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="fleet-details maintenance-details-grid">
        <div>
          <span>Total simulated mileage</span>
          <strong>
            {vehicle.odometer_km.toLocaleString()} km
          </strong>
        </div>

        <div>
          <span>Last service mileage</span>
          <strong>
            {vehicle.last_service_km.toLocaleString()} km
          </strong>
        </div>

        <div>
          <span>Remaining before service</span>
          <strong>
            {vehicle.kilometers_until_service.toLocaleString()} km
          </strong>
        </div>

        <div>
          <span>Dispatch availability</span>
          <strong>
            {vehicle.is_available ? 'Available' : 'Blocked'}
          </strong>
        </div>
      </div>

      <div className="maintenance-card-actions">
        <button
          type="button"
          className="button button-outline"
          onClick={() => onAction('distance', vehicle)}
        >
          + Record distance
        </button>

        <button
          type="button"
          className="button button-outline"
          onClick={() => onAction('interval', vehicle)}
        >
          Change interval
        </button>

        <button
          type="button"
          className="button button-primary"
          disabled={vehicle.status === 'in_use'}
          onClick={() => onAction('service', vehicle)}
        >
          Complete service
        </button>
      </div>
    </section>
  )
}

export default MaintenanceAlertCard