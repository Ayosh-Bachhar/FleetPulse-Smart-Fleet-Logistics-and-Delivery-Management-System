function formatDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}


function RouteSummaryPanel({ route }) {
  if (!route) return null

  const isEstimate = route.is_estimate

  return (
    <section className="fleet-panel">
      <div className="fleet-panel-header">
        <div>
          <h2>Route summary</h2>

          <p>
            Trip {route.trip_id.slice(-8).toUpperCase()}
          </p>
        </div>

        <span
          className={
            isEstimate
              ? 'route-source route-source-demo'
              : 'route-source route-source-live'
          }
        >
          {isEstimate
            ? 'Demo estimate'
            : 'Geoapify road route'}
        </span>
      </div>

      {isEstimate && (
        <div className="route-warning">
          This is an approximate demonstration estimate,
          not an actual road route. Travel time and distance
          may differ significantly from real conditions.
          The geometry contains straight-line segments.
        </div>
      )}

      <div className="route-summary-stats">
        <div>
          <span>Estimated distance</span>
          <strong>
            {route.distance_km.toLocaleString()} km
          </strong>
        </div>

        <div>
          <span>Estimated travel time</span>
          <strong>
            {route.duration_minutes.toLocaleString()} min
          </strong>
        </div>

        <div>
          <span>Route stops</span>
          <strong>{route.stops.length}</strong>
        </div>
      </div>

      <div className="route-details">
        <div>
          <span>Source</span>

          <strong>
            {isEstimate
              ? 'Offline demonstration estimate'
              : 'Geoapify Routing API'}
          </strong>
        </div>

        <div>
          <span>Calculated at</span>

          <strong>
            {formatDateTime(route.calculated_at)}
          </strong>
        </div>

        <div>
          <span>Stored in MongoDB</span>

          <strong>
            {route.from_saved_route
              ? 'Loaded from saved route'
              : 'Calculated and saved'}
          </strong>
        </div>
      </div>

      <div className="route-stops-section">
        <h3>Route stop sequence</h3>

        <p>
          F12 currently follows each order's pickup,
          then its delivery. F13 will implement optimized
          stop sequencing.
        </p>

        <ol className="route-stop-list">
          {route.stops.map((stop, index) => (
            <li
              key={`${stop.order_id}-${stop.kind}-${index}`}
              className="route-stop-item"
            >
              <span className="route-stop-number">
                {index + 1}
              </span>

              <div className="route-stop-content">
                <strong>
                  {stop.kind === 'pickup'
                    ? 'Pickup'
                    : 'Delivery'}
                </strong>

                <span>{stop.address}</span>

                <small>
                  Order: {stop.order_id.slice(-8).toUpperCase()}
                </small>

                <small>
                  Coordinates:
                  {' '}
                  {stop.latitude.toFixed(6)},
                  {' '}
                  {stop.longitude.toFixed(6)}
                </small>
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="route-geometry-note">
        Route geometry is saved in GeoJSON MultiLineString
        format for later integration with F13, F14 and F16.
      </div>
    </section>
  )
}

export default RouteSummaryPanel