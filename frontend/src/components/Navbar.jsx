import { NavLink, useNavigate } from 'react-router-dom';
import {
  Flower2,
  LayoutGrid,
  Package,
  ClipboardList,
  UserCircle2,
  ShieldCheck,
  Activity,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../api/AuthContext';
import { getUserDisplayName } from '../api/api';

const ROLE_BADGE = {
  customer: 'badge-customer',
  staff: 'badge-staff',
  admin: 'badge-admin',
};

function navItemsFor(role) {
  const base = [
    { to: '/', label: 'Home', icon: LayoutGrid },
    { to: '/products', label: 'Products', icon: Package },
    { to: '/orders', label: 'Orders', icon: ClipboardList },
    { to: '/profile', label: 'Profile', icon: UserCircle2 },
    { to: '/security-center', label: 'Security Center', icon: ShieldCheck },
    { to: '/monitoring', label: 'Monitoring', icon: Activity },
  ];
  return base;
}

export default function Navbar() {
  const { user, role, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {await logout();} catch {navigate('/login');}
  };

  const roleKey = (role || '').toLowerCase();
  const badgeClass = ROLE_BADGE[roleKey] || 'badge bg-navy-50 text-navy-700';
  const displayName = getUserDisplayName(user) || 'Guest';

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-navy-50 bg-white">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-navy-700">
          <Flower2 className="h-5 w-5 text-bloom-300" strokeWidth={2} />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-bold text-navy-700">FloraSecure</p>
          <p className="text-[11px] text-ink-faint">Shop &amp; Security Demo</p>
        </div>
      </div>

      <div className="mx-5 mb-4 flex items-center justify-between rounded-lg bg-canvas px-3 py-2.5">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-ink">
            {displayName}
          </p>
          <p className="truncate text-[11px] text-ink-faint">{user?.email}</p>
        </div>
        <span className={badgeClass}>{role || '—'}</span>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {navItemsFor(roleKey).map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-navy-700 text-white'
                  : 'text-ink-muted hover:bg-navy-50 hover:text-navy-700'
              }`
            }
          >
            <Icon className="h-4 w-4" strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 pb-5">
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
        >
          <LogOut className="h-4 w-4" strokeWidth={2} />
          Logout
        </button>
      </div>
    </aside>
  );
}
