const STATUS_LABELS = {
  placed: 'Placed',
  warehouse: 'Warehouse',
  out_for_delivery: 'Out for Delivery',
  delivered: 'Delivered',
}


function OrderStatusBadge({ status }) {
  return (
    <span
      className={`lifecycle-badge lifecycle-badge-${status}`}
    >
      {STATUS_LABELS[status] || status}
    </span>
  )
}


export default OrderStatusBadge