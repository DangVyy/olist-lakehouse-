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

ranked_orders AS (

    -- Deduplicate at order grain, preferring the row with the most complete
    -- timestamp data; use stable tie-breakers if records are still tied.
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY
                (
                    IF(order_purchase_timestamp IS NOT NULL, 1, 0)
                  + IF(order_approved_at IS NOT NULL, 1, 0)
                  + IF(order_delivered_carrier_date IS NOT NULL, 1, 0)
                  + IF(order_delivered_customer_date IS NOT NULL, 1, 0)
                  + IF(order_estimated_delivery_date IS NOT NULL, 1, 0)
                ) DESC,
                IF(order_delivered_customer_date IS NULL, 1, 0),
                order_delivered_customer_date DESC,
                order_estimated_delivery_date DESC,
                order_delivered_carrier_date DESC,
                order_approved_at DESC,
                order_purchase_timestamp DESC,
                order_status ASC,
                customer_id ASC
        ) AS row_num
    FROM source_data
    WHERE order_id IS NOT NULL

)

SELECT
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date
FROM ranked_orders
WHERE row_num = 1
