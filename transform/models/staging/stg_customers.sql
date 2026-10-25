
{{ config(materialized='table') }}

SELECT DISTINCT
    NULLIF(TRIM(CAST(customer_id AS STRING)), '') AS customer_id,
    NULLIF(TRIM(CAST(customer_unique_id AS STRING)), '') AS customer_unique_id,
    SAFE_CAST(customer_zip_code_prefix AS INT64) AS customer_zip_code_prefix,
    LOWER(NULLIF(TRIM(CAST(customer_city AS STRING)), '')) AS customer_city,
    UPPER(NULLIF(TRIM(CAST(customer_state AS STRING)), '')) AS customer_state
FROM {{ source('bronze', 'customers') }}
WHERE NULLIF(TRIM(CAST(customer_id AS STRING)), '') IS NOT NULL
