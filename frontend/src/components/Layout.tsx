import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

export function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/');
  }

  return (
    <div className="layout">
      <header className="header">
        <Link to="/" className="logo">🏺 Enchères Scellées</Link>
        <nav>
          <button type="button" className="theme-toggle" onClick={toggleTheme} aria-label="Changer le thème">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          {user ? (
            <>
              {user.role === 'seller' && (
                <>
                  <Link to="/seller/dashboard">Mes ventes</Link>
                  <Link to="/seller/upload">Vendre</Link>
                </>
              )}
              {user.role === 'buyer' && (
                <Link to="/buyer/catalog">Enchères</Link>
              )}
              <span className="user-email">{user.email}</span>
              <button type="button" className="btn-logout" onClick={handleLogout}>
                Déconnexion
              </button>
            </>
          ) : (
            <>
              <Link to="/login">Connexion</Link>
              <Link to="/register">Inscription</Link>
            </>
          )}
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
      <footer className="footer">
        Plateforme d'enchères intelligente — IA + Blockchain — Enchères scellées
      </footer>
    </div>
  );
}
