CREATE OR REPLACE TABLE stg_context AS
WITH typed AS (
    SELECT
        lpad(CAST(CAST(sedaadmin AS BIGINT) AS VARCHAR), 7, '0') AS district_id,
        TRY_CAST(year AS SMALLINT) AS year,
        trim(sedaadminname) AS district_name,
        CASE
            WHEN lower(trim(CAST(gslo AS VARCHAR))) IN ('pre-kindergarten', 'prekindergarten', 'pk') THEN -1
            WHEN lower(trim(CAST(gslo AS VARCHAR))) IN ('kindergarten', 'k') THEN 0
            ELSE TRY_CAST(gslo AS SMALLINT)
        END AS grade_low,
        CASE
            WHEN lower(trim(CAST(gshi AS VARCHAR))) IN ('pre-kindergarten', 'prekindergarten', 'pk') THEN -1
            WHEN lower(trim(CAST(gshi AS VARCHAR))) IN ('kindergarten', 'k') THEN 0
            ELSE TRY_CAST(gshi AS SMALLINT)
        END AS grade_high,
        TRY_CAST(fips AS SMALLINT) AS state_fips,
        upper(trim(stateabb)) AS state_abbreviation,
        TRY_CAST(urban AS DOUBLE) AS share_city,
        TRY_CAST(suburb AS DOUBLE) AS share_suburb,
        TRY_CAST(town AS DOUBLE) AS share_town,
        TRY_CAST(rural AS DOUBLE) AS share_rural,
        TRY_CAST(pernam AS DOUBLE) AS share_native_american,
        TRY_CAST(perasn AS DOUBLE) AS share_asian,
        TRY_CAST(perhsp AS DOUBLE) AS share_hispanic,
        TRY_CAST(perblk AS DOUBLE) AS share_black,
        TRY_CAST(perwht AS DOUBLE) AS share_white,
        TRY_CAST(perell AS DOUBLE) AS source_perell,
        TRY_CAST(perspeced AS DOUBLE) AS source_perspeced,
        TRY_CAST(totenrl AS DOUBLE) AS enrollment_grades_3_8,
        TRY_CAST(povertyall AS DOUBLE) AS family_poverty_rate,
        TRY_CAST(sesall AS DOUBLE) AS socioeconomic_status_composite,
        trim(CAST(urbanicity AS VARCHAR)) AS source_urbanicity
    FROM read_csv_auto(
        '{{ context_path }}',
        header = true,
        delim = ',',
        quote = '"',
        escape = '"',
        all_varchar = true,
        sample_size = 200000,
        parallel = true
    )
)
SELECT * FROM typed;
