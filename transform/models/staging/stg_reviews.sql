
{{ config(materialized='table') }}

SELECT
    NULLIF(TRIM(CAST(review_id AS STRING)), '') AS review_id,
    NULLIF(TRIM(CAST(order_id AS STRING)), '') AS order_id,
    SAFE_CAST(review_score AS INT64) AS review_score,

    NULLIF(TRIM(CAST(review_comment_title AS STRING)), '')
        AS review_comment_title,

    NULLIF(TRIM(CAST(review_comment_message AS STRING)), '')
        AS review_comment_message,

    SAFE_CAST(
        NULLIF(TRIM(CAST(review_creation_date AS STRING)), '')
        AS TIMESTAMP
    ) AS review_creation_date,

    SAFE_CAST(
        NULLIF(TRIM(CAST(review_answer_timestamp AS STRING)), '')
        AS TIMESTAMP
    ) AS review_answer_timestamp

FROM {{ source('bronze', 'reviews') }}

WHERE NULLIF(TRIM(CAST(order_id AS STRING)), '') IS NOT NULL
