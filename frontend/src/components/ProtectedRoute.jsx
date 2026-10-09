import { Navigate, useLocation } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '../api/AuthContext';

/**
 * Wraps a page that requires authentication.
 * - If not logged in -> redirect to /login
 * - If `allowedRoles` is given and the user's role isn't in it -> render Access Denied
 */
export default function ProtectedRoute({ children, allowedRoles }) {
  const { isAuthenticated, role, loading } = useAuth();
  const location = useLocation();

  if (loading) return <p role="status">Checking session…</p>;

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && !allowedRoles.includes(role)) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-50">
          <ShieldAlert className="h-7 w-7 text-red-600" />
        </div>
        <h2 className="text-lg font-bold text-ink">Access Denied</h2>
        <p className="max-w-sm text-sm text-ink-muted">
          Your role <span className="font-semibold text-navy-700">({role || 'unknown'})</span>{' '}
          does not have permission to view this page. This block is enforced on the client to
          mirror the role check performed by the API.
        </p>
      </div>
    );
  }

  return children;
}
