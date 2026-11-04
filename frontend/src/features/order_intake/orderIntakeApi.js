import apiClient from '../../api/apiClient'

const ORDERS_URL = '/api/v1/orders'


async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}


export async function getOrders(
  params = {},
  signal
) {
  const response = await apiClient.get(
    ORDERS_URL,
    {
      params,
      signal,
    }
  )

  return response.data
}


export async function getOrder(orderId) {
  const response = await apiClient.get(
    `${ORDERS_URL}/${orderId}`
  )

  return response.data
}


export async function createOrder(orderData) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    ORDERS_URL,
    orderData,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}