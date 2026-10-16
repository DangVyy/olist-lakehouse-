
{{ config(materialized='table') }}

SELECT
    NULLIF(TRIM(CAST(order_id AS STRING)), '') AS order_id,
    SAFE_CAST(payment_sequential AS INT64) AS payment_sequential,
    LOWER(NULLIF(TRIM(CAST(payment_type AS STRING)), ''))
        AS payment_type,
    SAFE_CAST(payment_installments AS INT64) AS payment_installments,
    SAFE_CAST(payment_value AS NUMERIC) AS payment_value

FROM {{ source('bronze', 'payments') }}

WHERE NULLIF(TRIM(CAST(order_id AS STRING)), '') IS NOT NULL
