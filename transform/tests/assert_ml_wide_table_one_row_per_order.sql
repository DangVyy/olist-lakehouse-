SELECT
    order_id
FROM {{ ref('ml_wide_table') }}
GROUP BY order_id
HAVING COUNT(*) > 1
