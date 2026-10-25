# TV2 — dbt Transform (BigQuery): Silver + Gold

This folder contains only the TV2-owned transformation scope: Bronze → Silver and Silver → Gold.
ML / Wide Table models are intentionally excluded because they belong to another team member.

## BigQuery resources

- GCP project: `olist-lakehouse-511407`
- Source dataset (Bronze): `olist_bronze`
- Silver output dataset: `olist_silver`
- Gold output dataset: `olist_gold`
- Location: `US`

## Local profile

Keep `profiles.yml` and any credentials outside the repository. The dbt profile name must match
`profile: olist_tv2_bq` in `dbt_project.yml`. Example OAuth profile:

```yaml
olist_tv2_bq:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: olist-lakehouse-511407
      dataset: olist_silver
      location: US
      threads: 4
```

Do not commit `profiles.yml`, tokens, service-account keys, `.venv`, `target`, or logs.

## Commands

Run commands from this `transform/` directory, and use the local profiles directory:

```powershell
dbt debug --profiles-dir <PATH_TO_LOCAL_PROFILES_DIRECTORY>
dbt parse --profiles-dir <PATH_TO_LOCAL_PROFILES_DIRECTORY>
dbt run --profiles-dir <PATH_TO_LOCAL_PROFILES_DIRECTORY> --select "staging.*"
dbt run --profiles-dir <PATH_TO_LOCAL_PROFILES_DIRECTORY> --select "marts.*"
dbt test --profiles-dir <PATH_TO_LOCAL_PROFILES_DIRECTORY> --select "marts.*"
```

The `generate_schema_name` macro maps each configured schema to its exact BigQuery dataset name,
so staging models target `olist_silver` and marts models target `olist_gold`.

## Model inventory

### Silver / staging
- `stg_category_translation`
- `stg_customers`
- `stg_geolocation`
- `stg_orders`
- `stg_order_items`
- `stg_payments`
- `stg_products`
- `stg_reviews`
- `stg_sellers`

### Gold / marts
- Dimensions: `dim_customers`, `dim_products`, `dim_sellers`
- Facts: `fct_orders`, `fct_order_items`

`fct_orders` is one row per `order_id`; it derives `delivery_days` and `late_delivery`.
`late_delivery` is `1` when the actual delivery date is later than the estimated date, `0` when delivered on or before the estimate, and `NULL` when a reliable label cannot be determined.

`fct_order_items` grain is `(order_id, order_item_id)`. The singular data test checks that this composite key is unique.

## Validation notes

The previously run BigQuery build created all 9 staging models and all 5 Gold models.
The most recent Gold test run reported 16 passing tests after correcting the numeric `accepted_values` test.
Re-run `dbt parse`, the staging/Gold builds, and the Gold tests after applying this reviewed package, because `stg_orders` now explicitly deduplicates by `order_id`.
