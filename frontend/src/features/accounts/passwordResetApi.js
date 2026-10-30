import apiClient from '../../api/apiClient'

export async function requestPasswordReset(email) {
  const response = await apiClient.post(
    '/api/v1/accounts/forgot-password',
    { email }
  )

  return response.data
}

export async function completePasswordReset(
  token,
  newPassword
) {
  const response = await apiClient.post(
    '/api/v1/accounts/reset-password',
    {
      token,
      new_password: newPassword,
    }
  )

  return response.data
}