CREATE OR REPLACE TABLE mart_illinois_rcdts_identity_audit AS
SELECT
    rcdts,
    min(report_card_year) AS first_year,
    max(report_card_year) AS last_year,
    count(DISTINCT school_name) AS school_name_versions,
    count(DISTINCT district_name) AS district_name_versions,
    string_agg(DISTINCT school_name, ' | ' ORDER BY school_name) AS school_names,
    string_agg(DISTINCT district_name, ' | ' ORDER BY district_name) AS district_names,
    school_name_versions > 1 OR district_name_versions > 1 AS identity_review_needed
FROM stg_illinois_school_roster
GROUP BY rcdts;
