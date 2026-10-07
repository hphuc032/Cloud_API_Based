import { useEffect, useState } from 'react';
import { UserCircle2, Clock, KeyRound, ShieldCheck } from 'lucide-react';
import AppLayout from '../components/AppLayout';
import { useAuth } from '../api/AuthContext';
import {
  getAccessToken,
  getExpiresAt,
  getTokenStatus,
  getUserDisplayName,
  tokenPreview,
} from '../api/api';

const ROLE_BADGE = {
  customer: 'badge-customer',
  staff: 'badge-staff',
  admin: 'badge-admin',
};

const STATUS_STYLE = {
  valid: 'bg-sage-50 text-sage-700',
  expired: 'bg-red-50 text-red-600',
  missing: 'bg-amber-50 text-amber-700',
};

export default function Profile() {
  const { user, role } = useAuth();
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const token = getAccessToken();
  const expiresAt = getExpiresAt();
  const status = getTokenStatus();
  const roleKey = (role || '').toLowerCase();
  const displayName = getUserDisplayName(user);

  const remainingMs = expiresAt ? expiresAt - now : null;
  const remainingLabel =
    remainingMs === null
      ? '-'
      : remainingMs <= 0
      ? 'Expired'
      : `${Math.floor(remainingMs / 60000)}m ${Math.floor((remainingMs % 60000) / 1000)}s remaining`;

  return (
    <AppLayout>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-ink">Profile</h1>
        <p className="text-sm text-ink-muted">Your account and session details.</p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="card p-6 lg:col-span-1">
          <div className="flex flex-col items-center text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-navy-50">
              <UserCircle2 className="h-9 w-9 text-navy-700" />
            </div>
            <h2 className="mt-3 text-sm font-bold text-ink">{displayName || 'User'}</h2>
            <p className="text-xs text-ink-faint">{user?.email || '-'}</p>
            <span className={`mt-3 ${ROLE_BADGE[roleKey] || 'badge bg-navy-50 text-navy-700'}`}>
              {role || 'unknown'}
            </span>
          </div>
        </div>

        <div className="card p-6 lg:col-span-2">
          <div className="mb-4 flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-navy-700" />
            <h3 className="text-sm font-bold text-ink">Session &amp; Token</h3>
          </div>

          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-semibold text-ink-muted">Email</dt>
              <dd className="mt-0.5 text-sm text-ink">{user?.email || '-'}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-ink-muted">Full name</dt>
              <dd className="mt-0.5 text-sm text-ink">{user?.full_name || '-'}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-ink-muted">Username</dt>
              <dd className="mt-0.5 text-sm text-ink">{user?.username || '-'}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-ink-muted">Role</dt>
              <dd className="mt-0.5 text-sm text-ink">{role || '-'}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-ink-muted">Verified</dt>
              <dd className="mt-0.5 text-sm text-ink">{user?.is_verified ? 'Yes' : 'No'}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-ink-muted">Token status</dt>
              <dd className="mt-0.5">
                <span className={`badge ${STATUS_STYLE[status]}`}>{status}</span>
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-1 text-xs font-semibold text-ink-muted">
                <Clock className="h-3 w-3" /> Token expiration
              </dt>
              <dd className="mt-0.5 text-sm text-ink">{remainingLabel}</dd>
            </div>
          </dl>

          <div className="mt-4 border-t border-navy-50 pt-4">
            <p className="mb-1.5 text-xs font-semibold text-ink-muted">
              Access token preview (truncated for security)
            </p>
            <code className="block break-all rounded-lg bg-navy-900 px-3 py-2.5 text-xs text-sage-400">
              {tokenPreview(token)}
            </code>
            <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-faint">
              <ShieldCheck className="h-3.5 w-3.5 text-sage-600" />
              Only the first and last 20 characters are shown. The full token is never rendered.
            </p>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
