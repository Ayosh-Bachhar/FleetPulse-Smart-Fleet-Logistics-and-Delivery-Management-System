import { useEffect, useState } from 'react'
import { AuthContext } from './auth'

import {
  loginUser,
  getCurrentUser,
} from '../features/accounts/loginApi'

import { logoutUser } from '../features/accounts/logoutApi'


export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()

    async function restoreSession() {
      try {
        const currentUser = await getCurrentUser(
          controller.signal
        )

        if (!controller.signal.aborted) {
          setUser(currentUser)
        }
      } catch {
        if (!controller.signal.aborted) {
          setUser(null)
        }
      } finally {
        if (!controller.signal.aborted) {
          setAuthLoading(false)
        }
      }
    }

    restoreSession()

    return () => controller.abort()
  }, [])

  async function login(credentials) {
    const loggedInUser = await loginUser(credentials)

    setUser(loggedInUser)
    setAuthLoading(false)

    return loggedInUser
  }

  async function logout() {
    await logoutUser()
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        authLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}