-- Migration: Add indexes for AI insights performance optimization
-- This migration adds indexes to improve query performance for analytics and AI insights

-- Indexes for Order table
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_staff_id ON orders(staff_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_date_status ON orders(order_date, status);
CREATE INDEX IF NOT EXISTS idx_orders_customer_date ON orders(customer_id, order_date);

-- Composite index for common analytics queries
CREATE INDEX IF NOT EXISTS idx_orders_analytics ON orders(order_date, status, customer_id, staff_id);

-- Indexes for OrderItem table
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_order ON order_items(product_id, order_id);

-- Indexes for SalesAnalyticsSnapshot table (if using materialized views)
CREATE INDEX IF NOT EXISTS idx_sales_analytics_snapshot_date ON sales_analytics_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_sales_analytics_period_date ON sales_analytics_snapshots(aggregation_period, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_sales_analytics_staff_date ON sales_analytics_snapshots(staff_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_sales_analytics_product_date ON sales_analytics_snapshots(product_id, snapshot_date);

-- Function-based index for hour extraction (PostgreSQL specific)
CREATE INDEX IF NOT EXISTS idx_orders_hour ON orders(EXTRACT(hour FROM order_date));
CREATE INDEX IF NOT EXISTS idx_orders_dow ON orders(EXTRACT(dow FROM order_date));

-- Partial indexes for completed orders (most analytics queries filter by this)
CREATE INDEX IF NOT EXISTS idx_orders_completed ON orders(order_date, customer_id, total_amount) 
WHERE status IN ('completed', 'paid');

-- Index for anomaly detection (daily aggregations)
CREATE INDEX IF NOT EXISTS idx_orders_date_trunc ON orders(DATE(order_date));

-- Performance tip: Run ANALYZE after creating indexes
ANALYZE orders;
ANALYZE order_items;
ANALYZE sales_analytics_snapshots;