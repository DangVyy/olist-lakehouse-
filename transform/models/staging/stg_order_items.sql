
{{ config(materialized='table') }}

SELECT DISTINCT
    NULLIF(TRIM(CAST(order_id AS STRING)), '') AS order_id,
    SAFE_CAST(order_item_id AS INT64) AS order_item_id,
    NULLIF(TRIM(CAST(product_id AS STRING)), '') AS product_id,
    NULLIF(TRIM(CAST(seller_id AS STRING)), '') AS seller_id,

    SAFE_CAST(
        NULLIF(TRIM(CAST(shipping_limit_date AS STRING)), '')
        AS TIMESTAMP
    ) AS shipping_limit_date,

    SAFE_CAST(price AS NUMERIC) AS price,
    SAFE_CAST(freight_value AS NUMERIC) AS freight_value

FROM {{ source('bronze', 'order_items') }}
WHERE NULLIF(TRIM(CAST(order_id AS STRING)), '') IS NOT NULL
