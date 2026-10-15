{{ config(materialized='table') }}

WITH ranked_items AS (
    SELECT
        order_id,
        order_item_id,
        product_id,
        seller_id,
        shipping_limit_date,
        price,
        freight_value,
        ROW_NUMBER() OVER (
            PARTITION BY order_id, order_item_id
            ORDER BY product_id, seller_id, price DESC, freight_value DESC
        ) AS row_num
    FROM {{ ref('stg_order_items') }}
    WHERE order_id IS NOT NULL
      AND order_item_id IS NOT NULL
), deduplicated_items AS (
    SELECT
        order_id,
        order_item_id,
        product_id,
        seller_id,
        shipping_limit_date,
        price,
        freight_value
    FROM ranked_items
    WHERE row_num = 1
)
SELECT
    oi.order_id,
    oi.order_item_id,
    fo.customer_id,
    DATE(fo.order_purchase_timestamp) AS order_date,
    COALESCE(dp.product_id, oi.product_id) AS product_id,
    COALESCE(ds.seller_id, oi.seller_id) AS seller_id,
    oi.shipping_limit_date,
    oi.price,
    oi.freight_value,
    COALESCE(oi.price, 0) + COALESCE(oi.freight_value, 0) AS item_total_value
FROM deduplicated_items AS oi
LEFT JOIN {{ ref('fct_orders') }} AS fo
    ON oi.order_id = fo.order_id
LEFT JOIN {{ ref('dim_products') }} AS dp
    ON oi.product_id = dp.product_id
LEFT JOIN {{ ref('dim_sellers') }} AS ds
    ON oi.seller_id = ds.seller_id
