import { Navigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
      </div>
    );
  }

  if (!user) {
    return (
      <section className="hero">
        <h1>🏺 Enchères Scellées</h1>
        <p className="tagline">
          Plateforme d'enchères intelligente — IA + Blockchain + Smart Contracts
        </p>
        <div className="features">
          <div className="feature">
            <span className="icon">🤖</span>
            <h3>IA</h3>
            <p>Authentification • Estimation de prix</p>
          </div>
          <div className="feature">
            <span className="icon">⛓️</span>
            <h3>Blockchain</h3>
            <p>Smart Contract • Prix chiffré et sécurisé</p>
          </div>
          <div className="feature">
            <span className="icon">🏆</span>
            <h3>Enchères</h3>
            <p>Scellées, sécurisées • Remboursement auto</p>
          </div>
        </div>
        <div className="hero-actions">
          <Link to="/login" className="cta">Se connecter</Link>
          <Link to="/register" className="cta secondary">S'inscrire</Link>
        </div>
      </section>
    );
  }

  if (user.role === 'seller') {
    return <Navigate to="/seller/dashboard" replace />;
  }

  return <Navigate to="/buyer/catalog" replace />;
}
