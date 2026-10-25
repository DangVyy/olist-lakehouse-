{{ config(materialized='table') }}

SELECT
    p.product_id,
    p.product_category_name,
    NULLIF(TRIM(ct.product_category_name_english), '') AS product_category_name_english,
    p.product_name_length,
    p.product_description_length,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm
FROM {{ ref('stg_products') }} AS p
LEFT JOIN {{ ref('stg_category_translation') }} AS ct
    ON p.product_category_name = ct.product_category_name
WHERE p.product_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY p.product_id
    ORDER BY
        IF(ct.product_category_name_english IS NULL, 1, 0),
        ct.product_category_name_english
) = 1
