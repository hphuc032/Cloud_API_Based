import { useEffect, useState } from 'react';
import {
  Flower2,
  Plus,
  Pencil,
  Trash2,
  ShoppingCart,
  Loader2,
  X,
  PackageSearch,
} from 'lucide-react';
import AppLayout from '../components/AppLayout';
import { useAuth } from '../api/AuthContext';
import {
  getProducts,
  createProduct,
  updateProduct,
  deleteProduct,
  createOrder,
  getApiErrorMessage,
  unwrapItems,
} from '../api/api';

const PLACEHOLDER_PALETTE = ['from-bloom-100 to-bloom-300', 'from-sage-100 to-sage-400', 'from-navy-50 to-navy-200'];

function FlowerPlaceholder({ index }) {
  const cls = PLACEHOLDER_PALETTE[index % PLACEHOLDER_PALETTE.length];
  return (
    <div className={`flex h-36 items-center justify-center rounded-lg bg-gradient-to-br ${cls}`}>
      <Flower2 className="h-10 w-10 text-white/90" strokeWidth={1.5} />
    </div>
  );
}

function ProductImage({ product, index }) {
  const [failed, setFailed] = useState(false);

  if (!product.image_url || failed) return <FlowerPlaceholder index={index} />;

  return (
    <img
      src={product.image_url}
      alt={product.name}
      className="h-36 w-full rounded-lg object-cover"
      onError={() => setFailed(true)}
    />
  );
}

function ProductFormModal({ initial, onClose, onSubmit, submitting }) {
  const [sku, setSku] = useState(initial?.sku || '');
  const [name, setName] = useState(initial?.name || '');
  const [description, setDescription] = useState(initial?.description || '');
  const [price, setPrice] = useState(initial?.price ?? '');
  const [stock, setStock] = useState(initial?.stock ?? initial?.stock_quantity ?? '');
  const [imageUrl, setImageUrl] = useState(initial?.image_url || '');

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit({
      sku,
      name,
      description,
      price: Number(price),
      stock_quantity: Number(stock),
      image_url: imageUrl || null,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/40 px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-bold text-ink">
            {initial ? 'Update Product' : 'Create Product'}
          </h3>
          <button onClick={onClose} className="text-ink-faint hover:text-ink">
            <X className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-semibold text-ink-muted">SKU</label>
            <input
              required
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              className="input-field"
              placeholder="e.g. LAPTOP-001"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-ink-muted">Product name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input-field"
              placeholder="e.g. Business Laptop"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-ink-muted">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input-field min-h-[72px]"
              placeholder="Short description"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-ink-muted">
                Price (VND)
              </label>
              <input
                type="number"
                min="0"
                required
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                className="input-field"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-ink-muted">Stock</label>
              <input
                type="number"
                min="0"
                required
                value={stock}
                onChange={(e) => setStock(e.target.value)}
                className="input-field"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-ink-muted">Image URL</label>
            <input
              type="url"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              className="input-field"
              placeholder="https://example.com/laptop.png"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="btn-sage">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {initial ? 'Save changes' : 'Create product'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Products() {
  const { role } = useAuth();
  const isStaffOrAdmin = ['staff', 'admin'].includes((role || '').toLowerCase());

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [modalMode, setModalMode] = useState(null); // null | 'create' | product object
  const [submitting, setSubmitting] = useState(false);
  const [actionNotice, setActionNotice] = useState(null);
  const [orderingId, setOrderingId] = useState(null);

  async function loadProducts() {
    setLoading(true);
    setErrorMsg('');
    try {
      const data = await getProducts();
      setProducts(unwrapItems(data));
    } catch (err) {
      setErrorMsg(getApiErrorMessage(err, 'Failed to load products'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProducts();
  }, []);

  async function handleCreateOrUpdate(payload) {
    setSubmitting(true);
    try {
      if (modalMode && modalMode !== 'create') {
        await updateProduct(modalMode.id ?? modalMode.product_id, payload);
        setActionNotice({ type: 'success', text: 'Product updated successfully.' });
      } else {
        await createProduct(payload);
        setActionNotice({ type: 'success', text: 'Product created successfully.' });
      }
      setModalMode(null);
      await loadProducts();
    } catch (err) {
      setActionNotice({
        type: 'error',
        text: `Operation failed (${err.response?.status ?? 'error'}): ${
          err.response?.data?.detail || 'See console for details.'
        }`,
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(product) {
    if (!confirm(`Delete "${product.name}"? This cannot be undone.`)) return;
    try {
      await deleteProduct(product.id ?? product.product_id);
      setActionNotice({ type: 'success', text: 'Product deleted.' });
      await loadProducts();
    } catch (err) {
      setActionNotice({
        type: 'error',
        text: `Delete failed (${err.response?.status ?? 'error'}): ${
          err.response?.data?.detail || ''
        }`,
      });
    }
  }

  async function handleOrder(product) {
    setOrderingId(product.id ?? product.product_id);
    try {
      await createOrder({
        items: [{ product_id: product.id ?? product.product_id, quantity: 1 }],
      });
      setActionNotice({ type: 'success', text: `Order placed for "${product.name}".` });
    } catch (err) {
      setActionNotice({
        type: 'error',
        text: `Order failed (${err.response?.status ?? 'error'}): ${
          err.response?.data?.detail || ''
        }`,
      });
    } finally {
      setOrderingId(null);
    }
  }

  return (
    <AppLayout>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ink">Flower Catalog</h1>
          <p className="text-sm text-ink-muted">
            {isStaffOrAdmin
              ? 'Manage the product catalog: create, update, and delete listings.'
              : 'Browse our flowers and place an order.'}
          </p>
        </div>
        {isStaffOrAdmin && (
          <button onClick={() => setModalMode('create')} className="btn-sage">
            <Plus className="h-4 w-4" /> Create Product
          </button>
        )}
      </div>

      {actionNotice && (
        <div
          className={`mb-4 rounded-lg px-4 py-2.5 text-sm font-medium ${
            actionNotice.type === 'success'
              ? 'bg-sage-50 text-sage-700'
              : 'bg-red-50 text-red-700'
          }`}
        >
          {actionNotice.text}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 py-12 text-ink-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading products...
        </div>
      )}

      {!loading && errorMsg && (
        <div className="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMsg}
        </div>
      )}

      {!loading && !errorMsg && products.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-16 text-center text-ink-muted">
          <PackageSearch className="h-8 w-8 text-ink-faint" />
          <p className="text-sm">No products yet.</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((p, i) => {
          const id = p.id ?? p.product_id;
          const stock = p.stock_quantity ?? p.stock ?? 0;
          return (
            <div key={id ?? i} className="card flex flex-col p-4">
              <ProductImage product={p} index={i} />
              <div className="mt-3 flex-1">
                <h3 className="text-sm font-bold text-ink">{p.name}</h3>
                {p.sku && <p className="mt-0.5 font-mono text-[11px] text-ink-faint">{p.sku}</p>}
                <p className="mt-1 line-clamp-2 text-xs text-ink-muted">
                  {p.description || 'No description provided.'}
                </p>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className="text-sm font-bold text-navy-700">
                  {Number(p.price ?? 0).toLocaleString('vi-VN')} đ
                </span>
                <span
                  className={`text-xs font-medium ${
                    stock > 0 ? 'text-sage-600' : 'text-red-500'
                  }`}
                >
                  {stock > 0 ? `${stock} in stock` : 'Out of stock'}
                </span>
              </div>

              <div className="mt-3 flex gap-2">
                {!isStaffOrAdmin && (
                  <button
                    onClick={() => handleOrder(p)}
                    disabled={stock <= 0 || orderingId === id}
                    className="btn-primary w-full text-xs"
                  >
                    {orderingId === id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <ShoppingCart className="h-3.5 w-3.5" />
                    )}
                    Order
                  </button>
                )}
                {isStaffOrAdmin && (
                  <>
                    <button
                      onClick={() => setModalMode(p)}
                      className="btn-secondary flex-1 text-xs"
                    >
                      <Pencil className="h-3.5 w-3.5" /> Update
                    </button>
                    <button
                      onClick={() => handleDelete(p)}
                      className="btn-danger flex-1 text-xs"
                    >
                      <Trash2 className="h-3.5 w-3.5" /> Delete
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {modalMode && (
        <ProductFormModal
          initial={modalMode === 'create' ? null : modalMode}
          onClose={() => setModalMode(null)}
          onSubmit={handleCreateOrUpdate}
          submitting={submitting}
        />
      )}
    </AppLayout>
  );
}
