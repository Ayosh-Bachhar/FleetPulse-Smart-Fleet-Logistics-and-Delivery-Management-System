import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom'

import { useAuth } from '../context/auth'

import App from '../App'
import MainLayout from '../layouts/MainLayout'
import ProtectedRoute from './ProtectedRoute'

import RegisterPage from '../features/accounts/RegisterPage'
import LoginPage from '../features/accounts/LoginPage'
import ForgotPasswordPage from '../features/accounts/ForgotPasswordPage'
import ResetPasswordPage from '../features/accounts/ResetPasswordPage'

import FleetManagementPage from '../features/fleet_management/FleetManagementPage'
import DriverManagementPage from '../features/driver_management/DriverManagementPage'
import ShiftRosterPage from '../features/shift_roster/ShiftRosterPage'
import MaintenanceAlertsPage from '../features/maintenance_alerts/MaintenanceAlertsPage'
import DispatchPlanningPage from '../features/dispatch_planning/DispatchPlanningPage'
import RouteDistanceAndTimePage from '../features/route_distance_and_time/RouteDistanceAndTimePage'
import StopSequencingPage from '../features/stop_sequencing/StopSequencingPage'
import SimulationControlPage from '../features/simulated_gps/SimulationControlPage'

function LoginRoute() {
  const { user, authLoading } = useAuth()

  if (!authLoading && user) {
    return <Navigate to="/dashboard" replace />
  }

  return <LoginPage />
}


function DashboardWelcome() {
  const { user } = useAuth()

  return (
    <section className="workspace-welcome">
      <p className="workspace-eyebrow">
        DASHBOARD
      </p>

      <h1 className="workspace-heading">
        Welcome, {user?.full_name}.
      </h1>

      <p className="workspace-description">
        Your FleetPulse workspace is ready.
        Fleet management, driver operations, shift scheduling,
        and other features are being implemented.
      </p>

      <div className="workspace-info-card">
        <h2>Account information</h2>

        <div className="workspace-info-row">
          <span>Name</span>
          <strong>{user?.full_name}</strong>
        </div>

        <div className="workspace-info-row">
          <span>Email</span>
          <strong>{user?.email}</strong>
        </div>

        <div className="workspace-info-row">
          <span>Role</span>
          <strong>{user?.role}</strong>
        </div>
      </div>
    </section>
  )
}


function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<App />}
        />

        <Route
          path="/register"
          element={<RegisterPage />}
        />

        <Route
          path="/login"
          element={<LoginRoute />}
        />

        <Route
          path="/forgot-password"
          element={<ForgotPasswordPage />}
        />

        <Route
          path="/reset-password"
          element={<ResetPasswordPage />}
        />

        <Route element={<ProtectedRoute />}>
          <Route element={<MainLayout />}>

            <Route
              path="/maintenance"
              element={<MaintenanceAlertsPage />}
            />

            <Route
              path="/dashboard"
              element={<DashboardWelcome />}
            />

            <Route
              path="/fleet"
              element={<FleetManagementPage />}
            />

            <Route
              path="/drivers"
              element={<DriverManagementPage />}
            />

            <Route
              path="/shifts"
              element={<ShiftRosterPage />}
            />

            <Route
              path="/dispatch"
              element={<DispatchPlanningPage />}
            />

            <Route
              path="/routes"
              element={<RouteDistanceAndTimePage />}
            />

            <Route
              path="/stop-sequencing"
              element={<StopSequencingPage />}
            />

            <Route
              path="/gps-simulation"
              element={<SimulationControlPage />}
            />

          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default AppRoutes