-- ============================================================
-- DATABASE SCHEMA - Cloud API Security Capstone Project
-- NT219 - Cryptography
-- ============================================================

-- Enable UUID extension (PostgreSQL)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TABLE: users
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    username        VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    phone           VARCHAR(20),
    role            VARCHAR(20) NOT NULL DEFAULT 'customer'
                    CHECK (role IN ('admin', 'staff', 'customer')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,

    -- Security fields
    failed_login_attempts   INT NOT NULL DEFAULT 0,
    locked_until            TIMESTAMP WITH TIME ZONE,
    last_login_at           TIMESTAMP WITH TIME ZONE,
    last_login_ip           VARCHAR(45),         -- supports IPv6

    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email    ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role     ON users(role);

-- ============================================================
-- TABLE: refresh_tokens  (JWT revocation support)
-- ============================================================
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,  -- SHA-256 of raw token
    device_info VARCHAR(255),
    ip_address  VARCHAR(45),
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at  TIMESTAMP WITH TIME ZONE,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user_id    ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);

-- ============================================================
-- TABLE: categories
-- ============================================================
CREATE TABLE categories (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL UNIQUE,
    slug        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TABLE: products
-- ============================================================
CREATE TABLE products (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id     UUID REFERENCES categories(id) ON DELETE SET NULL,
    sku             VARCHAR(100) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    price           NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    stock_quantity  INT NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    image_url       VARCHAR(500),

    -- Metadata
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_products_sku         ON products(sku);
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_products_is_active   ON products(is_active);

-- ============================================================
-- TABLE: orders
-- ============================================================
CREATE TABLE orders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    order_number    VARCHAR(50) NOT NULL UNIQUE,   -- human-readable e.g. ORD-20240614-0001
    status          VARCHAR(30) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','confirmed','processing','shipped','delivered','cancelled','refunded')),
    total_amount    NUMERIC(14, 2) NOT NULL CHECK (total_amount >= 0),
    currency        CHAR(3) NOT NULL DEFAULT 'VND',

    -- Shipping
    shipping_name       VARCHAR(255),
    shipping_phone      VARCHAR(20),
    shipping_address    TEXT,
    shipping_city       VARCHAR(100),

    -- Tracking
    notes           TEXT,
    cancelled_at    TIMESTAMP WITH TIME ZONE,
    cancel_reason   TEXT,

    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_user_id      ON orders(user_id);
CREATE INDEX idx_orders_order_number ON orders(order_number);
CREATE INDEX idx_orders_status       ON orders(status);
CREATE INDEX idx_orders_created_at   ON orders(created_at DESC);

-- ============================================================
-- TABLE: order_items
-- ============================================================
CREATE TABLE order_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id        UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity        INT NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    subtotal        NUMERIC(14, 2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_order_items_order_id   ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);

-- ============================================================
-- TABLE: audit_logs  (Security requirement)
-- ============================================================
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(100) NOT NULL,      -- e.g. LOGIN, CREATE_ORDER, DELETE_PRODUCT
    resource_type   VARCHAR(50),               -- e.g. order, product, user
    resource_id     UUID,
    ip_address      VARCHAR(45),
    user_agent      VARCHAR(500),
    request_id      UUID,                       -- correlation id
    status_code     INT,
    detail          JSONB,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id      ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action       ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource     ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_created_at   ON audit_logs(created_at DESC);

-- ============================================================
-- Auto-update updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_categories_updated_at
    BEFORE UPDATE ON categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- Seed: default admin user (password must be changed)
-- ============================================================
-- INSERT INTO users (email, username, hashed_password, full_name, role, is_verified)
-- VALUES ('admin@company.com', 'admin', '<bcrypt_hash>', 'System Admin', 'admin', TRUE);