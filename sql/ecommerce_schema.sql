CREATE SCHEMA IF NOT EXISTS ecommerce;

CREATE TABLE IF NOT EXISTS ecommerce.customers (
    customer_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    signup_date TIMESTAMP,
    region VARCHAR(100),
    customer_tier VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS ecommerce.orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date TIMESTAMP,
    total_amount NUMERIC(12,2),
    status VARCHAR(50),
    payment_status VARCHAR(50),
    shipping_status VARCHAR(50),
    region VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES ecommerce.customers(customer_id)
);

CREATE TABLE IF NOT EXISTS ecommerce.order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    product_id INTEGER,
    sku VARCHAR(100),
    quantity INTEGER,
    unit_price NUMERIC(12,2),
    FOREIGN KEY (order_id) REFERENCES ecommerce.orders(order_id)
);

CREATE TABLE IF NOT EXISTS ecommerce.products (
    product_id INTEGER PRIMARY KEY,
    sku VARCHAR(100),
    product_name VARCHAR(200),
    category VARCHAR(100),
    price NUMERIC(12,2)
);

CREATE TABLE IF NOT EXISTS ecommerce.inventory (
    inventory_id INTEGER PRIMARY KEY,
    product_id INTEGER,
    sku VARCHAR(100),
    stock_qty INTEGER,
    reorder_level INTEGER,
    warehouse VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ecommerce.returns (
    return_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    customer_id INTEGER,
    return_reason VARCHAR(200),
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES ecommerce.orders(order_id)
);

CREATE TABLE IF NOT EXISTS ecommerce.refunds (
    refund_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    customer_id INTEGER,
    refund_amount NUMERIC(12,2),
    status VARCHAR(50),
    reason VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES ecommerce.orders(order_id)
);

CREATE TABLE IF NOT EXISTS ecommerce.shipments (
    shipment_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    carrier VARCHAR(100),
    tracking_number VARCHAR(100),
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    status VARCHAR(50)
);

INSERT INTO ecommerce.customers (customer_id, first_name, last_name, email, signup_date, region, customer_tier)
VALUES
(1, 'Ava', 'Patel', 'ava.patel@example.com', '2024-01-10', 'North', 'Gold'),
(2, 'Leo', 'Martin', 'leo.martin@example.com', '2023-11-15', 'West', 'Silver'),
(3, 'Nia', 'Johnson', 'nia.johnson@example.com', '2024-02-20', 'East', 'Gold'),
(4, 'Omar', 'Ali', 'omar.ali@example.com', '2023-12-01', 'South', 'Platinum'),
(5, 'Sofia', 'Nguyen', 'sofia.nguyen@example.com', '2024-03-05', 'Central', 'Silver')
ON CONFLICT DO NOTHING;

INSERT INTO ecommerce.products (product_id, sku, product_name, category, price)
VALUES
(101, 'SKU-123', 'Wireless Headphones', 'Electronics', 129.99),
(102, 'SKU-456', 'Running Shoes', 'Footwear', 89.50),
(103, 'SKU-789', 'Backpack', 'Accessories', 54.00),
(104, 'SKU-246', 'Coffee Grinder', 'Home', 75.00)
ON CONFLICT DO NOTHING;

INSERT INTO ecommerce.orders (order_id, customer_id, order_date, total_amount, status, payment_status, shipping_status, region)
VALUES
(10021, 1, '2026-11-01 09:15:00', 249.98, 'shipped', 'paid', 'in_transit', 'North'),
(10022, 2, '2026-11-02 18:45:00', 89.50, 'delivered', 'paid', 'delivered', 'West'),
(10023, 3, '2026-11-04 12:00:00', 179.00, 'processing', 'paid', 'pending', 'East'),
(10024, 4, '2026-11-08 15:20:00', 54.00, 'returned', 'refunded', 'returned', 'South'),
(10025, 5, '2026-11-10 08:00:00', 209.99, 'shipped', 'paid', 'delivered', 'Central')
ON CONFLICT DO NOTHING;

INSERT INTO ecommerce.order_items (order_item_id, order_id, product_id, sku, quantity, unit_price)
VALUES
(1, 10021, 101, 'SKU-123', 1, 129.99),
(2, 10021, 103, 'SKU-789', 2, 54.00),
(3, 10022, 102, 'SKU-456', 1, 89.50),
(4, 10023, 104, 'SKU-246', 2, 75.00),
(5, 10024, 103, 'SKU-789', 1, 54.00),
(6, 10025, 101, 'SKU-123', 1, 209.99)
ON CONFLICT DO NOTHING;

INSERT INTO ecommerce.inventory (inventory_id, product_id, sku, stock_qty, reorder_level, warehouse, updated_at)
VALUES
(1, 101, 'SKU-123', 18, 20, 'WH-01', '2026-11-15 10:00:00'),
(2, 102, 'SKU-456', 42, 15, 'WH-02', '2026-11-15 09:30:00'),
(3, 103, 'SKU-789', 7, 10, 'WH-01', '2026-11-15 08:20:00'),
(4, 104, 'SKU-246', 35, 10, 'WH-03', '2026-11-15 11:00:00')
ON CONFLICT DO NOTHING;

INSERT INTO ecommerce.returns (return_id, order_id, customer_id, return_reason, status, created_at, approved_at, resolved_at)
VALUES
(9001, 10024, 4, 'Damaged item', 'approved', '2026-11-09 12:00:00', '2026-11-09 13:00:00', '2026-11-11 14:00:00')
ON CONFLICT DO NOTHING;

INSERT INTO ecommerce.refunds (refund_id, order_id, customer_id, refund_amount, status, reason, created_at, resolved_at)
VALUES
(7001, 10024, 4, 54.00, 'completed', 'Damaged item', '2026-11-09 12:30:00', '2026-11-11 15:00:00')
ON CONFLICT DO NOTHING;

INSERT INTO ecommerce.shipments (shipment_id, order_id, carrier, tracking_number, shipped_at, delivered_at, status)
VALUES
(5001, 10021, 'FedEx', 'FX123456', '2026-11-02 10:00:00', NULL, 'in_transit'),
(5002, 10022, 'UPS', 'UPS654321', '2026-11-03 11:00:00', '2026-11-05 09:30:00', 'delivered'),
(5003, 10025, 'DHL', 'DHL987654', '2026-11-11 08:10:00', NULL, 'in_transit')
ON CONFLICT DO NOTHING;
