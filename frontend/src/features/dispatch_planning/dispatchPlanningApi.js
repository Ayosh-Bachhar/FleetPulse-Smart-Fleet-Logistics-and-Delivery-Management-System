import apiClient from '../../api/apiClient'

const TRIPS_URL = '/api/v1/trips'


async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}


export async function getTrips(params = {}, signal) {
  const response = await apiClient.get(TRIPS_URL, {
    params,
    signal,
  })

  return response.data
}


export async function getTrip(tripId) {
  const response = await apiClient.get(
    `${TRIPS_URL}/${tripId}`
  )

  return response.data
}


export async function getEligibleOrders(
  params = {},
  signal
) {
  const response = await apiClient.get(
    `${TRIPS_URL}/eligible-orders`,
    {
      params,
      signal,
    }
  )

  return response.data
}


export async function createDispatch(data) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    TRIPS_URL,
    data,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function completeTrip(
  tripId,
  actualDistanceKm = null
) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${TRIPS_URL}/${tripId}/complete`,
    {
      actual_distance_km: actualDistanceKm,
    },
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function cancelTrip(tripId) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${TRIPS_URL}/${tripId}/cancel`,
    {},
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}