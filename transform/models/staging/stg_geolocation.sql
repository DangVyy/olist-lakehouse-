
{{ config(materialized='table') }}

SELECT
    SAFE_CAST(geolocation_zip_code_prefix AS INT64)
        AS geolocation_zip_code_prefix,

    SAFE_CAST(geolocation_lat AS FLOAT64) AS geolocation_lat,
    SAFE_CAST(geolocation_lng AS FLOAT64) AS geolocation_lng,

    LOWER(NULLIF(TRIM(CAST(geolocation_city AS STRING)), ''))
        AS geolocation_city,

    UPPER(NULLIF(TRIM(CAST(geolocation_state AS STRING)), ''))
        AS geolocation_state

FROM {{ source('bronze', 'geolocation') }}

WHERE SAFE_CAST(geolocation_zip_code_prefix AS INT64) IS NOT NULL
