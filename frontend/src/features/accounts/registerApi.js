import apiClient from '../../api/apiClient'

export async function registerCustomer(userData) {
  const response = await apiClient.post(
    '/api/v1/accounts/register',
    userData
  )

  return response.data
}