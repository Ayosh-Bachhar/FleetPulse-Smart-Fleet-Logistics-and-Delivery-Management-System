import { useEffect, useState } from 'react'

import { useAuth } from '../../context/auth'

import {
  getLifecycleOrders,
  getLifecycleOrder,
  updateOrderStatus,
} from './orderLifecycleApi'


import OrderStatusBadge from './OrderStatusBadge'

const ORDER_STAGES = [
  { value: 'placed', label: 'Placed' },
  { value: 'warehouse', label: 'Warehouse' },
  { value: 'out_for_delivery', label: 'Out for Delivery' },
  { value: 'delivered', label: 'Delivered' },
]


function statusLabel(value) {
  return (
    ORDER_STAGES.find(
      (stage) => stage.value === value
    )?.label || value
  )
}


const PAGE_SIZE = 10


function getErrorMessage(error, fallback) {
  const detail = error.response?.data?.detail

  if (typeof detail === 'string') {
    return detail
  }

  return fallback
}


function formatDateTime(value) {
  return value
    ? new Date(value).toLocaleString()
    : '—'
}


function LifecycleProgress({ status }) {
  const currentIndex = ORDER_STAGES.findIndex(
    (stage) => stage.value === status
  )

  return (
    <div className="lifecycle-progress">
      {ORDER_STAGES.map((stage, index) => {
        const completed = index <= currentIndex

        return (
          <div
            key={stage.value}
            className={
              `lifecycle-progress-step ${
                completed ? 'is-complete' : ''
              }`
            }
          >
            <span className="lifecycle-step-number">
              {index + 1}
            </span>

            <span>{stage.label}</span>
          </div>
        )
      })}
    </div>
  )
}


function OrderLifecyclePage() {
  const { user } = useAuth()

  const canView = [
    'admin',
    'dispatcher',
    'driver',
    'customer',
  ].includes(user?.role)

  const canManage = [
    'dispatcher',
    'driver',
  ].includes(user?.role)

  const [orders, setOrders] = useState([])
  const [total, setTotal] = useState(0)

  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')

  const [selectedOrder, setSelectedOrder] = useState(null)

  const [loading, setLoading] = useState(true)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [busy, setBusy] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [reloadKey, setReloadKey] = useState(0)


  useEffect(() => {
    if (!canView) return

    const controller = new AbortController()

    async function loadOrders() {
      try {
        const result = await getLifecycleOrders(
          {
            status: statusFilter || undefined,
            search: search || undefined,
            page,
            page_size: PAGE_SIZE,
          },
          controller.signal
        )

        if (!controller.signal.aborted) {
          setOrders(result.items)
          setTotal(result.total)
        }

      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            getErrorMessage(
              err,
              'Unable to load order lifecycle records.'
            )
          )
        }

      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadOrders()

    return () => controller.abort()
  }, [
    canView,
    page,
    statusFilter,
    search,
    reloadKey,
  ])


  async function handleView(orderId) {
    setLoadingDetails(true)
    setError('')
    setSuccess('')

    try {
      const result = await getLifecycleOrder(orderId)
      setSelectedOrder(result)

    } catch (err) {
      setError(
        getErrorMessage(
          err,
          'Unable to view this order.'
        )
      )

    } finally {
      setLoadingDetails(false)
    }
  }


  async function handleStatusChange(order) {
    if (
      !canManage
      || !order.allowed_next_status
      || busy
    ) {
      return
    }

    const target = order.allowed_next_status

    const confirmed = window.confirm(
      `Move order ${order.reference_code} `
      + `to ${statusLabel(target)}?`
    )

    if (!confirmed) return

    setBusy(true)
    setError('')
    setSuccess('')

    try {
      const updated = await updateOrderStatus(
        order.id,
        target
      )

      setSelectedOrder(updated)

      setSuccess(
        `Order ${updated.reference_code} moved `
        + `to ${statusLabel(updated.status)}.`
      )

      setReloadKey((old) => old + 1)

    } catch (err) {
      setError(
        getErrorMessage(
          err,
          'Unable to update the order status.'
        )
      )

    } finally {
      setBusy(false)
    }
  }


  function handleSearch(event) {
    event.preventDefault()

    setPage(1)
    setSearch(searchInput.trim())
    setLoading(true)
    setError('')
  }


  const totalPages = Math.max(
    1,
    Math.ceil(total / PAGE_SIZE)
  )


  if (!canView) {
    return (
      <section className="workspace-welcome">
        <h1 className="workspace-heading">
          Access restricted
        </h1>

        <p className="workspace-description">
          You do not have permission to view
          order lifecycle records.
        </p>
      </section>
    )
  }


  return (
    <section className="lifecycle-page">
      <header>
        <p className="workspace-eyebrow">
          DELIVERY OPERATIONS
        </p>

        <h1 className="workspace-heading">
          Order Lifecycle
        </h1>

        <p className="workspace-description">
          Monitor order progress from placement
          through warehouse preparation, dispatch
          and delivery confirmation.
        </p>
      </header>

      {error && (
        <p
          className="notice notice-error"
          role="alert"
        >
          {error}
        </p>
      )}

      {success && (
        <p
          className="notice notice-success"
          role="status"
        >
          {success}
        </p>
      )}

      <section className="fleet-panel">
        <div className="fleet-panel-header">
          <div>
            <h2>
              {user?.role === 'customer'
                ? 'My order progress'
                : user?.role === 'driver'
                  ? 'My assigned orders'
                  : 'Delivery orders'}
            </h2>

            <p>
              {total} matching order
              {total === 1 ? '' : 's'}
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
              aria-label="Search order reference"
              placeholder="Search order reference..."
              value={searchInput}
              maxLength={100}
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
            aria-label="Filter order status"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value)
              setPage(1)
              setLoading(true)
            }}
          >
            <option value="">All statuses</option>

            {ORDER_STAGES.map((stage) => (
              <option
                key={stage.value}
                value={stage.value}
              >
                {stage.label}
              </option>
            ))}
          </select>
        </div>

        <div className="fleet-table-container">
          <table className="fleet-table lifecycle-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Pickup</th>
                <th>Delivery</th>
                <th>Status</th>
                <th>Trip</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="fleet-empty">
                    Loading orders...
                  </td>
                </tr>

              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan={6} className="fleet-empty">
                    No matching orders found.
                  </td>
                </tr>

              ) : (
                orders.map((order) => (
                  <tr key={order.id}>
                    <td>
                      <strong>
                        {order.reference_code}
                      </strong>

                      {order.is_rush && (
                        <small className="lifecycle-rush">
                          Rush delivery
                        </small>
                      )}
                    </td>

                    <td className="lifecycle-address">
                      {order.pickup_address}
                    </td>

                    <td className="lifecycle-address">
                      {order.delivery_address}
                    </td>

                    <td>
                      <OrderStatusBadge
                        status={order.status}
                      />
                    </td>

                    <td>
                      {order.trip_id
                        ? order.trip_id.slice(-8).toUpperCase()
                        : 'Not assigned'}
                    </td>

                    <td>
                      <button
                        type="button"
                        className="button button-outline"
                        onClick={() => handleView(order.id)}
                        disabled={loadingDetails}
                      >
                        View
                      </button>
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
              onClick={() => {
                setLoading(true)
                setPage((old) => old - 1)
              }}
            >
              Previous
            </button>

            <button
              type="button"
              className="button button-outline"
              disabled={loading || page >= totalPages}
              onClick={() => {
                setLoading(true)
                setPage((old) => old + 1)
              }}
            >
              Next
            </button>
          </div>
        </div>
      </section>

      {loadingDetails && (
        <section className="fleet-panel">
          Loading order details...
        </section>
      )}

      {selectedOrder && (
        <section className="fleet-panel">
          <div className="fleet-panel-header">
            <div>
              <h2>Order progress</h2>

              <p>{selectedOrder.reference_code}</p>
            </div>

            <button
              type="button"
              className="button button-outline"
              onClick={() => setSelectedOrder(null)}
            >
              Close
            </button>
          </div>

          <div className="lifecycle-details">
            <div>
              <span>Current status</span>

              <OrderStatusBadge
                status={selectedOrder.status}
              />
            </div>

            <div>
              <span>Assigned trip</span>

              <strong>
                {selectedOrder.trip_id
                  ? selectedOrder.trip_id
                  : 'Not yet dispatched'}
              </strong>
            </div>

            <div>
              <span>Created</span>

              <strong>
                {formatDateTime(
                  selectedOrder.created_at
                )}
              </strong>
            </div>

            <div>
              <span>Last status update</span>

              <strong>
                {formatDateTime(
                  selectedOrder.updated_at
                )}
              </strong>
            </div>
          </div>

          <h3 className="lifecycle-section-title">
            Delivery progress
          </h3>

          <LifecycleProgress
            status={selectedOrder.status}
          />

          <div className="lifecycle-addresses">
            <div>
              <span>Pickup address</span>

              <strong>
                {selectedOrder.pickup_address}
              </strong>
            </div>

            <div>
              <span>Delivery address</span>

              <strong>
                {selectedOrder.delivery_address}
              </strong>
            </div>
          </div>

          {canManage
            && selectedOrder.allowed_next_status
            && (
              <div className="lifecycle-actions">
                <button
                  type="button"
                  className="button button-primary"
                  disabled={busy}
                  onClick={() => {
                    handleStatusChange(selectedOrder)
                  }}
                >
                  {busy
                    ? 'Updating...'
                    : selectedOrder.allowed_next_status
                      === 'warehouse'
                      ? 'Move to Warehouse'
                      : 'Mark Out for Delivery'}
                </button>
              </div>
            )}

          {selectedOrder.status === 'warehouse'
            && !selectedOrder.trip_id
            && (
              <p className="lifecycle-note">
                This order is ready for F11 Dispatch
                Planning. Assign it to a trip before
                starting delivery.
              </p>
            )}

          {selectedOrder.status === 'out_for_delivery'
            && (
              <p className="lifecycle-note">
                Delivery completion requires the
                assigned Driver to submit a photo
                through F10 Delivery Proof.
              </p>
            )}

          {selectedOrder.status === 'delivered'
            && (
              <p className="lifecycle-note">
                This order has been delivered.
              </p>
            )}

          {(user?.role === 'customer'
            || user?.role === 'admin')
            && (
              <p className="lifecycle-note">
                This is a read-only order progress view.
              </p>
            )}
        </section>
      )}
    </section>
  )
}

export default OrderLifecyclePage