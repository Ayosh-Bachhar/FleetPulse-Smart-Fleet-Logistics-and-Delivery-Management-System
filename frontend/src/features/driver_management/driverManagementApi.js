import apiClient from '../../api/apiClient'

const DRIVERS_URL = '/api/v1/drivers'

async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}


export async function getDrivers(params = {}, signal) {
  const response = await apiClient.get(DRIVERS_URL, {
    params,
    signal,
  })

  return response.data
}


export async function getDriver(driverId) {
  const response = await apiClient.get(
    `${DRIVERS_URL}/${driverId}`
  )

  return response.data
}


export async function createDriver(driverData) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    DRIVERS_URL,
    driverData,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function updateDriver(driverId, driverData) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.patch(
    `${DRIVERS_URL}/${driverId}`,
    driverData,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function checkDriverCompatibility(
  driverId,
  vehicleId
) {
  const response = await apiClient.get(
    `${DRIVERS_URL}/${driverId}/compatibility/${vehicleId}`
  )

  return response.data
}