import apiClient from '../../api/apiClient'

const TRIPS_URL = '/api/v1/trips'


async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}


export async function getTripRoute(tripId) {
  const response = await apiClient.get(
    `${TRIPS_URL}/${tripId}/route`
  )

  return response.data
}


export async function getTripRouteStatus(tripId) {
  const response = await apiClient.get(
    `${TRIPS_URL}/${tripId}/route/status`
  )

  return response.data
}


export async function calculateTripRoute(
  tripId,
  refresh = false
) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${TRIPS_URL}/${tripId}/route`,
    {},
    {
      params: { refresh },
      headers: {
        'X-CSRF-Token': csrfToken,
      },
      timeout: 60000,
    }
  )

  return response.data
}