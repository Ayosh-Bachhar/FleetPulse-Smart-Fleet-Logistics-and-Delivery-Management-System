import apiClient from '../../api/apiClient'

const MAINTENANCE_URL = '/api/v1/maintenance'


async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}


export async function getMaintenanceList(
  params = {},
  signal
) {
  const response = await apiClient.get(
    MAINTENANCE_URL,
    { params, signal }
  )

  return response.data
}


export async function getMaintenance(vehicleId) {
  const response = await apiClient.get(
    `${MAINTENANCE_URL}/${vehicleId}`
  )

  return response.data
}


export async function getMaintenanceHistory(
  vehicleId,
  page = 1
) {
  const response = await apiClient.get(
    `${MAINTENANCE_URL}/${vehicleId}/history`,
    {
      params: {
        page,
        page_size: 20,
      },
    }
  )

  return response.data
}


export async function addVehicleDistance(
  vehicleId,
  data
) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${MAINTENANCE_URL}/${vehicleId}/distance`,
    data,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function changeServiceInterval(
  vehicleId,
  data
) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.patch(
    `${MAINTENANCE_URL}/${vehicleId}/interval`,
    data,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function completeVehicleService(
  vehicleId,
  data
) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    `${MAINTENANCE_URL}/${vehicleId}/complete-service`,
    data,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}