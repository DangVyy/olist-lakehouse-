{{ config(materialized='table') }}

WITH ranked_orders AS (
    SELECT
        order_id,
        customer_id,
        order_status,
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY order_purchase_timestamp DESC, order_approved_at DESC, order_id
        ) AS row_num
    FROM {{ ref('stg_orders') }}
    WHERE order_id IS NOT NULL
), deduplicated_orders AS (
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
)
SELECT
    o.order_id,
    COALESCE(c.customer_id, o.customer_id) AS customer_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    CASE
        WHEN o.order_purchase_timestamp IS NOT NULL
         AND o.order_delivered_customer_date IS NOT NULL
        THEN DATE_DIFF(
            DATE(o.order_delivered_customer_date),
            DATE(o.order_purchase_timestamp),
            DAY
        )
        ELSE NULL
    END AS delivery_days,
    CASE
        WHEN o.order_delivered_customer_date IS NULL
          OR o.order_estimated_delivery_date IS NULL THEN NULL
        WHEN DATE(o.order_delivered_customer_date) > DATE(o.order_estimated_delivery_date) THEN 1
        ELSE 0
    END AS late_delivery,
    CASE
        WHEN o.order_purchase_timestamp IS NOT NULL
         AND o.order_approved_at IS NOT NULL
        THEN TIMESTAMP_DIFF(o.order_approved_at, o.order_purchase_timestamp, HOUR)
        ELSE NULL
    END AS approval_delay_hours
FROM deduplicated_orders AS o
LEFT JOIN {{ ref('dim_customers') }} AS c
    ON o.customer_id = c.customer_id
