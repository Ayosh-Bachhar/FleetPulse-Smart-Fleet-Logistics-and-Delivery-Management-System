import apiClient from '../../api/apiClient'

const TRIPS_URL = '/api/v1/trips'


async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}


export async function getSavedSequence(tripId) {
  const response = await apiClient.get(
    `${TRIPS_URL}/${tripId}/stop-sequence`
  )

  return response.data
}


export async function previewSequence(tripId) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${TRIPS_URL}/${tripId}/stop-sequence/preview`,
    {},
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
      timeout: 60000,
    }
  )

  return response.data
}


export async function applySequence(
  tripId,
  token
) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${TRIPS_URL}/${tripId}/stop-sequence/apply`,
    {
      preview_token: token,
    },
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
      timeout: 60000,
    }
  )

  return response.data
}