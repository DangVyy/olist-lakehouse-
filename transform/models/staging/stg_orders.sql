
{{ config(materialized='table') }}

WITH source_data AS (

    SELECT
        NULLIF(TRIM(CAST(order_id AS STRING)), '') AS order_id,
        NULLIF(TRIM(CAST(customer_id AS STRING)), '') AS customer_id,
        LOWER(NULLIF(TRIM(CAST(order_status AS STRING)), ''))
            AS order_status,

        SAFE_CAST(
            NULLIF(TRIM(CAST(order_purchase_timestamp AS STRING)), '')
            AS TIMESTAMP
        ) AS order_purchase_timestamp,

        SAFE_CAST(
            NULLIF(TRIM(CAST(order_approved_at AS STRING)), '')
            AS TIMESTAMP
        ) AS order_approved_at,

        SAFE_CAST(
            NULLIF(TRIM(CAST(order_delivered_carrier_date AS STRING)), '')
            AS TIMESTAMP
        ) AS order_delivered_carrier_date,

        SAFE_CAST(
            NULLIF(TRIM(CAST(order_delivered_customer_date AS STRING)), '')
            AS TIMESTAMP
        ) AS order_delivered_customer_date,

        SAFE_CAST(
            NULLIF(TRIM(CAST(order_estimated_delivery_date AS STRING)), '')
            AS TIMESTAMP
        ) AS order_estimated_delivery_date

    FROM {{ source('bronze', 'orders') }}

),

deduplicated AS (

    SELECT DISTINCT *
    FROM source_data
    WHERE order_id IS NOT NULL

)

SELECT *
FROM deduplicated
