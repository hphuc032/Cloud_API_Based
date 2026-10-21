import { identity } from '../identity/runtime';
import axios from 'axios';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export function getAccessToken() { return identity.currentToken(); }
export function getExpiresAt() { return identity.expiresAt(); }
export function getTokenStatus() {
  if (!getAccessToken()) return 'missing';
  return getExpiresAt() <= Date.now() ? 'expired' : 'valid';
}
export function tokenPreview() { return getAccessToken() ? 'Access token held in memory' : '-'; }

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
api.interceptors.request.use(async (config) => {
  if (!config.skipAuth) {
    const token = await identity.token();
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
    if (error.response?.status === 401 && !error.config?.intentionalSecurityProbe && typeof onUnauthorized === 'function') {
      onUnauthorized();
    }
    return Promise.reject(error);
  }
);

// --- Auth ------------------------------------------------------------------

export async function getMe(opts = {}) {
  const res = await api.get('/api/v1/auth/me', opts);
  return res.data;
}

// --- Products --------------------------------------------------------------

export async function getProducts() {
  const res = await api.get('/api/v1/products/', {skipAuth:true});
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

export async function postWebhookReceive(rawBody, signature, timestamp) {
  // Axios JSON transforms may trim strings; MAC verification needs exact bytes.
  const res = await api.post('/api/v1/webhooks/receive', rawBody, {
    skipAuth:true,
    transformRequest: [(value) => value],
    headers: {'Content-Type':'application/json','X-Signature':signature,'X-Timestamp':timestamp},
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
  const res = await api.get('/health', {skipAuth:true});
  return res.data;
}

export { BASE_URL };
