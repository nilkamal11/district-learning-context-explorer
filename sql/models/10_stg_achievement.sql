CREATE OR REPLACE TABLE stg_achievement AS
SELECT
    -- Normalize numeric-looking IDs, then restore SEDA's seven-character format.
    lpad(CAST(CAST(sedaadmin AS BIGINT) AS VARCHAR), 7, '0') AS district_id,
    trim(sedaadminname) AS district_name,
    lower(trim(subject)) AS subject,
    -- Unexpected source values remain NULL for QA instead of stopping the full load.
    TRY_CAST(grade AS SMALLINT) AS grade,
    TRY_CAST(year AS SMALLINT) AS year,
    TRY_CAST(fips AS SMALLINT) AS state_fips,
    upper(trim(stateabb)) AS state_abbreviation,
    TRY_CAST(multi_comp_all AS SMALLINT) AS multi_component_flag,
    TRY_CAST(tot_asmt_all AS BIGINT) AS tested_count,
    TRY_CAST(flag_estasmt_all AS SMALLINT) AS tested_count_estimated_flag,
    TRY_CAST(cs_mn_all AS DOUBLE) AS achievement_cs,
    TRY_CAST(cs_mn_se_all AS DOUBLE) AS standard_error_within_state,
    TRY_CAST(cs_mn_se_adj_all AS DOUBLE) AS standard_error_cross_state,
    md5(
        concat_ws(
            '|',
            coalesce(sedaadmin, '<NULL>'),
            coalesce(sedaadminname, '<NULL>'),
            coalesce(subject, '<NULL>'),
            coalesce(grade, '<NULL>'),
            coalesce(year, '<NULL>'),
            coalesce(fips, '<NULL>'),
            coalesce(stateabb, '<NULL>'),
            coalesce(multi_comp_all, '<NULL>'),
            coalesce(tot_asmt_all, '<NULL>'),
            coalesce(flag_estasmt_all, '<NULL>'),
            coalesce(cs_mn_all, '<NULL>'),
            coalesce(cs_mn_se_all, '<NULL>'),
            coalesce(cs_mn_se_adj_all, '<NULL>')
        )
    ) AS source_row_hash
-- A quoted district name containing a comma broke the full-file autodetected
-- parse, so delimiter, quote, escape, and input type are pinned here.
FROM read_csv_auto(
    '{{ achievement_path }}',
    header = true,
    delim = ',',
    quote = '"',
    escape = '"',
    all_varchar = true,
    sample_size = 200000,
    parallel = true
)
WHERE lower(trim(subject)) IN ('mth', 'rla');
