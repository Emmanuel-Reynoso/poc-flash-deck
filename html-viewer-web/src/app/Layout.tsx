import { Link, Outlet } from 'react-router-dom';
import { logoutUrl } from '../auth/api';
import { usePrincipal } from '../auth/AuthGate';

export function Layout() {
  const principal = usePrincipal();
  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <img src="/favicon.svg" alt="" width={22} height={22} />
          Visor HTML
        </Link>
        <div className="topbar__user">
          <span className="muted small">{principal?.userDetails}</span>
          <a href={logoutUrl} className="btn btn--ghost">
            Salir
          </a>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
