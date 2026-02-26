import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

type Role = 'seller' | 'buyer';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireRole?: Role;
}

export function ProtectedRoute({ children, requireRole }: ProtectedRouteProps) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p>Chargement…</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireRole && user.role !== requireRole) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
