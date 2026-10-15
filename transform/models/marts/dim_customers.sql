{{ config(materialized='table') }}

WITH ranked_customers AS (
    SELECT
        customer_id,
        customer_unique_id,
        customer_zip_code_prefix,
        customer_city,
        customer_state,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY customer_unique_id, customer_zip_code_prefix, customer_city, customer_state
        ) AS row_num
    FROM {{ ref('stg_customers') }}
    WHERE customer_id IS NOT NULL
)
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM ranked_customers
WHERE row_num = 1
