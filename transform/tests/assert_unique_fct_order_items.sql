SELECT
    order_id,
    order_item_id,
    COUNT(*) AS row_count
FROM {{ ref('fct_order_items') }}
GROUP BY order_id, order_item_id
HAVING COUNT(*) > 1
