CREATE OR REPLACE TABLE mart_context_snapshot AS
SELECT
    c.*,
    CASE
        WHEN c.grade_low <= 4 AND c.grade_high <= 8 THEN 'elementary_or_k8'
        WHEN c.grade_low <= 4 AND c.grade_high >= 9 THEN 'unified_or_k12'
        ELSE 'other'
    END AS grade_span_bucket,
    CASE lower(c.source_urbanicity)
        WHEN 'city' THEN 'City'
        WHEN 'suburb' THEN 'Suburb'
        WHEN 'town' THEN 'Town'
        WHEN 'rural' THEN 'Rural'
        ELSE NULL
    END AS dominant_locale,
    CASE
        WHEN greatest(c.share_city, c.share_suburb, c.share_town, c.share_rural) = c.share_city
            THEN 'City'
        WHEN greatest(c.share_city, c.share_suburb, c.share_town, c.share_rural) = c.share_suburb
            THEN 'Suburb'
        WHEN greatest(c.share_city, c.share_suburb, c.share_town, c.share_rural) = c.share_town
            THEN 'Town'
        WHEN greatest(c.share_city, c.share_suburb, c.share_town, c.share_rural) = c.share_rural
            THEN 'Rural'
        ELSE NULL
    END AS share_argmax_locale,
    CASE
        WHEN c.share_native_american IS NOT NULL
         AND c.share_asian IS NOT NULL
         AND c.share_hispanic IS NOT NULL
         AND c.share_black IS NOT NULL
         AND c.share_white IS NOT NULL
        THEN greatest(
            0.0,
            1.0 - c.share_native_american
                - c.share_asian
                - c.share_hispanic
                - c.share_black
                - c.share_white
        )
        ELSE NULL
    END AS share_other_race_ethnicity,
    c.grade_low <= 4 AND c.grade_high >= 4 AS serves_grade_4,
    -- Recent EL and special-education fields stay in staging for audit but are
    -- excluded from peer selection because both are constant at zero in 2024.
    c.total_enrollment_grades_3_8 > 0
        AND c.family_poverty_rate IS NOT NULL
        AND c.share_city IS NOT NULL
        AND c.share_suburb IS NOT NULL
        AND c.share_town IS NOT NULL
        AND c.share_rural IS NOT NULL
        AND c.share_native_american IS NOT NULL
        AND c.share_asian IS NOT NULL
        AND c.share_hispanic IS NOT NULL
        AND c.share_black IS NOT NULL
        AND c.share_white IS NOT NULL
        AND c.socioeconomic_status_composite IS NOT NULL AS has_core_peer_context,
    c.year = {{ context_year }} AS is_default_context_year
FROM stg_context AS c;
