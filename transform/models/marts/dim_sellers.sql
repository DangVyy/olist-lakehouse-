{{ config(materialized='table') }}

WITH ranked_sellers AS (
    SELECT
        seller_id,
        seller_zip_code_prefix,
        seller_city,
        seller_state,
        ROW_NUMBER() OVER (
            PARTITION BY seller_id
            ORDER BY seller_zip_code_prefix, seller_city, seller_state
        ) AS row_num
    FROM {{ ref('stg_sellers') }}
    WHERE seller_id IS NOT NULL
)
SELECT
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state
FROM ranked_sellers
WHERE row_num = 1
