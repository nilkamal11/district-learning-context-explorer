CREATE OR REPLACE TABLE stg_illinois_school_roster AS
SELECT
    try_cast(report_card_year AS INTEGER) AS report_card_year,
    trim(rcdts) AS rcdts,
    trim(rcdts_formatted) AS rcdts_formatted,
    trim(rcdts_source) AS rcdts_source,
    trim(school_name) AS school_name,
    trim(district_name) AS district_name,
    trim(city) AS city,
    trim(county) AS county,
    trim(school_type) AS school_type,
    trim(grades_served) AS grades_served,
    try_cast(school_enrollment AS DOUBLE) AS school_enrollment,
    trim(school_enrollment_status) AS school_enrollment_status,
    trim(source_file) AS source_file,
    trim(source_sheet) AS source_sheet
FROM read_csv(
    '{{ school_roster_csv_path }}',
    header = true,
    all_varchar = true,
    null_padding = true
);
