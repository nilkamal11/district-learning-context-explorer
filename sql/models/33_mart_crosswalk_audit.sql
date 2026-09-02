CREATE OR REPLACE TABLE mart_crosswalk_audit AS
SELECT
    year,
    state_abbreviation,
    count(*) AS mapping_rows,
    count(DISTINCT source_district_id) AS source_districts,
    count(DISTINCT stable_district_id) AS stable_districts,
    count_if(source_district_id <> stable_district_id) AS changed_stable_ids,
    count(imputed_flag) AS mappings_with_imputed_flag,
    count_if(imputed_flag = 1) AS imputed_mappings,
    count(latest_virtual_flag) AS mappings_with_virtual_flag,
    count_if(latest_virtual_flag = 1) AS virtual_mappings
FROM stg_crosswalk_admin
GROUP BY year, state_abbreviation;
