import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Flower2, ShieldCheck, Loader2, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { login, getMe, saveSession } from '../api/api';
import { useAuth } from '../api/AuthContext';

const DEMO_ACCOUNTS = [
  { label: 'Staff', email: 'demo_api4@example.com', password: 'Demo@123' },
  { label: 'Customer', email: 'customer_order@example.com', password: 'Customer@123' },
  { label: 'Customer B', email: 'customer_test2@example.com', password: 'Customer2@123' },
];

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { completeLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const tokenData = await login(email, password);
      // Token must be saved before calling /auth/me so the interceptor can attach it
      saveSession(tokenData);
      const me = await getMe();
      completeLogin(tokenData, me);

      const roleKey = (me?.role || '').toLowerCase();
      const redirectTo =
        location.state?.from?.pathname ||
        (roleKey === 'customer' ? '/customer-dashboard' : '/admin-dashboard');
      navigate(redirectTo, { replace: true });
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || err.response?.data?.message;
      if (status === 401) {
        setError('Invalid email or password. (401 Unauthorized)');
      } else if (status === 429) {
        setError('Too many login attempts. Please wait before trying again. (429 Too Many Requests)');
      } else if (detail) {
        setError(
          `${Array.isArray(detail) ? detail.map((item) => item.msg || item.message || JSON.stringify(item)).join('; ') : detail} (${status ?? 'network error'})`
        );
      } else {
        setError(`Login failed: ${err.message || 'Please check your credentials and try again.'}`);
      }
    } finally {
      setLoading(false);
    }
  }

  function fillDemo(acc) {
    setEmail(acc.email);
    setPassword(acc.password);
    setError('');
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-navy-700 via-navy-700 to-sage-700 px-4">
      <div className="grid w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl md:grid-cols-2">
        {/* Left brand panel */}
        <div className="hidden flex-col justify-between bg-navy-700 p-10 text-white md:flex">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/10">
                <Flower2 className="h-5 w-5 text-bloom-300" />
              </div>
              <span className="text-lg font-bold">FloraSecure Shop</span>
            </div>
            <p className="mt-6 text-sm leading-relaxed text-navy-100">
              A small-business flower e-commerce API, hardened end to end &mdash; OAuth2/OIDC
              authentication, RBAC, gateway-level rate limiting, and signed webhooks.
            </p>
          </div>
          <div className="space-y-3 rounded-xl bg-white/5 p-4">
            <div className="flex items-center gap-2 text-sage-400">
              <ShieldCheck className="h-4 w-4" />
              <span className="text-xs font-semibold uppercase tracking-wide">
                Capstone Security Demo
              </span>
            </div>
            <p className="text-xs leading-relaxed text-navy-100">
              Every request on this site is authenticated with a short-lived JWT and authorized
              against the role returned by the Identity Provider.
            </p>
          </div>
        </div>

        {/* Right form panel */}
        <div className="flex flex-col justify-center p-8 md:p-10">
          <div className="mb-6 flex items-center gap-2 md:hidden">
            <Flower2 className="h-5 w-5 text-navy-700" />
            <span className="text-lg font-bold text-navy-700">FloraSecure Shop</span>
          </div>

          <h1 className="text-xl font-bold text-ink">Sign in to your account</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Use your registered email and password.
          </p>

          <div className="mt-4 flex items-center gap-2 rounded-lg border border-sage-100 bg-sage-50 px-3 py-2">
            <ShieldCheck className="h-4 w-4 flex-shrink-0 text-sage-600" />
            <span className="text-xs font-medium text-sage-700">JWT Authentication enabled</span>
          </div>

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-ink-muted">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="input-field"
                autoComplete="email"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-ink-muted">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;"
                  className="input-field pr-10"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink-muted"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-100 bg-red-50 px-3 py-2.5">
                <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-600" />
                <span className="text-xs font-medium text-red-700">{error}</span>
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Signing in...
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <div className="mt-6 border-t border-navy-50 pt-4">
            <p className="mb-2 text-xs font-semibold text-ink-muted">Demo accounts</p>
            <div className="flex flex-wrap gap-2">
              {DEMO_ACCOUNTS.map((acc) => (
                <button
                  key={acc.email}
                  type="button"
                  onClick={() => fillDemo(acc)}
                  className="btn-ghost-sm"
                >
                  {acc.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
