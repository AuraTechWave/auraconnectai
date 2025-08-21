"""Create materialized views for analytics aggregations

Revision ID: create_materialized_views_2025_01_21
Revises: add_performance_indexes_2025_01_21
Create Date: 2025-01-21 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'create_materialized_views_2025_01_21'
down_revision = 'add_performance_indexes_2025_01_21'
branch_labels = None
depends_on = None


def upgrade():
    """Create materialized views for pre-computed analytics aggregations"""
    
    # 1. Daily Sales Summary Materialized View
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_sales_summary AS
        SELECT 
            DATE(o.order_date) as sale_date,
            o.restaurant_id,
            COUNT(DISTINCT o.id) as total_orders,
            COUNT(DISTINCT o.customer_id) as unique_customers,
            SUM(o.total_amount) as total_revenue,
            AVG(o.total_amount) as avg_order_value,
            SUM(o.discount_amount) as total_discounts,
            SUM(o.tax_amount) as total_tax,
            COUNT(DISTINCT CASE WHEN o.status = 'completed' THEN o.id END) as completed_orders,
            COUNT(DISTINCT CASE WHEN o.status = 'cancelled' THEN o.id END) as cancelled_orders,
            -- Time-based aggregations
            COUNT(DISTINCT CASE WHEN EXTRACT(hour FROM o.order_date) BETWEEN 11 AND 14 THEN o.id END) as lunch_orders,
            COUNT(DISTINCT CASE WHEN EXTRACT(hour FROM o.order_date) BETWEEN 17 AND 21 THEN o.id END) as dinner_orders,
            -- Staff performance
            COUNT(DISTINCT o.staff_id) as active_staff,
            MAX(o.total_amount) as highest_order_value,
            MIN(o.total_amount) as lowest_order_value
        FROM orders o
        WHERE o.status IN ('completed', 'paid')
        GROUP BY DATE(o.order_date), o.restaurant_id
    """)
    
    # Create index on materialized view
    op.execute("""
        CREATE INDEX idx_mv_daily_sales_date_restaurant 
        ON mv_daily_sales_summary(sale_date DESC, restaurant_id)
    """)
    
    # 2. Product Performance Materialized View
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_product_performance AS
        SELECT 
            oi.menu_item_id as product_id,
            mi.name as product_name,
            mi.category_id,
            mc.name as category_name,
            DATE(o.order_date) as sale_date,
            o.restaurant_id,
            SUM(oi.quantity) as quantity_sold,
            SUM(oi.price * oi.quantity) as revenue,
            COUNT(DISTINCT o.id) as order_count,
            COUNT(DISTINCT o.customer_id) as unique_customers,
            AVG(oi.price) as avg_price,
            -- Rankings (will be calculated in query)
            ROW_NUMBER() OVER (
                PARTITION BY DATE(o.order_date), o.restaurant_id 
                ORDER BY SUM(oi.quantity) DESC
            ) as daily_quantity_rank,
            ROW_NUMBER() OVER (
                PARTITION BY DATE(o.order_date), o.restaurant_id 
                ORDER BY SUM(oi.price * oi.quantity) DESC
            ) as daily_revenue_rank
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        LEFT JOIN menu_items mi ON oi.menu_item_id = mi.id
        LEFT JOIN menu_categories mc ON mi.category_id = mc.id
        WHERE o.status IN ('completed', 'paid')
        GROUP BY 
            oi.menu_item_id,
            mi.name,
            mi.category_id,
            mc.name,
            DATE(o.order_date),
            o.restaurant_id
    """)
    
    # Create indexes
    op.execute("""
        CREATE INDEX idx_mv_product_perf_date_restaurant 
        ON mv_product_performance(sale_date DESC, restaurant_id)
    """)
    
    op.execute("""
        CREATE INDEX idx_mv_product_perf_product 
        ON mv_product_performance(product_id, sale_date DESC)
    """)
    
    # 3. Hourly Sales Patterns Materialized View
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_sales_patterns AS
        SELECT 
            EXTRACT(hour FROM o.order_date) as hour_of_day,
            EXTRACT(dow FROM o.order_date) as day_of_week,
            o.restaurant_id,
            COUNT(o.id) as order_count,
            SUM(o.total_amount) as total_revenue,
            AVG(o.total_amount) as avg_order_value,
            COUNT(DISTINCT o.customer_id) as unique_customers,
            AVG(EXTRACT(epoch FROM (o.completed_at - o.created_at))/60) as avg_processing_minutes
        FROM orders o
        WHERE o.status IN ('completed', 'paid')
            AND o.order_date >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY 
            EXTRACT(hour FROM o.order_date),
            EXTRACT(dow FROM o.order_date),
            o.restaurant_id
    """)
    
    # Create index
    op.execute("""
        CREATE INDEX idx_mv_hourly_patterns_restaurant 
        ON mv_hourly_sales_patterns(restaurant_id, hour_of_day, day_of_week)
    """)
    
    # 4. Customer Lifetime Value Materialized View
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_customer_lifetime_value AS
        SELECT 
            c.id as customer_id,
            c.restaurant_id,
            COUNT(DISTINCT o.id) as total_orders,
            SUM(o.total_amount) as lifetime_value,
            AVG(o.total_amount) as avg_order_value,
            MIN(o.order_date) as first_order_date,
            MAX(o.order_date) as last_order_date,
            CASE 
                WHEN COUNT(DISTINCT o.id) = 1 THEN 'one_time'
                WHEN COUNT(DISTINCT o.id) <= 5 THEN 'occasional'
                WHEN COUNT(DISTINCT o.id) <= 10 THEN 'regular'
                ELSE 'vip'
            END as customer_segment,
            -- Recency calculation (days since last order)
            EXTRACT(days FROM CURRENT_DATE - MAX(o.order_date)::date) as days_since_last_order,
            -- Frequency (orders per month)
            CASE 
                WHEN MAX(o.order_date) > MIN(o.order_date) THEN
                    COUNT(DISTINCT o.id) / NULLIF(
                        EXTRACT(months FROM AGE(MAX(o.order_date), MIN(o.order_date))), 0
                    )
                ELSE 0
            END as orders_per_month
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id AND o.status IN ('completed', 'paid')
        GROUP BY c.id, c.restaurant_id
    """)
    
    # Create indexes
    op.execute("""
        CREATE INDEX idx_mv_customer_ltv_restaurant 
        ON mv_customer_lifetime_value(restaurant_id, customer_segment)
    """)
    
    op.execute("""
        CREATE INDEX idx_mv_customer_ltv_value 
        ON mv_customer_lifetime_value(lifetime_value DESC)
    """)
    
    # 5. POS Provider Daily Summary Materialized View
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_pos_provider_daily_summary AS
        SELECT 
            pas.provider_id,
            pas.snapshot_date,
            epp.provider_name,
            epp.provider_code,
            SUM(pas.total_transactions) as total_transactions,
            SUM(pas.successful_transactions) as successful_transactions,
            SUM(pas.failed_transactions) as failed_transactions,
            SUM(pas.total_transaction_value) as total_transaction_value,
            AVG(pas.uptime_percentage) as avg_uptime,
            AVG(pas.average_sync_time_ms) as avg_sync_time,
            COUNT(DISTINCT pth.terminal_id) as total_terminals,
            COUNT(DISTINCT CASE WHEN pth.is_online THEN pth.terminal_id END) as online_terminals
        FROM pos_analytics_snapshot pas
        JOIN external_pos_provider epp ON pas.provider_id = epp.id
        LEFT JOIN pos_terminal_health pth ON pth.provider_id = pas.provider_id
        GROUP BY 
            pas.provider_id,
            pas.snapshot_date,
            epp.provider_name,
            epp.provider_code
    """)
    
    # Create index
    op.execute("""
        CREATE INDEX idx_mv_pos_daily_provider_date 
        ON mv_pos_provider_daily_summary(provider_id, snapshot_date DESC)
    """)
    
    # Create function to refresh all materialized views
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_analytics_materialized_views()
        RETURNS void AS $$
        BEGIN
            -- Refresh views in dependency order
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales_summary;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_product_performance;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_sales_patterns;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_customer_lifetime_value;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pos_provider_daily_summary;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create a scheduled job to refresh materialized views (requires pg_cron extension)
    # This is commented out as it requires pg_cron to be installed
    # op.execute("""
    #     SELECT cron.schedule('refresh-analytics-views', '0 * * * *', 
    #         'SELECT refresh_analytics_materialized_views();'
    #     );
    # """)


def downgrade():
    """Drop materialized views and related objects"""
    
    # Drop the refresh function
    op.execute("DROP FUNCTION IF EXISTS refresh_analytics_materialized_views()")
    
    # Drop materialized views in reverse order
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_pos_provider_daily_summary")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_customer_lifetime_value")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_hourly_sales_patterns")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_product_performance")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_sales_summary")