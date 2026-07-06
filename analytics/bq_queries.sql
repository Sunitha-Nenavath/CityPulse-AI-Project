-- CityPulse AI - BigQuery SQL Queries for Civic Intelligence

-- Query 1: Weekly Complaints per Ward
-- Aggregates complaints by ward and week to show geographical distribution and volume.
SELECT
  ward_name,
  DATE_TRUNC(DATE(timestamp), WEEK) AS complaint_week,
  COUNT(complaint_id) AS complaint_count
FROM
  `YOUR_PROJECT.YOUR_DATASET.YOUR_TABLE`
GROUP BY
  ward_name,
  complaint_week
ORDER BY
  complaint_week DESC,
  complaint_count DESC;


-- Query 2: Category Trends Over Time (Weekly Aggregation)
-- Tracks category breakdown weekly to observe shift in citizen concerns (e.g. rising pothole reports).
SELECT
  category_classified AS category,
  DATE_TRUNC(DATE(timestamp), WEEK) AS complaint_week,
  COUNT(complaint_id) AS complaint_count
FROM
  `YOUR_PROJECT.YOUR_DATASET.YOUR_TABLE`
GROUP BY
  category,
  complaint_week
ORDER BY
  complaint_week DESC,
  complaint_count DESC;


-- Query 3: Week-over-Week (WoW) Spike Detection per Ward and Category
-- Computes the week-over-week percentage change in complaints.
-- Highlight combos where wow_growth_percentage > 50% for anomaly flagging.
WITH WeeklyComplaints AS (
  SELECT
    ward_name,
    category_classified AS category,
    DATE_TRUNC(DATE(timestamp), WEEK) AS complaint_week,
    COUNT(complaint_id) AS current_week_count
  FROM
    `YOUR_PROJECT.YOUR_DATASET.YOUR_TABLE`
  GROUP BY
    ward_name,
    category,
    complaint_week
),
WeeklyLags AS (
  SELECT
    ward_name,
    category,
    complaint_week,
    current_week_count,
    LAG(current_week_count, 1) OVER (
      PARTITION BY ward_name, category
      ORDER BY complaint_week
    ) AS prev_week_count
  FROM
    WeeklyComplaints
)
SELECT
  ward_name,
  category,
  complaint_week,
  current_week_count,
  COALESCE(prev_week_count, 0) AS prev_week_count,
  CASE
    WHEN COALESCE(prev_week_count, 0) = 0 AND current_week_count > 0 THEN 100.0
    WHEN COALESCE(prev_week_count, 0) = 0 AND current_week_count = 0 THEN 0.0
    ELSE ROUND(((current_week_count - prev_week_count) / prev_week_count) * 100.0, 2)
  END AS wow_growth_percentage
FROM
  WeeklyLags
ORDER BY
  complaint_week DESC,
  wow_growth_percentage DESC;
