function formatValue(value, unit) {
  const number = Number(value)

  if (!Number.isFinite(number)) {
    return '—'
  }

  return `${number.toFixed(2)} ${unit}`
}


function StopList({ title, variant }) {
  return (
    <div className="sequence-stop-group">
      <h3>{title}</h3>

      <ol className="sequence-stop-list">
        {variant.stops.map((stop, index) => (
          <li
            key={`${stop.order_id}-${stop.kind}-${index}`}
          >
            <span className="sequence-stop-index">
              {index + 1}
            </span>

            <div className="sequence-stop-text">
              <strong>
                {stop.kind === 'pickup'
                  ? 'Pickup'
                  : 'Delivery'}
              </strong>

              <span>{stop.address}</span>

              <small>
                Order:
                {' '}
                {stop.order_id.slice(-8).toUpperCase()}
              </small>
            </div>
          </li>
        ))}
      </ol>

      <div className="sequence-variant-footer">
        <div>
          <span>Distance</span>
          <strong>
            {formatValue(variant.distance_km, 'km')}
          </strong>
        </div>

        <div>
          <span>Travel time</span>
          <strong>
            {formatValue(
              variant.duration_minutes,
              'min'
            )}
          </strong>
        </div>
      </div>
    </div>
  )
}


function StopSequencePanel({
  sequence,
  canManage,
  applying,
  onApply,
}) {
  if (!sequence) return null

  const {
    original,
    optimized,
  } = sequence

  const isSaved = sequence.is_applied

  const improvement = (
    sequence.distance_saved_km > 0
  )

  return (
    <section className="fleet-panel sequence-result">
      <div className="fleet-panel-header">
        <div>
          <h2>
            {isSaved
              ? 'Applied stop sequence'
              : 'Optimization preview'}
          </h2>

          <p>
            Pickup-before-delivery nearest-neighbour
            optimization.
          </p>
        </div>

        <span
          className={
            isSaved
              ? 'sequence-pill sequence-pill-saved'
              : 'sequence-pill'
          }
        >
          {isSaved ? 'Saved' : 'Preview'}
        </span>
      </div>

      {original.source === 'demo_estimate' && (
        <p className="sequence-note">
          Offline demo estimates are approximate.
          They are not verified road distances
          or live traffic predictions.
        </p>
      )}

      <div className="sequence-comparison">
        <div>
          <span>Original distance</span>
          <strong>
            {formatValue(
              original.distance_km,
              'km'
            )}
          </strong>
        </div>

        <div>
          <span>Optimized distance</span>
          <strong>
            {formatValue(
              optimized.distance_km,
              'km'
            )}
          </strong>
        </div>

        <div>
          <span>Distance saved</span>
          <strong>
            {formatValue(
              sequence.distance_saved_km,
              'km'
            )}
          </strong>

          <small>
            {sequence.distance_saved_percent.toFixed(2)}
            % change
          </small>
        </div>

        <div>
          <span>Time saved</span>
          <strong>
            {formatValue(
              sequence.time_saved_minutes,
              'min'
            )}
          </strong>
        </div>
      </div>

      <p className="sequence-explanation">
        The algorithm selects the nearest feasible
        next stop using straight-line distances.
        The comparison above uses the F12 routing
        calculation for the resulting stop order.
      </p>

      {!isSaved && !sequence.sequence_changed && (
        <p className="sequence-note">
          The nearest-neighbour algorithm found
          the same stop order as the original route.
        </p>
      )}

      {!isSaved
        && sequence.sequence_changed
        && !sequence.can_apply
        && (
          <p className="sequence-note">
            The suggested sequence does not
            reduce measured route distance.
            Your existing F12 route will remain unchanged.
          </p>
        )}

      <div className="sequence-two-columns">
        <StopList
          title="Original sequence"
          variant={original}
        />

        <StopList
          title="Optimized sequence"
          variant={optimized}
        />
      </div>

      {canManage
        && !isSaved
        && sequence.can_apply
        && (
          <div className="sequence-actions">
            <button
              type="button"
              className="button button-primary"
              disabled={applying}
              onClick={onApply}
            >
              {applying
                ? 'Applying...'
                : 'Apply optimized sequence'}
            </button>
          </div>
        )}

      {isSaved && (
        <p className="sequence-saved-notice">
          Optimized route saved to the existing
          F12 TripRoute document. The original
          route information has been preserved.
        </p>
      )}

      {!isSaved && improvement && (
        <p className="sequence-note">
          This is only a preview.
          No route data changes until you
          click Apply optimized sequence.
        </p>
      )}
    </section>
  )
}

export default StopSequencePanel