import { useEffect, useState } from 'react'

import { useAuth } from '../../context/auth'

import {
  getOrders,
  getOrder,
} from './orderIntakeApi'

import OrderForm from './OrderForm'


const PAGE_SIZE = 10

const STATUS_LABELS = {
  placed: 'Placed',
  warehouse: 'Warehouse',
  out_for_delivery: 'Out for delivery',
  delivered: 'Delivered',
}


function formatDateTime(value) {
  if (!value) return '—'

  return new Date(value).toLocaleString()
}


function OrderIntakePage() {
  const { user } = useAuth()

  const isCustomer = user?.role === 'customer'
  const isDispatcher = user?.role === 'dispatcher'

  const canAccess = isCustomer || isDispatcher

  const [orders, setOrders] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const [creating, setCreating] = useState(false)
  const [selectedOrder, setSelectedOrder] = useState(null)

  const [loading, setLoading] = useState(true)
  const [loadingDetails, setLoadingDetails] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [reloadKey, setReloadKey] = useState(0)


  useEffect(() => {
    if (!canAccess) return

    const controller = new AbortController()

    async function loadOrders() {
      setLoading(true)

      try {
        const result = await getOrders(
          {
            search: search || undefined,
            status: statusFilter || undefined,
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
          const detail = err.response?.data?.detail

          setError(
            typeof detail === 'string'
              ? detail
              : 'Unable to load orders.'
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
    canAccess,
    search,
    statusFilter,
    page,
    reloadKey,
  ])


  function handleSearch(event) {
    event.preventDefault()

    setSearch(searchInput.trim())
    setPage(1)
    setError('')
  }


  function handleCreate() {
    setCreating(true)
    setSelectedOrder(null)
    setError('')
    setSuccess('')
  }


  function handleSaved(order) {
    setCreating(false)
    setSelectedOrder(order)

    setSuccess(
      `Order ${order.reference_code} placed successfully.`
    )

    setError('')
    setPage(1)
    setReloadKey((previous) => previous + 1)
  }


  async function handleView(orderId) {
    setError('')
    setSuccess('')
    setLoadingDetails(true)

    try {
      const order = await getOrder(orderId)

      setSelectedOrder(order)
      setCreating(false)

    } catch (err) {
      const detail = err.response?.data?.detail

      setError(
        typeof detail === 'string'
          ? detail
          : 'Unable to load order details.'
      )

    } finally {
      setLoadingDetails(false)
    }
  }


  const totalPages = Math.max(
    1,
    Math.ceil(total / PAGE_SIZE)
  )


  if (!canAccess) {
    return (
      <section className="workspace-welcome">
        <h1 className="workspace-heading">
          Access restricted
        </h1>

        <p className="workspace-description">
          Order Intake is available to
          Customers and Dispatchers.
        </p>
      </section>
    )
  }


  return (
    <section className="order-page">
      <div className="fleet-header">
        <div>
          <p className="workspace-eyebrow">
            DELIVERY OPERATIONS
          </p>

          <h1 className="workspace-heading">
            {isCustomer
              ? 'My Orders'
              : 'Order Intake'}
          </h1>

          <p className="workspace-description">
            {isCustomer
              ? 'Place and track the status of your delivery orders.'
              : 'Create delivery orders for registered customers and review incoming orders.'}
          </p>
        </div>

        <button
          type="button"
          className="button button-primary"
          onClick={handleCreate}
        >
          + Place order
        </button>
      </div>

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

      {creating && (
        <OrderForm
          isDispatcher={isDispatcher}
          onSaved={handleSaved}
          onCancel={() => setCreating(false)}
        />
      )}

      <section className="fleet-panel">
        <div className="fleet-panel-header">
          <div>
            <h2>
              {isCustomer
                ? 'My delivery orders'
                : 'Customer orders'}
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
              placeholder="Search reference or address..."
              aria-label="Search orders"
              value={searchInput}
              onChange={(event) => {
                setSearchInput(event.target.value)
              }}
              maxLength={100}
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
            }}
          >
            <option value="">All statuses</option>
            <option value="placed">Placed</option>
            <option value="warehouse">Warehouse</option>
            <option value="out_for_delivery">
              Out for delivery
            </option>
            <option value="delivered">Delivered</option>
          </select>
        </div>

        <div className="fleet-table-container">
          <table className="fleet-table order-table">
            <thead>
              <tr>
                <th>Reference</th>

                {isDispatcher && (
                  <th>Customer</th>
                )}

                <th>Pickup</th>
                <th>Delivery</th>
                <th>Weight</th>
                <th>Rush</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td
                    colSpan={isDispatcher ? 8 : 7}
                    className="fleet-empty"
                  >
                    Loading orders...
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td
                    colSpan={isDispatcher ? 8 : 7}
                    className="fleet-empty"
                  >
                    No orders found.
                  </td>
                </tr>
              ) : (
                orders.map((order) => (
                  <tr key={order.id}>
                    <td>
                      <strong>
                        {order.reference_code}
                      </strong>

                      <small className="order-date">
                        {formatDateTime(order.created_at)}
                      </small>
                    </td>

                    {isDispatcher && (
                      <td>
                        <strong>
                          {order.customer_name}
                        </strong>

                        <small className="order-date">
                          {order.customer_email}
                        </small>
                      </td>
                    )}

                    <td className="order-address">
                      {order.pickup_address}
                    </td>

                    <td className="order-address">
                      {order.delivery_address}
                    </td>

                    <td>
                      {order.weight_kg} kg
                    </td>

                    <td>
                      {order.is_rush
                        ? 'Yes'
                        : 'No'}
                    </td>

                    <td>
                      <span
                        className={
                          `order-status order-status-${order.status}`
                        }
                      >
                        {STATUS_LABELS[order.status]
                          || order.status}
                      </span>
                    </td>

                    <td>
                      <button
                        type="button"
                        className="button button-outline"
                        disabled={loadingDetails}
                        onClick={() => handleView(order.id)}
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
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>

            <button
              type="button"
              className="button button-outline"
              disabled={
                loading
                || page >= totalPages
              }
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>

      {loadingDetails && (
        <div className="fleet-panel">
          Loading order details...
        </div>
      )}

      {selectedOrder && (
        <section className="fleet-panel">
          <div className="fleet-panel-header">
            <div>
              <h2>Order details</h2>

              <p>
                {selectedOrder.reference_code}
              </p>
            </div>

            <button
              type="button"
              className="button button-outline"
              onClick={() => setSelectedOrder(null)}
            >
              Close
            </button>
          </div>

          <div className="order-details-grid">
            <div>
              <span>Customer</span>
              <strong>
                {selectedOrder.customer_name}
              </strong>
            </div>

            <div>
              <span>Customer email</span>
              <strong>
                {selectedOrder.customer_email}
              </strong>
            </div>

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

            <div>
              <span>Package weight</span>
              <strong>
                {selectedOrder.weight_kg} kg
              </strong>
            </div>

            <div>
              <span>Package dimensions</span>
              <strong>
                {selectedOrder.length_cm}
                {' × '}
                {selectedOrder.width_cm}
                {' × '}
                {selectedOrder.height_cm} cm
              </strong>
            </div>

            <div>
              <span>Package volume</span>
              <strong>
                {selectedOrder.volume_m3} m³
              </strong>
            </div>

            <div>
              <span>Rush delivery</span>
              <strong>
                {selectedOrder.is_rush ? 'Yes' : 'No'}
              </strong>
            </div>

            <div>
              <span>Order status</span>
              <strong>
                {STATUS_LABELS[selectedOrder.status]}
              </strong>
            </div>

            <div>
              <span>Created at</span>
              <strong>
                {formatDateTime(selectedOrder.created_at)}
              </strong>
            </div>

            <div>
              <span>Assigned trip</span>
              <strong>
                {selectedOrder.trip_id
                  ? selectedOrder.trip_id
                  : 'Not assigned'}
              </strong>
            </div>

            <div>
              <span>Tracking identifier</span>
              <strong className="order-tracking-id">
                {selectedOrder.public_tracking_uuid}
              </strong>
            </div>
          </div>

          <p className="order-form-note">
            Order status updates will be managed by
            F9 Order Lifecycle. Public tracking links
            will be implemented by F17.
          </p>
        </section>
      )}
    </section>
  )
}

export default OrderIntakePage