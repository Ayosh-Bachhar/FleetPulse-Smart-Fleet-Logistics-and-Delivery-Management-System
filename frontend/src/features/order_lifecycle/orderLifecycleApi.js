import apiClient from '../../api/apiClient'

const URL = '/api/v1/order-lifecycle/orders'


async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}


export async function getLifecycleOrders(
  params = {},
  signal
) {
  const response = await apiClient.get(URL, {
    params,
    signal,
  })

  return response.data
}


export async function getLifecycleOrder(orderId) {
  const response = await apiClient.get(
    `${URL}/${orderId}`
  )

  return response.data
}


export async function updateOrderStatus(
  orderId,
  nextStatus
) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.patch(
    `${URL}/${orderId}/status`,
    { status: nextStatus },
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}