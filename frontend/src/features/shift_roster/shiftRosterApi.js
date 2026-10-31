import apiClient from '../../api/apiClient'

const SHIFTS_URL = '/api/v1/shifts'


async function getCsrfToken() {
  const response = await apiClient.get(
    '/api/v1/accounts/csrf'
  )

  return response.data.csrf_token
}


export async function getShifts(params = {}, signal) {
  const response = await apiClient.get(SHIFTS_URL, {
    params,
    signal,
  })

  return response.data
}


export async function getShift(shiftId) {
  const response = await apiClient.get(
    `${SHIFTS_URL}/${shiftId}`
  )

  return response.data
}


export async function createShift(shiftData) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.post(
    SHIFTS_URL,
    shiftData,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function updateShift(shiftId, shiftData) {
  const csrfToken = await getCsrfToken()

  const response = await apiClient.patch(
    `${SHIFTS_URL}/${shiftId}`,
    shiftData,
    {
      headers: {
        'X-CSRF-Token': csrfToken,
      },
    }
  )

  return response.data
}


export async function checkShiftHolidays(
  startAt,
  endAt
) {
  const response = await apiClient.get(
    `${SHIFTS_URL}/holiday-check`,
    {
      params: {
        start_at: startAt,
        end_at: endAt,
      },
    }
  )

  return response.data
}