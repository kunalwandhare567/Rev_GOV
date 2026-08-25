import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { STORAGE_KEYS, ROLES } from '../utils/constants'

const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,

      // Citizen specific state
      citizenToken: null,
      citizenUser: null, // { citizen_id, name, email, phone, address }
      isCitizenAuthenticated: false,

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

      setCitizenAuth: (token, citizenUser) => {
        localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, token)
        localStorage.setItem(STORAGE_KEYS.AUTH_USER, JSON.stringify(citizenUser))
        
        // Purge old user session and chat store state
        localStorage.removeItem(STORAGE_KEYS.SESSION_ID)
        localStorage.removeItem(STORAGE_KEYS.CITIZEN_IDENTIFIER)
        if (citizenUser?.citizen_id) {
          localStorage.setItem(STORAGE_KEYS.CITIZEN_IDENTIFIER, citizenUser.citizen_id)
        }

        set({
          token,
          user: citizenUser,
          isAuthenticated: true,
          citizenToken: token,
          citizenUser,
          isCitizenAuthenticated: true,
        })
      },

      updateCitizenUser: (updatedFields) => {
        set((state) => {
          const newCitizenUser = { ...state.citizenUser, ...updatedFields }
          const newUser = { ...state.user, ...updatedFields }
          localStorage.setItem(STORAGE_KEYS.AUTH_USER, JSON.stringify(newCitizenUser))
          return { citizenUser: newCitizenUser, user: newUser }
        })
      },

      clearCitizenAuth: () => {
        localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN)
        localStorage.removeItem(STORAGE_KEYS.AUTH_USER)
        localStorage.removeItem(STORAGE_KEYS.SESSION_ID)
        localStorage.removeItem(STORAGE_KEYS.CITIZEN_IDENTIFIER)
        set({
          token: null,
          user: null,
          isAuthenticated: false,
          citizenToken: null,
          citizenUser: null,
          isCitizenAuthenticated: false,
        })
      },

      isAdmin:   () => get().user?.role === ROLES.ADMIN,
      isOfficer: () => [ROLES.ADMIN, ROLES.OFFICER].includes(get().user?.role),
      isCitizen: () => get().isCitizenAuthenticated || get().user?.role === 'CITIZEN',
    }),
    {
      name: 'rsp-auth',
      partialize: (s) => ({
        token: s.token,
        user: s.user,
        isAuthenticated: s.isAuthenticated,
        citizenToken: s.citizenToken,
        citizenUser: s.citizenUser,
        isCitizenAuthenticated: s.isCitizenAuthenticated,
      }),
    }
  )
)

export default useAuthStore
