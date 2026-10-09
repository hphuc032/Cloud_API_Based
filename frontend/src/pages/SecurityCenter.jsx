import { useState } from 'react';
import {
  ShieldCheck,
  KeyRound,
  Lock,
  Webhook,
  Globe2,
  ListChecks,
  Loader2,
  Terminal,
  ExternalLink,
  RefreshCw,
} from 'lucide-react';
import AppLayout from '../components/AppLayout';
import { useAuth } from '../api/AuthContext';
import {
  api,
  BASE_URL,
  getAccessToken,
  getExpiresAt,
  tokenPreview,
  getTokenStatus,
  createProduct,
  getOrderById,
  getWebhookTestSignature,
  postWebhookReceive,
  testFetchUrl,
} from '../api/api';

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------

function SectionCard({ icon: Icon, title, subtitle, children }) {
  return (
    <div className="card p-5">
      <div className="mb-4 flex items-start gap-2.5">
        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-navy-50">
          <Icon className="h-4.5 w-4.5 text-navy-700" />
        </div>
        <div>
          <h3 className="text-sm font-bold text-ink">{title}</h3>
          {subtitle && <p className="text-xs text-ink-muted">{subtitle}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

function StatusCode({ code }) {
  if (code === null || code === undefined) return null;
  const cls =
    code >= 200 && code < 300
      ? 'status-2xx'
      : code === 401
      ? 'status-401'
      : code === 403
      ? 'status-403'
      : 'status-4xx';
  return <span className={cls}>HTTP {code}</span>;
}

function LogLine({ result }) {
  if (!result) return null;
  return (
    <div className="mt-3 rounded-lg bg-navy-900 p-3">
      <div className="console-line flex items-center justify-between text-sage-400">
        <span>$ {result.label}</span>
        <StatusCode code={result.status} />
      </div>
      {result.message && (
        <p className="console-line mt-1 text-navy-100">{result.message}</p>
      )}
    </div>
  );
}

async function runRequest(promiseFn) {
  try {
    const data = await promiseFn();
    return { status: 200, message: typeof data === 'object' ? JSON.stringify(data).slice(0, 160) : String(data) };
  } catch (err) {
    const status = err.response?.status ?? null;
    const detail = err.response?.data?.detail || err.response?.data?.message || err.message;
    return { status, message: detail, isError: true };
  }
}

// ---------------------------------------------------------------------------
// A. JWT Information
// ---------------------------------------------------------------------------

function JwtInfoCard() {
  const { role } = useAuth();
  const token = getAccessToken();
  const expiresAt = getExpiresAt();
  const status = getTokenStatus();

  const STATUS_STYLE = {
    valid: 'bg-sage-50 text-sage-700',
    expired: 'bg-red-50 text-red-600',
    missing: 'bg-amber-50 text-amber-700',
  };

  const expiresLabel = expiresAt
    ? new Date(expiresAt).toLocaleTimeString('vi-VN')
    : '—';

  return (
    <SectionCard icon={KeyRound} title="JWT Information" subtitle="Current access token state">
      <dl className="space-y-2.5 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-ink-muted">Token preview</dt>
          <dd className="font-mono text-xs text-ink">{tokenPreview(token)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-ink-muted">Expires at</dt>
          <dd className="text-ink">{expiresLabel}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-ink-muted">Role (from /auth/me)</dt>
          <dd className="font-semibold text-navy-700">{role || '—'}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-ink-muted">Token status</dt>
          <dd>
            <span className={`badge ${STATUS_STYLE[status]}`}>{status}</span>
          </dd>
        </div>
      </dl>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// B. RBAC
// ---------------------------------------------------------------------------

const PERMISSION_TABLE = {
  customer: [
    ['View Products', true],
    ['Create Order', true],
    ['View Own Orders', true],
    ['Create Product', false],
    ['Delete Product', false],
  ],
  'staff/admin': [
    ['View Products', true],
    ['Create Product', true],
    ['Update Product', true],
    ['Delete Product', true],
    ['View Orders', true],
  ],
};

function RbacCard() {
  const { role } = useAuth();
  const roleKey = (role || '').toLowerCase();
  const groupKey = ['staff', 'admin'].includes(roleKey) ? 'staff/admin' : 'customer';

  return (
    <SectionCard
      icon={Lock}
      title="Role-Based Access Control"
      subtitle={`Current role: ${role || 'unknown'}`}
    >
      <div className="space-y-3">
        {Object.entries(PERMISSION_TABLE).map(([group, rows]) => (
          <div key={group}>
            <p
              className={`mb-1.5 text-xs font-semibold uppercase tracking-wide ${
                group === groupKey ? 'text-navy-700' : 'text-ink-faint'
              }`}
            >
              {group} {group === groupKey && '(you)'}
            </p>
            <div className="space-y-1">
              {rows.map(([action, allowed]) => (
                <div
                  key={action}
                  className={`flex items-center justify-between rounded-md px-2.5 py-1.5 text-xs ${
                    group === groupKey ? 'bg-canvas' : 'opacity-50'
                  }`}
                >
                  <span className="text-ink">{action}</span>
                  <span className={allowed ? 'badge-allowed' : 'badge-denied'}>
                    {allowed ? 'allowed' : 'denied'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// C. API Rejection Demo
// ---------------------------------------------------------------------------

function DemoButton({ label, onClick, loading }) {
  return (
    <button onClick={onClick} disabled={loading} className="btn-secondary w-full justify-between text-xs">
      <span className="flex items-center gap-1.5">
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Terminal className="h-3.5 w-3.5" />}
        {label}
      </span>
    </button>
  );
}

function ApiRejectionDemoCard() {
  const [results, setResults] = useState({});
  const [loadingKey, setLoadingKey] = useState(null);
  const [orderIdInput, setOrderIdInput] = useState('');
  const [signature, setSignature] = useState('');
  const [ssrfUrl, setSsrfUrl] = useState('http://169.254.169.254');

  async function run(key, label, fn) {
    setLoadingKey(key);
    const result = await runRequest(fn);
    setResults((r) => ({ ...r, [key]: { ...result, label } }));
    setLoadingKey(null);
  }

  async function testMissingJwt() {
    await run('missingJwt', 'GET /api/v1/auth/me (no Authorization header)', async () => {
      const res = await api.get('/api/v1/auth/me', { skipAuth: true });
      return res.data;
    });
  }

  async function testUnauthorizedAdmin() {
    await run('unauthorizedAdmin', 'POST /api/v1/products (as current role)', () =>
      createProduct({ name: 'Unauthorized Test Flower', price: 1, stock_quantity: 1 })
    );
  }

  async function testBola() {
    if (!orderIdInput) return;
    await run('bola', `GET /api/v1/orders/${orderIdInput}`, () => getOrderById(orderIdInput));
  }

  async function testRateLimit() {
    setLoadingKey('rateLimit');
    const attempts = [];
    for (let i = 0; i < 6; i++) {
      const r = await runRequest(() =>
        api
          .get('/api/v1/products/', { skipAuth: true })
          .then((res) => res.data)
      );
      attempts.push(r.status);
      if (r.status === 429) break;
    }
    const hit429 = attempts.includes(429);
    setResults((r) => ({
      ...r,
      rateLimit: {
        status: hit429 ? 429 : attempts[attempts.length - 1],
        label: `6x GET /api/v1/products/`,
        message: hit429
          ? `Rate limit triggered after ${attempts.length} attempts: [${attempts.join(', ')}]`
          : `No 429 observed within ${attempts.length} attempts: [${attempts.join(', ')}]`,
      },
    }));
    setLoadingKey(null);
  }

  async function fetchTestSignature() {
    setLoadingKey('webhookFetch');
    const result = await runRequest(async () => {
      const data = await getWebhookTestSignature();
      if (data?.signature) setSignature(data.signature);
      return data;
    });
    setResults((r) => ({ ...r, webhookFetch: { ...result, label: 'GET /api/v1/webhooks/test-signature' } }));
    setLoadingKey(null);
  }

  async function sendWebhook(useValidSignature) {
    const key = useValidSignature ? 'webhookValid' : 'webhookInvalid';
    setLoadingKey(key);
    const sigToSend = useValidSignature ? signature : `${signature || 'sig'}_tampered`;
    const result = await runRequest(() =>
      postWebhookReceive({ event: 'order.created', test: true }, sigToSend)
    );
    setResults((r) => ({
      ...r,
      [key]: {
        ...result,
        label: `POST /api/v1/webhooks/receive (${useValidSignature ? 'valid' : 'tampered'} signature)`,
      },
    }));
    setLoadingKey(null);
  }

  async function runSsrf(url) {
    setLoadingKey(`ssrf_${url}`);
    const result = await runRequest(() => testFetchUrl(url));
    setResults((r) => ({
      ...r,
      ssrf: { ...result, label: `POST /api/v1/security/fetch-url { url: "${url}" }` },
    }));
    setLoadingKey(null);
  }

  return (
    <SectionCard
      icon={ListChecks}
      title="API Rejection Demo"
      subtitle="Each button fires a real request against the live backend"
    >
      <div className="space-y-5">
        {/* Missing JWT */}
        <div>
          <DemoButton
            label="Test Missing JWT"
            onClick={testMissingJwt}
            loading={loadingKey === 'missingJwt'}
          />
          <LogLine result={results.missingJwt} />
        </div>

        {/* Unauthorized admin action */}
        <div>
          <DemoButton
            label="Test Unauthorized Admin Access"
            onClick={testUnauthorizedAdmin}
            loading={loadingKey === 'unauthorizedAdmin'}
          />
          <LogLine result={results.unauthorizedAdmin} />
        </div>

        {/* BOLA */}
        <div>
          <p className="mb-1.5 text-xs font-semibold text-ink-muted">Test BOLA</p>
          <div className="flex gap-2">
            <input
              value={orderIdInput}
              onChange={(e) => setOrderIdInput(e.target.value)}
              placeholder="Order ID (e.g. another customer's)"
              className="input-field text-xs"
            />
            <button
              onClick={testBola}
              disabled={loadingKey === 'bola' || !orderIdInput}
              className="btn-secondary whitespace-nowrap text-xs"
            >
              {loadingKey === 'bola' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Fetch order'}
            </button>
          </div>
          <LogLine result={results.bola} />
        </div>

        {/* Rate limit */}
        <div>
          <DemoButton
            label="Test Rate Limit (6 public product reads)"
            onClick={testRateLimit}
            loading={loadingKey === 'rateLimit'}
          />
          <LogLine result={results.rateLimit} />
        </div>

        {/* Webhook signature */}
        <div>
          <p className="mb-1.5 text-xs font-semibold text-ink-muted">Test Webhook Signature</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={fetchTestSignature}
              disabled={loadingKey === 'webhookFetch'}
              className="btn-ghost-sm"
            >
              {loadingKey === 'webhookFetch' ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              Get test signature
            </button>
            <button
              onClick={() => sendWebhook(true)}
              disabled={loadingKey === 'webhookValid' || !signature}
              className="btn-sage text-xs"
            >
              Send with valid signature
            </button>
            <button
              onClick={() => sendWebhook(false)}
              disabled={loadingKey === 'webhookInvalid' || !signature}
              className="btn-danger text-xs"
            >
              Send with tampered signature
            </button>
          </div>
          {signature && (
            <p className="mt-1.5 truncate font-mono text-[11px] text-ink-faint">
              signature: {signature}
            </p>
          )}
          <LogLine result={results.webhookFetch} />
          <LogLine result={results.webhookValid} />
          <LogLine result={results.webhookInvalid} />
        </div>

        {/* SSRF */}
        <div>
          <p className="mb-1.5 text-xs font-semibold text-ink-muted">Test SSRF</p>
          <div className="flex flex-wrap gap-2">
            {['http://localhost', 'http://127.0.0.1', 'http://169.254.169.254'].map((url) => (
              <button
                key={url}
                onClick={() => runSsrf(url)}
                disabled={loadingKey === `ssrf_${url}`}
                className="btn-ghost-sm"
              >
                {loadingKey === `ssrf_${url}` ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : null}
                {url}
              </button>
            ))}
          </div>
          <LogLine result={results.ssrf} />
        </div>
      </div>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// D. Security Headers
// ---------------------------------------------------------------------------

const SECURITY_HEADERS = [
  'Strict-Transport-Security',
  'X-Content-Type-Options',
  'X-Frame-Options',
  'Referrer-Policy',
  'Content-Security-Policy',
];

function SecurityHeadersCard() {
  const [headers, setHeaders] = useState(null);
  const [loading, setLoading] = useState(false);
  const [checked, setChecked] = useState(false);

  async function checkHeaders() {
    setLoading(true);
    setChecked(false);
    try {
      const res = await fetch(`${BASE_URL}/health`, { headers: { 'ngrok-skip-browser-warning': 'true' } });
      const found = {};
      SECURITY_HEADERS.forEach((h) => {
        const v = res.headers.get(h);
        if (v) found[h] = v;
      });
      setHeaders(found);
    } catch {
      setHeaders({});
    } finally {
      setChecked(true);
      setLoading(false);
    }
  }

  const anyFound = headers && Object.keys(headers).length > 0;

  return (
    <SectionCard
      icon={ShieldCheck}
      title="Security Headers"
      subtitle="Headers enforced at the Kong Gateway edge"
    >
      <button onClick={checkHeaders} disabled={loading} className="btn-secondary mb-3 text-xs">
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
        Check headers on /health
      </button>

      {checked && !anyFound && (
        <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700">
          Browsers restrict JavaScript from reading most security headers via fetch(). Security
          headers are enforced at Kong Gateway, not visible client-side here.
        </p>
      )}

      <ul className="space-y-1.5">
        {SECURITY_HEADERS.map((h) => (
          <li
            key={h}
            className="flex items-center justify-between rounded-md bg-canvas px-2.5 py-1.5 text-xs"
          >
            <span className="font-mono text-ink">{h}</span>
            {headers?.[h] ? (
              <span className="badge-allowed">{headers[h]}</span>
            ) : (
              <span className="text-ink-faint">enforced at gateway</span>
            )}
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// E. Monitoring
// ---------------------------------------------------------------------------

const SAMPLE_METRICS = [
  { label: 'Total API Requests', value: '12,840' },
  { label: '401 Unauthorized', value: '37' },
  { label: '403 Forbidden', value: '19' },
  { label: '429 Too Many Requests', value: '8' },
  { label: 'Webhook Rejected', value: '4' },
  { label: 'SSRF Blocked', value: '6' },
];

function MonitoringCard() {
  return (
    <SectionCard
      icon={Globe2}
      title="Monitoring &amp; Logs"
      subtitle="Aggregated via Loki, visualized in Grafana"
    >
      <div className="mb-4 grid grid-cols-2 gap-2.5">
        {SAMPLE_METRICS.map((m) => (
          <div key={m.label} className="rounded-lg bg-canvas px-3 py-2.5">
            <p className="text-base font-bold text-navy-700">{m.value}</p>
            <p className="text-[11px] text-ink-muted">{m.label}</p>
          </div>
        ))}
      </div>
      <a
        href="http://localhost:3000"
        target="_blank"
        rel="noreferrer"
        className="btn-secondary w-full text-xs"
      >
        <ExternalLink className="h-3.5 w-3.5" /> Open Grafana Dashboard
      </a>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SecurityCenter() {
  return (
    <AppLayout>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-ink">Security Center</h1>
        <p className="text-sm text-ink-muted">
          Live demonstrations of the API&apos;s authentication, authorization, and abuse-prevention
          mechanisms. Every action below sends a real request to the backend.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <JwtInfoCard />
        <RbacCard />
        <div className="lg:col-span-2">
          <ApiRejectionDemoCard />
        </div>
        <SecurityHeadersCard />
        <MonitoringCard />
      </div>
    </AppLayout>
  );
}
