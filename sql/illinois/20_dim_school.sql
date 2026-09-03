CREATE OR REPLACE TABLE dim_illinois_school AS
WITH roster_history AS (
    SELECT
        *,
        min(report_card_year) OVER (PARTITION BY rcdts) AS first_report_card_year,
        max(report_card_year) OVER (PARTITION BY rcdts) AS latest_report_card_year,
        row_number() OVER (
            PARTITION BY rcdts
            ORDER BY report_card_year DESC
        ) AS recency_rank
    FROM stg_illinois_school_roster
),
assessment_coverage AS (
    SELECT
        rcdts,
        min(report_card_year) AS first_grade4_result_year,
        max(report_card_year) AS latest_grade4_result_year
    FROM stg_illinois_grade4
    GROUP BY rcdts
)
SELECT
    roster.rcdts,
    roster.rcdts_formatted,
    roster.rcdts_source,
    roster.school_name,
    roster.district_name,
    roster.city,
    roster.county,
    roster.school_type,
    roster.grades_served,
    roster.school_enrollment,
    roster.school_enrollment_status,
    roster.first_report_card_year,
    roster.latest_report_card_year,
    coverage.first_grade4_result_year,
    coverage.latest_grade4_result_year,
    coverage.rcdts IS NOT NULL AS has_grade4_results
FROM roster_history AS roster
LEFT JOIN assessment_coverage AS coverage USING (rcdts)
WHERE roster.recency_rank = 1;
