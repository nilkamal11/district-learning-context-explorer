CREATE OR REPLACE TABLE mart_illinois_grade4_coverage AS
SELECT
    report_card_year,
    count(*) AS row_count,
    count(DISTINCT rcdts) AS school_count,
    count(*) FILTER (WHERE proficiency_status = 'reported') AS proficiency_reported,
    count(*) FILTER (WHERE proficiency_status = 'suppressed') AS proficiency_suppressed,
    count(*) FILTER (WHERE growth_status = 'reported') AS growth_reported,
    count(*) FILTER (WHERE growth_status = 'suppressed') AS growth_suppressed,
    count(*) FILTER (WHERE growth_status = 'not_published') AS growth_not_published
FROM stg_illinois_grade4
GROUP BY report_card_year
ORDER BY report_card_year;
