import apiClient from '../../api/apiClient'

const GPS_URL = '/api/v1/gps/trips'


async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}


export async function getGpsTrips(
  params = {},
  signal
) {
  const response = await apiClient.get(
    GPS_URL,
    {
      params,
      signal,
    }
  )

  return response.data
}


export async function getGpsPosition(
  tripId,
  signal
) {
  const response = await apiClient.get(
    `${GPS_URL}/${tripId}`,
    { signal }
  )

  return response.data
}


export async function startGpsSimulation(
  tripId,
  speedKmh
) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${GPS_URL}/${tripId}/start`,
    { speed_kmh: speedKmh },
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function pauseGpsSimulation(tripId) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${GPS_URL}/${tripId}/pause`,
    {},
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function resetGpsSimulation(tripId) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${GPS_URL}/${tripId}/reset`,
    {},
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}