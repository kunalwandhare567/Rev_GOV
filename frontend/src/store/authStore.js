import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { STORAGE_KEYS, ROLES } from '../utils/constants'

const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,

      setAuth: (token, user) => {
        localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, token)
        localStorage.setItem(STORAGE_KEYS.AUTH_USER, JSON.stringify(user))
        set({ token, user, isAuthenticated: true })
      },

      clearAuth: () => {
        localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN)
        localStorage.removeItem(STORAGE_KEYS.AUTH_USER)
        set({ token: null, user: null, isAuthenticated: false })
      },

      isAdmin:   () => get().user?.role === ROLES.ADMIN,
      isOfficer: () => [ROLES.ADMIN, ROLES.OFFICER].includes(get().user?.role),
    }),
    {
      name: 'rsp-auth',
      partialize: (s) => ({ token: s.token, user: s.user, isAuthenticated: s.isAuthenticated }),
    }
  )
)

export default useAuthStore
