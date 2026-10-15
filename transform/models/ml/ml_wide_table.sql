{{ config(materialized='table') }}

-- BigQuery translation of the approved MotherDuck model.
-- Grain: exactly one row per labeled Olist order_id.
-- Preserves the original MotherDuck logic, including filtering out NULL targets.
WITH orders_base AS (
    SELECT
        order_id,
        customer_id,
        order_purchase_timestamp,
        late_delivery,
        EXTRACT(MONTH FROM order_purchase_timestamp) AS purchase_month,
        EXTRACT(DAYOFWEEK FROM order_purchase_timestamp) - 1 AS purchase_weekday
    FROM {{ ref('fct_orders') }}
),

geo_by_zip AS (
    -- Exact median coordinate per ZIP prefix, matching MotherDuck MEDIAN().
    SELECT
        zip_code,
        latitude,
        longitude
    FROM (
        SELECT
            geolocation_zip_code_prefix AS zip_code,
            PERCENTILE_CONT(geolocation_lat, 0.5 IGNORE NULLS)
                OVER (PARTITION BY geolocation_zip_code_prefix) AS latitude,
            PERCENTILE_CONT(geolocation_lng, 0.5 IGNORE NULLS)
                OVER (PARTITION BY geolocation_zip_code_prefix) AS longitude,
            ROW_NUMBER() OVER (
                PARTITION BY geolocation_zip_code_prefix
                ORDER BY geolocation_zip_code_prefix
            ) AS rn
        FROM {{ ref('stg_geolocation') }}
        WHERE geolocation_lat BETWEEN -90 AND 90
          AND geolocation_lng BETWEEN -180 AND 180
    )
    WHERE rn = 1
),

item_enriched AS (
    SELECT
        oi.order_id,
        oi.order_item_id,
        oi.product_id,
        oi.seller_id,
        oi.price,
        oi.freight_value,
        oi.shipping_limit_date,
        o.order_purchase_timestamp,
        COALESCE(
            NULLIF(TRIM(p.product_category_name), ''),
            'unknown'
        ) AS product_category_name,
        p.product_weight_g,
        p.product_length_cm,
        p.product_height_cm,
        p.product_width_cm,
        s.seller_state,
        gc.latitude AS customer_latitude,
        gc.longitude AS customer_longitude,
        gs.latitude AS seller_latitude,
        gs.longitude AS seller_longitude
    FROM {{ ref('fct_order_items') }} AS oi
    LEFT JOIN orders_base AS o
        ON oi.order_id = o.order_id
    LEFT JOIN {{ ref('dim_products') }} AS p
        ON oi.product_id = p.product_id
    LEFT JOIN {{ ref('dim_sellers') }} AS s
        ON oi.seller_id = s.seller_id
    LEFT JOIN {{ ref('dim_customers') }} AS c
        ON o.customer_id = c.customer_id
    LEFT JOIN geo_by_zip AS gc
        ON c.customer_zip_code_prefix = gc.zip_code
    LEFT JOIN geo_by_zip AS gs
        ON s.seller_zip_code_prefix = gs.zip_code
),

item_metrics AS (
    SELECT
        *,
        CASE
            WHEN order_purchase_timestamp IS NOT NULL
             AND shipping_limit_date IS NOT NULL
            THEN TIMESTAMP_DIFF(
                shipping_limit_date,
                order_purchase_timestamp,
                SECOND
            ) / 86400.0
            ELSE NULL
        END AS seller_prep_days_raw,
        CASE
            WHEN customer_latitude IS NOT NULL
             AND customer_longitude IS NOT NULL
             AND seller_latitude IS NOT NULL
             AND seller_longitude IS NOT NULL
            THEN 6371.0 * 2 * ASIN(
                SQRT(
                    LEAST(
                        1.0,
                        GREATEST(
                            0.0,
                            POWER(
                                SIN(((seller_latitude - customer_latitude) * ACOS(-1.0) / 180.0) / 2),
                                2
                            )
                            + COS(customer_latitude * ACOS(-1.0) / 180.0)
                            * COS(seller_latitude * ACOS(-1.0) / 180.0)
                            * POWER(
                                SIN(((seller_longitude - customer_longitude) * ACOS(-1.0) / 180.0) / 2),
                                2
                            )
                        )
                    )
                )
            )
            ELSE NULL
        END AS distance_km_item
    FROM item_enriched
),

prep_threshold AS (
    -- Exact 99.9th percentile over non-negative preparation intervals.
    SELECT p999
    FROM (
        SELECT
            PERCENTILE_CONT(seller_prep_days_raw, 0.999 IGNORE NULLS)
                OVER () AS p999,
            ROW_NUMBER() OVER () AS rn
        FROM item_metrics
        WHERE seller_prep_days_raw >= 0
    )
    WHERE rn = 1
),

prep_summary AS (
    SELECT
        i.order_id,
        MIN(
            CASE
                WHEN i.seller_prep_days_raw >= 0
                 AND i.seller_prep_days_raw <= t.p999
                THEN i.seller_prep_days_raw
                ELSE NULL
            END
        ) AS seller_prep_days
    FROM item_metrics AS i
    CROSS JOIN prep_threshold AS t
    GROUP BY i.order_id
),

item_summary AS (
    SELECT
        order_id,
        COUNT(*) AS item_count,
        SUM(price) AS order_value,
        SUM(freight_value) AS freight_value,
        CASE
            WHEN COUNT(product_weight_g) = COUNT(*)
            THEN SUM(product_weight_g)
            ELSE NULL
        END AS total_product_weight_g,
        MAX(product_weight_g) AS max_product_weight_g,
        MAX(product_length_cm) AS max_product_length_cm,
        MAX(product_height_cm) AS max_product_height_cm,
        MAX(product_width_cm) AS max_product_width_cm,
        MAX(distance_km_item) AS distance_km
    FROM item_metrics
    GROUP BY order_id
),

category_summary AS (
    SELECT
        order_id,
        product_category_name,
        SUM(price) AS category_order_value
    FROM item_metrics
    GROUP BY order_id, product_category_name
),

ranked_categories AS (
    SELECT
        order_id,
        product_category_name,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY category_order_value DESC, product_category_name ASC
        ) AS rn
    FROM category_summary
),

seller_summary AS (
    SELECT
        order_id,
        seller_id,
        seller_state,
        SUM(price) AS seller_order_value
    FROM item_metrics
    GROUP BY order_id, seller_id, seller_state
),

ranked_sellers AS (
    SELECT
        order_id,
        seller_state,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY seller_order_value DESC, seller_id ASC
        ) AS rn
    FROM seller_summary
)

SELECT
    o.order_id,
    COALESCE(i.item_count, 0) AS item_count,
    i.order_value,
    i.freight_value,
    i.total_product_weight_g,
    i.max_product_weight_g,
    i.max_product_length_cm,
    i.max_product_height_cm,
    i.max_product_width_cm,
    COALESCE(cat.product_category_name, 'unknown') AS product_category_name,
    COALESCE(c.customer_state, 'unknown') AS customer_state,
    COALESCE(seller.seller_state, 'unknown') AS seller_state,
    o.purchase_month,
    o.purchase_weekday,
    prep.seller_prep_days,
    i.distance_km,
    o.late_delivery
FROM orders_base AS o
LEFT JOIN item_summary AS i
    ON o.order_id = i.order_id
LEFT JOIN ranked_categories AS cat
    ON o.order_id = cat.order_id
   AND cat.rn = 1
LEFT JOIN ranked_sellers AS seller
    ON o.order_id = seller.order_id
   AND seller.rn = 1
LEFT JOIN {{ ref('dim_customers') }} AS c
    ON o.customer_id = c.customer_id
LEFT JOIN prep_summary AS prep
    ON o.order_id = prep.order_id
-- Preserve all orders: late_delivery may be NULL when no reliable label exists.
-- The ML training step should filter to non-NULL targets before fitting a model.
