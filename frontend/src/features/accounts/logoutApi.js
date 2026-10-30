import apiClient from '../../api/apiClient'

export async function logoutUser() {
  const csrfResponse = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  const csrfToken = csrfResponse.data.csrf_token

  const response = await apiClient.post(
    '/api/v1/accounts/logout',
    {},
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}