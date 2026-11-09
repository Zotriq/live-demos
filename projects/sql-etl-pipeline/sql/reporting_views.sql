-- Optional reporting views for BI tools (Metabase, Power BI, Looker Studio).
-- Run after the first pipeline run: psql "$DATABASE_URL" -f sql/reporting_views.sql

CREATE OR REPLACE VIEW monthly_revenue AS
SELECT date_trunc('month', order_date)::date AS month,
       source,
       COUNT(*)                               AS orders,
       SUM(amount_usd)                        AS revenue_usd,
       ROUND(AVG(amount_usd), 2)              AS avg_order_usd
FROM orders
WHERE status <> 'refunded'
GROUP BY 1, 2;

CREATE OR REPLACE VIEW customer_lifetime_value AS
SELECT c.email, c.name, c.country, c.first_order_date,
       COUNT(o.order_id)                      AS orders,
       COALESCE(SUM(o.amount_usd), 0)         AS lifetime_value_usd,
       MAX(o.order_date)                      AS last_order_date
FROM customers c
LEFT JOIN orders o ON o.customer_email = c.email AND o.status <> 'refunded'
GROUP BY c.email, c.name, c.country, c.first_order_date;

CREATE OR REPLACE VIEW data_quality AS
SELECT r.id AS run_id, r.started_at, r.status, r.extracted, r.loaded, r.rejected,
       ROUND(100.0 * r.rejected / NULLIF(r.extracted, 0), 1) AS rejected_pct
FROM etl_runs r
ORDER BY r.id DESC;
