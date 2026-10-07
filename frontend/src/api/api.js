import axios from 'axios';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'fs_access_token',
  REFRESH_TOKEN: 'fs_refresh_token',
  EXPIRES_AT: 'fs_expires_at',
  ROLE: 'fs_role',
  USER: 'fs_user',
};

// --- Token storage helpers -------------------------------------------------

export function saveSession({ access_token, refresh_token, expires_in }) {
  localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, access_token || '');
  if (refresh_token) localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refresh_token);
  if (expires_in) {
    const expiresAt = Date.now() + Number(expires_in) * 1000;
    localStorage.setItem(STORAGE_KEYS.EXPIRES_AT, String(expiresAt));
  }
}

export function saveUser(user) {
  localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user || {}));
  if (user?.role) localStorage.setItem(STORAGE_KEYS.ROLE, user.role);
}

export function getAccessToken() {
  return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN) || '';
}

export function getRefreshToken() {
  return localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN) || '';
}

export function getExpiresAt() {
  const v = localStorage.getItem(STORAGE_KEYS.EXPIRES_AT);
  return v ? Number(v) : null;
}

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.USER) || 'null');
  } catch {
    return null;
  }
}

export function getRole() {
  return localStorage.getItem(STORAGE_KEYS.ROLE) || getStoredUser()?.role || '';
}

export function clearSession() {
  Object.values(STORAGE_KEYS).forEach((k) => localStorage.removeItem(k));
}

export function getTokenStatus() {
  const token = getAccessToken();
  if (!token) return 'missing';
  const expiresAt = getExpiresAt();
  if (expiresAt && Date.now() > expiresAt) return 'expired';
  return 'valid';
}

export function tokenPreview(token) {
  if (!token) return '-';
  if (token.length <= 44) return token;
  return `${token.slice(0, 20)}...${token.slice(-20)}`;
}

export function unwrapItems(data) {
  return Array.isArray(data) ? data : data?.items || [];
}

export function getUserDisplayName(user) {
  return user?.full_name || user?.username || user?.email || '';
}

export function getApiErrorMessage(err, fallback = 'Request failed') {
  const status = err.response?.status;
  const detail = err.response?.data?.detail || err.response?.data?.message;
  const message = Array.isArray(detail)
    ? detail.map((item) => item.msg || item.message || JSON.stringify(item)).join('; ')
    : detail;

  if (status === 429) return `${fallback} (429). Backend is rate limiting requests.`;
  if (err.code === 'ECONNABORTED') return `${fallback}. Backend request timed out.`;
  if (!err.response && err.message) return `${fallback}. ${err.message}`;
  if (message) return `${fallback} (${status ?? 'network error'}). ${message}`;
  return `${fallback} (${status ?? err.message ?? 'network error'}).`;
}

// --- Axios instance ---------------------------------------------------------

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
});

// Attach Authorization header automatically, unless explicitly skipped.
api.interceptors.request.use((config) => {
  if (!config.skipAuth) {
    const token = getAccessToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

let onUnauthorized = null;
export function registerUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof onUnauthorized === 'function') {
      onUnauthorized();
    }
    return Promise.reject(error);
  }
);

// --- Auth ------------------------------------------------------------------

export async function login(email, password) {
  const body = new URLSearchParams();
  body.set('username', email);
  body.set('password', password);

  const res = await api.post('/api/v1/auth/login', body, {
    skipAuth: true,
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return res.data;
}

export async function register(payload) {
  const res = await api.post('/api/v1/auth/register', payload);
  return res.data;
}

export async function getMe(opts = {}) {
  const res = await api.get('/api/v1/auth/me', opts);
  return res.data;
}

// --- Products --------------------------------------------------------------

export async function getProducts() {
  const res = await api.get('/api/v1/products/');
  return res.data;
}

export async function createProduct(payload) {
  const res = await api.post('/api/v1/products/', payload);
  return res.data;
}

export async function updateProduct(productId, payload) {
  const res = await api.patch(`/api/v1/products/${productId}`, payload);
  return res.data;
}

export async function deleteProduct(productId) {
  const res = await api.delete(`/api/v1/products/${productId}`);
  return res.data;
}

// --- Orders ----------------------------------------------------------------

export async function getOrders() {
  const res = await api.get('/api/v1/orders/');
  return res.data;
}

export async function getOrderById(orderId) {
  const res = await api.get(`/api/v1/orders/${orderId}`);
  return res.data;
}

export async function createOrder(payload) {
  try {
    const res = await api.post('/api/v1/orders/', payload);
    return res.data;
  } catch (err) {
    const item = payload?.items?.[0];
    if (err.response?.status === 422 && item?.product_id) {
      const res = await api.post('/api/v1/orders/', {
        product_id: item.product_id,
        quantity: item.quantity ?? 1,
      });
      return res.data;
    }
    throw err;
  }
}

// --- Webhooks --------------------------------------------------------------

export async function getWebhookTestSignature() {
  const res = await api.get('/api/v1/webhooks/test-signature');
  return res.data;
}

export async function postWebhookReceive(payload, signature) {
  const res = await api.post('/api/v1/webhooks/receive', payload, {
    headers: signature ? { 'X-Webhook-Signature': signature } : {},
  });
  return res.data;
}

// --- SSRF / security -------------------------------------------------------

export async function testFetchUrl(url) {
  const res = await api.post('/api/v1/security/fetch-url', { url });
  return res.data;
}

// --- Health ----------------------------------------------------------------

export async function getHealth() {
  const res = await api.get('/health');
  return res.data;
}

export { BASE_URL };
