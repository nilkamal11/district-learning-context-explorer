CREATE OR REPLACE TABLE mart_achievement AS
SELECT
    a.*,
    CASE a.subject WHEN 'mth' THEN 'Mathematics' WHEN 'rla' THEN 'Reading / language arts' END
        AS subject_label,
    CASE
        WHEN a.year BETWEEN 2009 AND 2019 THEN 'pre_2020'
        WHEN a.year BETWEEN 2022 AND 2025 THEN 'post_2021'
        ELSE 'out_of_scope'
    END AS reporting_period,
    CAST(a.year - 1 AS VARCHAR) || '-' || right(CAST(a.year AS VARCHAR), 2) AS school_year,
    a.tested_count < 50
        OR coalesce(a.tested_count_estimated_flag, 0) = 1
        OR (1.959964 * a.standard_error_within_state) > 0.50 AS low_precision_flag
FROM stg_achievement AS a
WHERE a.grade BETWEEN 3 AND 8
  AND a.year IN (2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019,
                 2022, 2023, 2024, 2025)
  AND coalesce(a.multi_component_flag, 0) = 0
  AND a.achievement_cs IS NOT NULL
  AND a.standard_error_within_state IS NOT NULL
  AND a.standard_error_cross_state IS NOT NULL;
