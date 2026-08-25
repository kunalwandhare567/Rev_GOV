import { Navigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { ROLES } from '../utils/constants'

export default function AuthGuard({ children, requiredRole }) {
  const { isAuthenticated, isCitizenAuthenticated, user } = useAuthStore()

  if (requiredRole === 'CITIZEN') {
    if (!isCitizenAuthenticated && !user) {
      return <Navigate to="/login" replace />
    }
    return children
  }


  if (!isAuthenticated || !user) {
    const loginPath = requiredRole === ROLES.ADMIN ? '/admin/login' : '/officer/login'
    return <Navigate to={loginPath} replace />
  }

  if (requiredRole === ROLES.ADMIN && user.role !== ROLES.ADMIN) {
    return <Navigate to="/admin/login" replace />
  }

  if (requiredRole === ROLES.OFFICER && ![ROLES.ADMIN, ROLES.OFFICER].includes(user.role)) {
    return <Navigate to="/officer/login" replace />
  }

  return children
}
