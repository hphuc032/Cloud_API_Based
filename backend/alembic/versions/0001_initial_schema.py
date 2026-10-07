"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2024-06-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── users ─────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id',                    UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('email',                 sa.String(255), nullable=False),
        sa.Column('username',              sa.String(100), nullable=False),
        sa.Column('hashed_password',       sa.String(255), nullable=False),
        sa.Column('full_name',             sa.String(255)),
        sa.Column('phone',                 sa.String(20)),
        sa.Column('role',                  sa.Enum('admin', 'staff', 'customer', name='userrole'), nullable=False, server_default='customer'),
        sa.Column('is_active',             sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified',           sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until',          sa.DateTime(timezone=True)),
        sa.Column('last_login_at',         sa.DateTime(timezone=True)),
        sa.Column('last_login_ip',         sa.String(45)),
        sa.Column('created_at',            sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',            sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )
    op.create_index('idx_users_email',    'users', ['email'])
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_role',     'users', ['role'])

    # ── refresh_tokens ────────────────────────────────────────
    op.create_table(
        'refresh_tokens',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',     UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash',  sa.String(255), nullable=False),
        sa.Column('device_info', sa.String(255)),
        sa.Column('ip_address',  sa.String(45)),
        sa.Column('expires_at',  sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked',     sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('revoked_at',  sa.DateTime(timezone=True)),
        sa.Column('created_at',  sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index('idx_refresh_tokens_user_id',    'refresh_tokens', ['user_id'])
    op.create_index('idx_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])

    # ── categories ────────────────────────────────────────────
    op.create_table(
        'categories',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name',        sa.String(100), nullable=False),
        sa.Column('slug',        sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('is_active',   sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at',  sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',  sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug'),
    )

    # ── products ──────────────────────────────────────────────
    op.create_table(
        'products',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('category_id',   UUID(as_uuid=True), sa.ForeignKey('categories.id', ondelete='SET NULL')),
        sa.Column('created_by',    UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('sku',            sa.String(100), nullable=False),
        sa.Column('name',           sa.String(255), nullable=False),
        sa.Column('description',    sa.Text()),
        sa.Column('price',          sa.Numeric(12, 2), nullable=False),
        sa.Column('stock_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active',      sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('image_url',      sa.String(500)),
        sa.Column('created_at',     sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',     sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('sku'),
        sa.CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
    )
    op.create_index('idx_products_sku',         'products', ['sku'])
    op.create_index('idx_products_category_id', 'products', ['category_id'])
    op.create_index('idx_products_is_active',   'products', ['is_active'])

    # ── orders ────────────────────────────────────────────────
    op.create_table(
        'orders',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',          UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('order_number',     sa.String(50), nullable=False),
        sa.Column('status',           sa.Enum('pending','confirmed','processing','shipped','delivered','cancelled','refunded', name='orderstatus'), nullable=False, server_default='pending'),
        sa.Column('total_amount',     sa.Numeric(14, 2), nullable=False),
        sa.Column('currency',         sa.String(3), nullable=False, server_default='VND'),
        sa.Column('shipping_name',    sa.String(255)),
        sa.Column('shipping_phone',   sa.String(20)),
        sa.Column('shipping_address', sa.Text()),
        sa.Column('shipping_city',    sa.String(100)),
        sa.Column('notes',            sa.Text()),
        sa.Column('cancelled_at',     sa.DateTime(timezone=True)),
        sa.Column('cancel_reason',    sa.Text()),
        sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',       sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('order_number'),
        sa.CheckConstraint("total_amount >= 0", name="ck_orders_total_non_negative"),
    )
    op.create_index('idx_orders_user_id',      'orders', ['user_id'])
    op.create_index('idx_orders_order_number', 'orders', ['order_number'])
    op.create_index('idx_orders_status',       'orders', ['status'])
    op.create_index('idx_orders_created_at',   'orders', ['created_at'])

    # ── order_items ───────────────────────────────────────────
    op.create_table(
        'order_items',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('order_id',   UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('quantity',   sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_order_items_unit_price_non_negative"),
    )
    op.create_index('idx_order_items_order_id',   'order_items', ['order_id'])
    op.create_index('idx_order_items_product_id', 'order_items', ['product_id'])

    # ── audit_logs ────────────────────────────────────────────
    op.create_table(
        'audit_logs',
        sa.Column('id',            sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id',       UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('action',        sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(50)),
        sa.Column('resource_id',   UUID(as_uuid=True)),
        sa.Column('ip_address',    sa.String(45)),
        sa.Column('user_agent',    sa.String(500)),
        sa.Column('request_id',    UUID(as_uuid=True)),
        sa.Column('status_code',   sa.Integer()),
        sa.Column('detail',        JSONB()),
        sa.Column('created_at',    sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_audit_logs_user_id',    'audit_logs', ['user_id'])
    op.create_index('idx_audit_logs_action',     'audit_logs', ['action'])
    op.create_index('idx_audit_logs_created_at', 'audit_logs', ['created_at'])

    # ── Auto-update trigger ───────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql;
    """)
    for table in ['users', 'products', 'orders', 'categories']:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    for table in ['users', 'products', 'orders', 'categories']:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column")

    for table in ['audit_logs', 'order_items', 'orders', 'products', 'categories', 'refresh_tokens', 'users']:
        op.drop_table(table)

    op.execute("DROP TYPE IF EXISTS orderstatus")
    op.execute("DROP TYPE IF EXISTS userrole")