-- Campaign ROI with a sensitivity grid.
-- Reference notebook reports one ROI under hand-picked conversion assumptions;
-- a single scenario can flatter any strategy. This grid shows whether the
-- conclusion holds when the assumed coupon lift changes.
--
-- Strategy A (traditional): coupon the top-20% users by monetary.
-- Strategy B (precision): coupon high-value lapsing users from segmentation.

DROP TABLE IF EXISTS t_roi_sensitivity;
CREATE TABLE t_roi_sensitivity AS
WITH base AS (
  SELECT 10000.0 AS budget,
         10.0    AS coupon_cost,
         (SELECT AVG(monetary * 1.0 / frequency) FROM v_rfm_raw) AS aov
),
grid AS (
  SELECT 0.03 AS lift_trad, 0.10 AS lift_target
  UNION ALL SELECT 0.05, 0.15
  UNION ALL SELECT 0.08, 0.20
  UNION ALL SELECT 0.10, 0.25
),
trad_pool AS (
  SELECT user_id, monetary,
         NTILE(5) OVER (ORDER BY monetary DESC) AS bucket
  FROM v_rfm_raw
),
trad_cap AS (
  SELECT user_id, monetary,
         ROW_NUMBER() OVER (ORDER BY monetary DESC) AS rn
  FROM trad_pool WHERE bucket = 1
),
target_cap AS (
  SELECT user_id, monetary,
         ROW_NUMBER() OVER (ORDER BY monetary DESC) AS rn
  FROM v_user_segments
  WHERE segment IN ('重要挽留客户', '重要保持客户')
),
cnt AS (
  SELECT
    (SELECT COUNT(*) FROM trad_cap
      WHERE rn <= (SELECT CAST(budget / coupon_cost AS INTEGER) FROM base)) AS n_trad,
    (SELECT COUNT(*) FROM target_cap
      WHERE rn <= (SELECT CAST(budget / coupon_cost AS INTEGER) FROM base)) AS n_target
)
SELECT g.lift_trad,
       g.lift_target,
       ROUND(b.aov, 2) AS aov,
       c.n_trad,
       c.n_target,
       ROUND(c.n_trad * g.lift_trad * b.aov, 2)        AS trad_incremental_revenue,
       ROUND(c.n_target * g.lift_target * b.aov, 2)    AS target_incremental_revenue,
       ROUND(100.0 * (c.n_trad   * g.lift_trad   * b.aov - c.n_trad   * b.coupon_cost)
                   / NULLIF(c.n_trad   * b.coupon_cost, 0), 1) AS trad_roi_pct,
       ROUND(100.0 * (c.n_target * g.lift_target * b.aov - c.n_target * b.coupon_cost)
                   / NULLIF(c.n_target * b.coupon_cost, 0), 1) AS target_roi_pct
FROM grid g
CROSS JOIN base b
CROSS JOIN cnt c;
