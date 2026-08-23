import axios from 'axios'
import { STORAGE_KEYS } from '../utils/constants'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN)
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error)
)

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN)
      localStorage.removeItem(STORAGE_KEYS.AUTH_USER)
      window.dispatchEvent(new Event('auth:expired'))
    }
    const detail = error.response?.data?.detail || error.message || 'Request failed'
    return Promise.reject(new Error(detail))
  }
)

export default client
