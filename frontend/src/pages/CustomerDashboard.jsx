import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Flower2, ShoppingCart, ClipboardList, ShieldCheck, ArrowRight, Loader2 } from 'lucide-react';
import AppLayout from '../components/AppLayout';
import { useAuth } from '../api/AuthContext';
import { getProducts, getUserDisplayName, unwrapItems } from '../api/api';

export default function CustomerDashboard() {
  const { user } = useAuth();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getProducts()
      .then((data) => setProducts(unwrapItems(data).slice(0, 3)))
      .catch(() => setProducts([]))
      .finally(() => setLoading(false));
  }, []);

  const displayName = getUserDisplayName(user) || 'there';

  return (
    <AppLayout>
      {/* Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-navy-700 to-sage-700 px-8 py-10 text-white">
        <div className="relative z-10 max-w-lg">
          <p className="text-xs font-semibold uppercase tracking-wide text-bloom-300">
            Welcome back
          </p>
          <h1 className="mt-1 text-2xl font-bold">
            Hi {displayName}, welcome to FloraSecure Shop
          </h1>
          <p className="mt-2 text-sm text-navy-100">
            Fresh flowers, secured checkout. Every order you place is protected end-to-end by our
            API security layer.
          </p>
          <Link
            to="/products"
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-navy-700 transition-colors hover:bg-bloom-50"
          >
            Browse flowers <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <Flower2 className="absolute -right-6 -top-6 h-40 w-40 text-white/10" strokeWidth={1} />
      </div>

      {/* Quick actions */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link to="/products" className="card flex items-center gap-3 p-4 transition-shadow hover:shadow-cardHover">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-bloom-50">
            <ShoppingCart className="h-5 w-5 text-bloom-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">Order flowers</p>
            <p className="text-xs text-ink-muted">Browse the catalog</p>
          </div>
        </Link>
        <Link to="/orders" className="card flex items-center gap-3 p-4 transition-shadow hover:shadow-cardHover">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-navy-50">
            <ClipboardList className="h-5 w-5 text-navy-700" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">My Orders</p>
            <p className="text-xs text-ink-muted">Track your orders</p>
          </div>
        </Link>
        <Link to="/security-center" className="card flex items-center gap-3 p-4 transition-shadow hover:shadow-cardHover">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sage-50">
            <ShieldCheck className="h-5 w-5 text-sage-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">Security Center</p>
            <p className="text-xs text-ink-muted">See how your data is protected</p>
          </div>
        </Link>
      </div>

      {/* Featured products */}
      <div className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold text-ink">Featured flowers</h2>
          <Link to="/products" className="text-xs font-semibold text-navy-700 hover:underline">
            View all
          </Link>
        </div>

        {loading && (
          <div className="flex items-center gap-2 py-8 text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
          </div>
        )}

        {!loading && products.length === 0 && (
          <p className="py-4 text-sm text-ink-muted">No products available right now.</p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {products.map((p, i) => (
            <div key={p.id ?? p.product_id ?? i} className="card p-4">
              <div className="flex h-28 items-center justify-center rounded-lg bg-gradient-to-br from-bloom-100 to-bloom-300">
                <Flower2 className="h-8 w-8 text-white/90" strokeWidth={1.5} />
              </div>
              <h3 className="mt-3 text-sm font-bold text-ink">{p.name}</h3>
              <p className="text-sm font-semibold text-navy-700">
                {Number(p.price ?? 0).toLocaleString('vi-VN')} đ
              </p>
            </div>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
