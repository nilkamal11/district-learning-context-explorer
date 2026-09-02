CREATE OR REPLACE TABLE mart_exclusion_audit AS
SELECT
    'multi_component_unit' AS exclusion_reason,
    count(*) AS source_rows,
    count(DISTINCT district_id) AS districts,
    min(year) AS first_year,
    max(year) AS last_year,
    string_agg(DISTINCT state_abbreviation, ', ' ORDER BY state_abbreviation)
        AS state_abbreviations
FROM stg_achievement
WHERE coalesce(multi_component_flag, 0) = 1;
