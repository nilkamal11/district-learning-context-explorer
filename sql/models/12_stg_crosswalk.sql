-- TODO: add a historical ID bridge before joining external sources from before
-- 2022; the administrative-district rows in this release cover 2022-2025.
CREATE OR REPLACE TABLE stg_crosswalk_admin AS
SELECT
    lower(trim(geo)) AS geography_type,
    lpad(CAST(CAST(id AS BIGINT) AS VARCHAR), 7, '0') AS source_district_id,
    lpad(CAST(CAST(seda_id AS BIGINT) AS VARCHAR), 7, '0') AS stable_district_id,
    TRY_CAST(year AS SMALLINT) AS year,
    trim(name) AS district_name,
    upper(trim(stateabb)) AS state_abbreviation,
    TRY_CAST(fips AS SMALLINT) AS state_fips,
    TRY_CAST(fips_op AS SMALLINT) AS operating_state_fips,
    TRY_CAST(last_virtual AS SMALLINT) AS latest_virtual_flag,
    TRY_CAST(imputed AS SMALLINT) AS imputed_flag
FROM read_csv_auto(
    '{{ crosswalk_path }}',
    header = true,
    delim = ',',
    quote = '"',
    escape = '"',
    all_varchar = true,
    sample_size = 200000,
    parallel = true
)
WHERE lower(trim(geo)) = 'sedaadmin';
