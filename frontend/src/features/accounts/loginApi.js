import apiClient from '../../api/apiClient'

export async function loginUser(credentials) {
  const response = await apiClient.post(
    '/api/v1/accounts/login',
    credentials
  )

  return response.data
}

export async function getCurrentUser(signal) {
  const response = await apiClient.get(
    '/api/v1/accounts/me',
    { signal }
  )

  return response.data
}