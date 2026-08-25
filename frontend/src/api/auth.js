import client from './client'

export const login = (username, password) => {
  const form = new URLSearchParams()
  form.append('username', username)
  form.append('password', password)
  return client.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
}

export const registerCitizen = (data) => client.post('/auth/citizen/register', data)
export const loginCitizen = (data) => client.post('/auth/citizen/login', data)
export const getCitizenProfile = () => client.get('/auth/citizen/profile')
export const updateCitizenProfile = (data) => client.patch('/auth/citizen/profile', data)

export const getMe = () => client.get('/auth/me')
export const logout = () => client.post('/auth/logout')
