
{{ config(materialized='table') }}

SELECT DISTINCT
    NULLIF(TRIM(CAST(product_id AS STRING)), '') AS product_id,
    NULLIF(TRIM(CAST(product_category_name AS STRING)), '') AS product_category_name,

    SAFE_CAST(product_name_lenght AS INT64) AS product_name_length,
    SAFE_CAST(product_description_lenght AS INT64) AS product_description_length,
    SAFE_CAST(product_photos_qty AS INT64) AS product_photos_qty,

    SAFE_CAST(product_weight_g AS FLOAT64) AS product_weight_g,
    SAFE_CAST(product_length_cm AS FLOAT64) AS product_length_cm,
    SAFE_CAST(product_height_cm AS FLOAT64) AS product_height_cm,
    SAFE_CAST(product_width_cm AS FLOAT64) AS product_width_cm

FROM {{ source('bronze', 'products') }}
WHERE NULLIF(TRIM(CAST(product_id AS STRING)), '') IS NOT NULL
