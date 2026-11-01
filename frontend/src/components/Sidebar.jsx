import { Link, NavLink } from 'react-router-dom'

import { useAuth } from '../context/auth'


function Sidebar() {
  const { user } = useAuth()

  const canManageOperations = (
    user?.role === 'admin'
    || user?.role === 'dispatcher'
  )

  const navClass = ({ isActive }) =>
    `workspace-navlink ${isActive ? 'is-active' : ''}`

  return (
    <aside className="workspace-sidebar">
      <Link
        to="/dashboard"
        className="brand workspace-brand"
      >
        <span className="brand-symbol">
          F
        </span>

        FleetPulse
      </Link>

      <nav
        className="workspace-nav"
        aria-label="Dashboard navigation"
      >
        <span className="workspace-nav-label">
          WORKSPACE
        </span>

        <NavLink
          to="/dashboard"
          end
          className={navClass}
        >
          Dashboard
        </NavLink>

        {canManageOperations && (
          <>
            <NavLink
              to="/fleet"
              className={navClass}
            >
              Fleet Management
            </NavLink>

            <NavLink
              to="/drivers"
              className={navClass}
            >
              Driver Management
            </NavLink>

            <NavLink
              to="/shifts"
              className={navClass}
            >
              Shift Roster
            </NavLink>

            <NavLink
              to="/maintenance"
              className={navClass}
            >
              Maintenance Alerts
            </NavLink>

            <NavLink
              to="/dispatch"
              className={navClass}
            >
              Dispatch Planning
            </NavLink>

            <NavLink
              to="/routes"
              className={navClass}
            >
              Route Distance & Time
            </NavLink>

            <NavLink
              to="/stop-sequencing"
              className={navClass}
            >
              Stop Sequencing
            </NavLink>


          </>
        )}

        <Link
          to="/"
          className="workspace-navlink"
        >
          Homepage
        </Link>
      </nav>

      <div className="workspace-sidebar-footer">
        <span className="workspace-nav-label">
          ACCOUNT ROLE
        </span>

        <strong className="workspace-role">
          {user?.role || 'User'}
        </strong>
      </div>
    </aside>
  )
}

export default Sidebar