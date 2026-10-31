import { useAuth } from '../context/auth'
import LogoutButton from '../features/accounts/LogoutButton'

function Navbar() {
  const { user } = useAuth()

  return (
    <header className="workspace-topbar">
      <h2 className="workspace-topbar-title">
        FleetPulse Workspace
      </h2>

      <div className="workspace-account">
        <span className="workspace-account-name">
          {user?.full_name}
        </span>

        <LogoutButton />
      </div>
    </header>
  )
}

export default Navbar