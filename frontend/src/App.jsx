import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './api/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

import Login from './pages/Login';
import CustomerDashboard from './pages/CustomerDashboard';
import AdminDashboard from './pages/AdminDashboard';
import Products from './pages/Products';
import Orders from './pages/Orders';
import Profile from './pages/Profile';
import SecurityCenter from './pages/SecurityCenter';
import Monitoring from './pages/Monitoring';

function RoleHome() {
  const { role } = useAuth();
  const roleKey = (role || '').toLowerCase();
  return (
    <Navigate to={roleKey === 'customer' ? '/customer-dashboard' : '/admin-dashboard'} replace />
  );
}

function IdentityCallback() {
  const {loading,isAuthenticated}=useAuth();
  if(loading)return <p role="status">Completing sign-in…</p>;
  return <Navigate to={isAuthenticated?'/':'/login'} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/oidc/callback" element={<IdentityCallback />} />

          <Route
            path="/"
            element={
              <ProtectedRoute>
                <RoleHome />
              </ProtectedRoute>
            }
          />

          <Route
            path="/customer-dashboard"
            element={
              <ProtectedRoute allowedRoles={['customer']}>
                <CustomerDashboard />
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin-dashboard"
            element={
              <ProtectedRoute allowedRoles={['staff', 'admin']}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />

          <Route
            path="/products"
            element={
              <ProtectedRoute>
                <Products />
              </ProtectedRoute>
            }
          />

          <Route
            path="/orders"
            element={
              <ProtectedRoute>
                <Orders />
              </ProtectedRoute>
            }
          />

          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />

          <Route
            path="/security-center"
            element={
              <ProtectedRoute>
                <SecurityCenter />
              </ProtectedRoute>
            }
          />

          <Route
            path="/monitoring"
            element={
              <ProtectedRoute>
                <Monitoring />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
