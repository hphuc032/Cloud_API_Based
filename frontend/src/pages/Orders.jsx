import { useEffect, useState } from 'react';
import { ClipboardList, Loader2, Eye, X, AlertCircle } from 'lucide-react';
import AppLayout from '../components/AppLayout';
import { useAuth } from '../api/AuthContext';
import { getOrders, getOrderById, unwrapItems } from '../api/api';

function StatusBadge({ status }) {
  const s = (status || '').toLowerCase();
  const map = {
    pending: 'bg-amber-50 text-amber-700',
    completed: 'bg-sage-50 text-sage-700',
    cancelled: 'bg-red-50 text-red-600',
    processing: 'bg-navy-50 text-navy-700',
  };
  return (
    <span className={`badge ${map[s] || 'bg-navy-50 text-navy-700'}`}>
      {status || 'unknown'}
    </span>
  );
}

function OrderDetailModal({ orderId, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getOrderById(orderId)
      .then((data) => {
        if (active) setDetail(data);
      })
      .catch((err) => {
        if (active) {
          setError(
            `Request failed with ${err.response?.status ?? 'network error'}${
              err.response?.status === 403
                ? ' — Forbidden. You do not own this order (BOLA protection).'
                : err.response?.status === 404
                ? ' — Order not found.'
                : ''
            }`
          );
        }
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [orderId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/40 px-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-bold text-ink">Order #{orderId}</h3>
          <button onClick={onClose} className="text-ink-faint hover:text-ink">
            <X className="h-5 w-5" />
          </button>
        </div>

        {loading && (
          <div className="flex items-center gap-2 py-8 text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading order detail...
          </div>
        )}

        {!loading && error && (
          <div className="flex items-start gap-2 rounded-lg border border-red-100 bg-red-50 px-3 py-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-600" />
            <span className="text-xs font-medium text-red-700">{error}</span>
          </div>
        )}

        {!loading && !error && detail && (
          <pre className="max-h-80 overflow-auto rounded-lg bg-navy-900 p-4 text-xs text-sage-400">
            {JSON.stringify(detail, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

export default function Orders() {
  const { role } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [viewingId, setViewingId] = useState(null);

  useEffect(() => {
    let active = true;
    getOrders()
      .then((data) => {
        if (active) setOrders(unwrapItems(data));
      })
      .catch((err) => {
        if (active) {
          setErrorMsg(
            `Failed to load orders (${err.response?.status ?? 'network error'}). ${
              err.response?.data?.detail || ''
            }`
          );
        }
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const isStaffOrAdmin = ['staff', 'admin'].includes((role || '').toLowerCase());

  return (
    <AppLayout>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-ink">
          {isStaffOrAdmin ? 'All Orders' : 'My Orders'}
        </h1>
        <p className="text-sm text-ink-muted">
          {isStaffOrAdmin
            ? 'Orders visible to staff and admin roles, as permitted by the API.'
            : 'Only orders that belong to your account are shown here.'}
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-12 text-ink-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading orders...
        </div>
      )}

      {!loading && errorMsg && (
        <div className="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMsg}
        </div>
      )}

      {!loading && !errorMsg && orders.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-16 text-center text-ink-muted">
          <ClipboardList className="h-8 w-8 text-ink-faint" />
          <p className="text-sm">No orders found.</p>
        </div>
      )}

      {!loading && !errorMsg && orders.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-navy-50 bg-navy-50/40 text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <th className="px-4 py-3">Order ID</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o, i) => {
                const id = o.id ?? o.order_id;
                const orderNumber = o.order_number || id;
                return (
                  <tr key={id ?? i} className="border-b border-navy-50 last:border-0">
                    <td className="px-4 py-3 font-mono text-xs text-navy-700">
                      {orderNumber}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={o.status} />
                    </td>
                    <td className="px-4 py-3 font-medium text-ink">
                      {Number(o.total_amount ?? o.total ?? 0).toLocaleString('vi-VN')} đ
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      {o.created_at ? new Date(o.created_at).toLocaleString('vi-VN') : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setViewingId(id)}
                        className="btn-ghost-sm ml-auto"
                      >
                        <Eye className="h-3.5 w-3.5" /> View Detail
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {viewingId !== null && (
        <OrderDetailModal orderId={viewingId} onClose={() => setViewingId(null)} />
      )}
    </AppLayout>
  );
}
