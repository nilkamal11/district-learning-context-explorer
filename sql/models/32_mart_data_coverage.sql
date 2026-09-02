CREATE OR REPLACE TABLE mart_data_coverage AS
SELECT
    state_abbreviation,
    year,
    grade,
    subject,
    count(DISTINCT district_id) AS reporting_districts,
    sum(tested_count) AS represented_assessments,
    count_if(low_precision_flag) AS low_precision_districts
FROM mart_achievement
GROUP BY state_abbreviation, year, grade, subject;
