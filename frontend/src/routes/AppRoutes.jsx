import {
  BrowserRouter,
  Routes,
  Route,
} from 'react-router-dom'

import App from '../App'

import RegisterPage from '../features/accounts/RegisterPage'
import LoginPage from '../features/accounts/LoginPage'
import ForgotPasswordPage from '../features/accounts/ForgotPasswordPage'
import ResetPasswordPage from '../features/accounts/ResetPasswordPage'

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/forgot-password"
          element={<ForgotPasswordPage />}
        />
        <Route
          path="/reset-password"
          element={<ResetPasswordPage />}
        />
      </Routes>
    </BrowserRouter>
  )
}

export default AppRoutes