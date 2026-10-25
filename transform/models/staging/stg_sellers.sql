
{{ config(materialized='table') }}

SELECT DISTINCT
    NULLIF(TRIM(CAST(seller_id AS STRING)), '') AS seller_id,
    SAFE_CAST(seller_zip_code_prefix AS INT64) AS seller_zip_code_prefix,
    LOWER(NULLIF(TRIM(CAST(seller_city AS STRING)), '')) AS seller_city,
    UPPER(NULLIF(TRIM(CAST(seller_state AS STRING)), '')) AS seller_state
FROM {{ source('bronze', 'sellers') }}
WHERE NULLIF(TRIM(CAST(seller_id AS STRING)), '') IS NOT NULL
