
{{ config(materialized='table') }}

SELECT
    NULLIF(TRIM(CAST(product_category_name AS STRING)), '')
        AS product_category_name,

    NULLIF(TRIM(CAST(product_category_name_english AS STRING)), '')
        AS product_category_name_english

FROM {{ source('bronze', 'category_translation') }}

WHERE NULLIF(TRIM(CAST(product_category_name AS STRING)), '') IS NOT NULL
