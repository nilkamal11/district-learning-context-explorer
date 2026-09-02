CREATE OR REPLACE TABLE dim_district AS
WITH district_years AS (
    SELECT district_id, district_name, state_abbreviation, state_fips, year
    FROM stg_context
    UNION ALL
    SELECT district_id, district_name, state_abbreviation, state_fips, year
    FROM stg_achievement
),
latest AS (
    SELECT
        district_id,
        arg_max(district_name, year) AS district_name,
        arg_max(state_abbreviation, year) AS state_abbreviation,
        arg_max(state_fips, year) AS state_fips,
        min(year) AS first_year,
        max(year) AS last_year
    FROM district_years
    GROUP BY district_id
)
SELECT * FROM latest;
