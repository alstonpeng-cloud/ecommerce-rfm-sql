-- Core analytics for ecommerce-rfm-sql.
-- All metrics are computed from raw transaction tables with SQL only.
-- {{AS_OF}} is replaced by run.py with the snapshot date.

-- Step 1. Clean orders: remove duplicated log lines and non-completed orders.
DROP TABLE IF EXISTS v_clean_orders;
CREATE TABLE v_clean_orders AS
SELECT DISTINCT order_id, user_id, date(order_date) AS order_date
FROM orders
WHERE status = 'completed';

-- Step 2. Order-level revenue from item detail (quantity x unit price).
DROP TABLE IF EXISTS v_order_revenue;
CREATE TABLE v_order_revenue AS
SELECT o.user_id,
       o.order_id,
       o.order_date,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS order_amount
FROM v_clean_orders o
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.user_id, o.order_id, o.order_date;

-- Step 3. RFM per user: recency, frequency, monetary.
DROP TABLE IF EXISTS v_rfm_raw;
CREATE TABLE v_rfm_raw AS
SELECT user_id,
       CAST(julianday('{{AS_OF}}') - julianday(MAX(order_date)) AS INTEGER) AS recency_days,
       COUNT(DISTINCT order_id) AS frequency,
       ROUND(SUM(order_amount), 2) AS monetary
FROM v_order_revenue
GROUP BY user_id;

-- Step 4. Rank into 5 buckets with NTILE (a true SQL window function).
-- Recency is reversed: ORDER BY DESC puts the stalest buyer in bucket 1
-- and the most recent buyer in bucket 5, so a higher r_score = more recent.
DROP TABLE IF EXISTS v_rfm_scored;
CREATE TABLE v_rfm_scored AS
SELECT user_id,
       recency_days,
       frequency,
       monetary,
       NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
       NTILE(5) OVER (ORDER BY frequency ASC)     AS f_score,
       NTILE(5) OVER (ORDER BY monetary ASC)      AS m_score
FROM v_rfm_raw;

-- Step 5. Eight-segment business rules. Mutually exclusive by construction,
-- unlike the chained if/else in the reference notebook.
DROP TABLE IF EXISTS v_user_segments;
CREATE TABLE v_user_segments AS
SELECT user_id,
       recency_days,
       frequency,
       monetary,
       r_score,
       f_score,
       m_score,
       CASE
         WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN '重要价值客户'
         WHEN r_score >= 3 AND f_score <  3 AND m_score >= 3 THEN '重要发展客户'
         WHEN r_score <  3 AND f_score >= 3 AND m_score >= 3 THEN '重要保持客户'
         WHEN r_score <  3 AND f_score <  3 AND m_score >= 3 THEN '重要挽留客户'
         WHEN r_score >= 3 AND f_score >= 3 AND m_score <  3 THEN '一般价值客户'
         WHEN r_score >= 3 AND f_score <  3 AND m_score <  3 THEN '一般发展客户'
         WHEN r_score <  3 AND f_score >= 3 AND m_score <  3 THEN '一般保持客户'
         ELSE '一般挽留客户'
       END AS segment
FROM v_rfm_scored;

-- Step 6. Segment summary (the table used in the resume / dashboard).
DROP TABLE IF EXISTS t_segment_summary;
CREATE TABLE t_segment_summary AS
SELECT segment,
       COUNT(*) AS user_count,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_user_segments), 1) AS pct_users,
       ROUND(AVG(recency_days), 1) AS avg_recency_days,
       ROUND(AVG(frequency), 2) AS avg_frequency,
       ROUND(AVG(monetary), 2) AS avg_monetary,
       ROUND(SUM(monetary), 2) AS total_monetary,
       ROUND(100.0 * SUM(monetary) / (SELECT SUM(monetary) FROM v_user_segments), 1) AS pct_revenue
FROM v_user_segments
GROUP BY segment;
