import apiClient from '../../api/apiClient'

const VEHICLES_URL = '/api/v1/vehicles'

async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}

export async function getVehicles(params = {}, signal) {
  const response = await apiClient.get(VEHICLES_URL, {
    params,
    signal,
  })

  return response.data
}

export async function getVehicle(vehicleId) {
  const response = await apiClient.get(
    `${VEHICLES_URL}/${vehicleId}`
  )

  return response.data
}

export async function createVehicle(vehicleData) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    VEHICLES_URL,
    vehicleData,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}

export async function updateVehicle(
  vehicleId,
  vehicleData
) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.patch(
    `${VEHICLES_URL}/${vehicleId}`,
    vehicleData,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}