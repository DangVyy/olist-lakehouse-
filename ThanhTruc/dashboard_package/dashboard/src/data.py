"""data.py - Kết nối BigQuery và tải dữ liệu cho Dashboard.

Cách xác thực (tự chọn theo môi trường):
  1. Có mục [gcp_service_account] trong Streamlit Secrets  -> dùng Service Account (khi deploy).
  2. Không có                                               -> dùng đăng nhập Google trên máy
                                                               (gcloud auth application-default login).
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st
from google.cloud import bigquery

from . import config as cfg

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/bigquery"]

NUMERIC_COLUMNS = [
    "late_probability", "item_count", "order_value", "freight_value",
    "total_product_weight_g", "max_product_weight_g", "max_product_length_cm",
    "max_product_height_cm", "max_product_width_cm", "purchase_month",
    "purchase_weekday", "seller_prep_days", "distance_km",
]
TEXT_COLUMNS = [
    "order_id", "risk_level", "top_risk_factor_1", "top_risk_factor_2",
    "customer_state", "seller_state", "product_category_name",
    "year_month", "order_status",
]


def _secret_section(name: str):
    """Đọc một mục trong st.secrets. Trả None nếu không có (ví dụ khi chạy trong notebook)."""
    try:
        if name in st.secrets:
            return dict(st.secrets[name])
    except Exception:
        pass
    return None


@st.cache_resource(show_spinner=False)
def get_bq_client() -> bigquery.Client:
    info = _secret_section("gcp_service_account")
    if info:
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        return bigquery.Client(project=cfg.PROJECT_ID, credentials=creds)
    return bigquery.Client(project=cfg.PROJECT_ID)


def build_query(with_orders: bool = True) -> str:
    """JOIN bảng dự đoán với Wide Table (và fct_orders nếu có quyền) theo order_id."""
    if with_orders:
        extra_select = (
            ",\n  FORMAT_DATE('%Y-%m', DATE(o.order_purchase_timestamp)) AS year_month"
            ",\n  o.order_status AS order_status"
        )
        extra_join = f"LEFT JOIN `{cfg.ORDERS_TABLE}` AS o ON p.order_id = o.order_id"
    else:
        extra_select = (
            ",\n  CAST(NULL AS STRING) AS year_month"
            ",\n  CAST(NULL AS STRING) AS order_status"
        )
        extra_join = ""
    return f"""
SELECT
  p.order_id,
  p.late_probability,
  p.predicted_late,
  p.risk_level,
  p.top_risk_factor_1,
  p.top_risk_factor_2,
  w.late_delivery AS actual_late,
  w.customer_state,
  w.seller_state,
  w.product_category_name,
  w.purchase_month,
  w.purchase_weekday,
  w.item_count,
  CAST(w.order_value AS FLOAT64) AS order_value,
  CAST(w.freight_value AS FLOAT64) AS freight_value,
  w.total_product_weight_g,
  w.max_product_weight_g,
  w.max_product_length_cm,
  w.max_product_height_cm,
  w.max_product_width_cm,
  w.seller_prep_days,
  w.distance_km{extra_select}
FROM `{cfg.PRED_TABLE}` AS p
INNER JOIN `{cfg.WIDE_TABLE}` AS w ON p.order_id = w.order_id
{extra_join}
""".strip()


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Đưa các cột về kiểu dữ liệu đơn giản (float / int / chuỗi) để xử lý ổn định."""
    df = df.copy()
    for col in NUMERIC_COLUMNS + ["actual_late"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df["predicted_late"] = pd.to_numeric(df["predicted_late"], errors="coerce").fillna(0).astype(int)
    for col in TEXT_COLUMNS:
        df[col] = df[col].astype("object").where(df[col].notna(), None)
    return df


@st.cache_data(ttl=cfg.CACHE_TTL_SECONDS, show_spinner="Đang tải dữ liệu từ BigQuery...")
def load_dashboard_data() -> pd.DataFrame:
    client = get_bq_client()
    try:
        df = client.query(build_query(True)).to_dataframe(create_bqstorage_client=False)
    except Exception as exc:  # thường do chưa có quyền đọc olist_gold
        log.warning("Không đọc được %s, bỏ thông tin năm-tháng: %s", cfg.ORDERS_TABLE, exc)
        df = client.query(build_query(False)).to_dataframe(create_bqstorage_client=False)
    return clean_dataframe(df)
