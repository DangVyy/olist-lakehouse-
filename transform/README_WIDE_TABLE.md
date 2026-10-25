# TV2 Wide Table handoff (BigQuery)

This add-on contains only the Wide Table output and its data tests. It does not
contain model-training or dashboard code.

The output columns match the approved brainstorm design exactly (17 columns):
`order_id`, `item_count`, `order_value`, `freight_value`,
`total_product_weight_g`, `max_product_weight_g`, `max_product_length_cm`,
`max_product_height_cm`, `max_product_width_cm`, `product_category_name`,
`customer_state`, `seller_state`, `purchase_month`, `purchase_weekday`,
`seller_prep_days`, `distance_km`, `late_delivery`.

The model keeps orders with `late_delivery IS NULL`, as the design allows a NULL
target when a reliable label is unavailable. This differs from the original
MotherDuck SQL's final `WHERE late_delivery IN (0, 1)`, which filtered those rows
out. For model training, the ML owner should filter to non-NULL `late_delivery`
rows in the training query/data preparation, while keeping `order_id` out of
predictor features.

BigQuery translations used:
- `MEDIAN` -> analytic `PERCENTILE_CONT(..., 0.5 IGNORE NULLS)` by ZIP prefix.
- `QUANTILE_CONT(..., 0.999)` -> analytic `PERCENTILE_CONT(..., 0.999 IGNORE NULLS)`.
- `DATE_DIFF('second', start, end)` -> `TIMESTAMP_DIFF(end, start, SECOND)`.
- MotherDuck `DOW` (Sunday=0) -> BigQuery `DAYOFWEEK - 1` (Sunday=0).
- `RADIANS(x)` -> `x * ACOS(-1.0) / 180.0`.

After adding this model, compile and run it only after verifying the `ml` schema
configuration in `dbt_project.yml`. Then run `dbt test --select ml.*`.
