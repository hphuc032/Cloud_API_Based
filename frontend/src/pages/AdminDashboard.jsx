import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Package,
  ClipboardList,
  UserCog,
  ShieldCheck,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import AppLayout from '../components/AppLayout';
import { useAuth } from '../api/AuthContext';
import {
  getApiErrorMessage,
  getOrders,
  getProducts,
  getUserDisplayName,
  unwrapItems,
} from '../api/api';

const ROLE_BADGE = {
  staff: 'badge-staff',
  admin: 'badge-admin',
};

export default function AdminDashboard() {
  const { user, role } = useAuth();
  const [stats, setStats] = useState({
    products: { value: null, error: '' },
    orders: { value: null, error: '' },
  });

  useEffect(() => {
    Promise.allSettled([getProducts(), getOrders()]).then(([productsResult, ordersResult]) => {
      setStats({
        products:
          productsResult.status === 'fulfilled'
            ? { value: unwrapItems(productsResult.value).length, error: '' }
            : { value: '-', error: getApiErrorMessage(productsResult.reason, 'Products unavailable') },
        orders:
          ordersResult.status === 'fulfilled'
            ? { value: unwrapItems(ordersResult.value).length, error: '' }
            : { value: '-', error: getApiErrorMessage(ordersResult.reason, 'Orders unavailable') },
      });
    });
  }, []);

  const roleKey = (role || '').toLowerCase();
  const displayName = getUserDisplayName(user) || 'team member';

  return (
    <AppLayout>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-ink">Welcome back, {displayName}</h1>
            <span className={ROLE_BADGE[roleKey] || 'badge bg-navy-50 text-navy-700'}>
              {role}
            </span>
          </div>
          <p className="text-sm text-ink-muted">
            You have elevated permissions to manage the catalog and review orders.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="card p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-muted">Products in catalog</span>
            <Package className="h-4 w-4 text-navy-700" />
          </div>
          <p className="mt-2 text-2xl font-bold text-navy-700">
            {stats.products.value === null ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              stats.products.value
            )}
          </p>
          {stats.products.error && (
            <p className="mt-1 text-xs font-medium text-amber-700">{stats.products.error}</p>
          )}
        </div>
        <div className="card p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-muted">Visible orders</span>
            <ClipboardList className="h-4 w-4 text-sage-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-sage-600">
            {stats.orders.value === null ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              stats.orders.value
            )}
          </p>
          {stats.orders.error && (
            <p className="mt-1 text-xs font-medium text-amber-700">{stats.orders.error}</p>
          )}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link to="/products" className="card flex items-center gap-3 p-4 transition-shadow hover:shadow-cardHover">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-navy-50">
            <Package className="h-5 w-5 text-navy-700" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">Manage Products</p>
            <p className="text-xs text-ink-muted">Create, update, delete</p>
          </div>
        </Link>
        <Link to="/orders" className="card flex items-center gap-3 p-4 transition-shadow hover:shadow-cardHover">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sage-50">
            <ClipboardList className="h-5 w-5 text-sage-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">View Orders</p>
            <p className="text-xs text-ink-muted">All orders visible to your role</p>
          </div>
        </Link>
        <Link to="/security-center" className="card flex items-center gap-3 p-4 transition-shadow hover:shadow-cardHover">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-bloom-50">
            <ShieldCheck className="h-5 w-5 text-bloom-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">Security Center</p>
            <p className="text-xs text-ink-muted">Test API protections live</p>
          </div>
        </Link>
      </div>

      <div className="mt-6 card p-5">
        <div className="mb-3 flex items-center gap-2">
          <UserCog className="h-4 w-4 text-navy-700" />
          <h3 className="text-sm font-bold text-ink">Your account</h3>
        </div>
        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-ink-muted">Email</dt>
            <dd className="font-medium text-ink">{user?.email || '-'}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Username</dt>
            <dd className="font-medium text-ink">{user?.username || '-'}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Role</dt>
            <dd className="font-medium text-ink">{role || '-'}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Access level</dt>
            <dd className="flex items-center gap-1 font-medium text-sage-600">
              Elevated <ArrowRight className="h-3 w-3" />
            </dd>
          </div>
        </dl>
      </div>
    </AppLayout>
  );
}
