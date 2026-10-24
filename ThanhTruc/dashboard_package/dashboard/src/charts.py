"""charts.py - Tính KPI và dựng biểu đồ (Plotly) cho Dashboard."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import config as cfg
from .factors import describe_factor, fmt_number, fmt_pct

TEAL = "#0F766E"
RED = "#8F1D14"
GREY = "#6B7280"


# =========================================================================
# KPI
# =========================================================================
def compute_kpis(df: pd.DataFrame) -> dict:
    """Các chỉ số tổng quan. Mọi con số đều tính trực tiếp từ dữ liệu đang lọc."""
    labeled = df["actual_late"].notna()
    high = df["risk_level"] == cfg.RISK_HIGH
    high_labeled = high & labeled
    return {
        "total_orders": int(len(df)),
        "labeled_orders": int(labeled.sum()),
        "actual_late_rate": df.loc[labeled, "actual_late"].mean() if labeled.any() else float("nan"),
        "predicted_late_rate": df["predicted_late"].mean() if len(df) else float("nan"),
        "high_risk_orders": int(high.sum()),
        "high_risk_actual_late_rate": (
            df.loc[high_labeled, "actual_late"].mean() if high_labeled.any() else float("nan")
        ),
        "avg_probability": df["late_probability"].mean() if len(df) else float("nan"),
    }


def render_kpis(k: dict) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tổng số đơn", fmt_number(k["total_orders"]))
    c2.metric(
        "Tỷ lệ trễ thực tế", fmt_pct(k["actual_late_rate"]),
        help=f"Tính trên {fmt_number(k['labeled_orders'])} đơn có nhãn thật (đã biết trễ hay không).",
    )
    c3.metric(
        "Tỷ lệ mô hình dự báo trễ", fmt_pct(k["predicted_late_rate"]),
        help="Mô hình cố ý cảnh báo rộng để ít bỏ sót, nên con số này cao hơn tỷ lệ trễ thực tế.",
    )
    c4.metric("Số đơn nguy cơ cao", fmt_number(k["high_risk_orders"]))
    c5.metric(
        "Đơn nguy cơ cao thật sự trễ", fmt_pct(k["high_risk_actual_late_rate"]),
        help="Trong nhóm nguy cơ cao có nhãn thật, bao nhiêu % đúng là đã trễ. Cho biết độ tin cậy của cảnh báo.",
    )
    st.caption(f"Xác suất trễ trung bình của các đơn đang lọc: {fmt_pct(k['avg_probability'])}")


# =========================================================================
# Biểu đồ
# =========================================================================
def _style(fig: go.Figure, title: str, height: int = 340) -> go.Figure:
    fig.update_layout(
        template="plotly_white", title=dict(text=title, x=0, font=dict(size=15)),
        height=height, margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def has_time(df: pd.DataFrame) -> bool:
    return "year_month" in df.columns and df["year_month"].notna().any()


def fig_risk_distribution(df: pd.DataFrame) -> go.Figure:
    counts = df["risk_level"].value_counts().reindex(cfg.RISK_ORDER).fillna(0).astype(int)
    fig = go.Figure(go.Bar(
        x=[cfg.RISK_LABEL_VI[k] for k in counts.index], y=counts.values,
        marker_color=[cfg.RISK_COLORS[k] for k in counts.index],
        text=[fmt_number(v) for v in counts.values], textposition="outside",
    ))
    fig.update_yaxes(title="Số đơn")
    fig.update_xaxes(title="Mức rủi ro")
    return _style(fig, "Phân bố đơn theo mức rủi ro")


def fig_state_rates(df: pd.DataFrame, top_n: int = 10) -> go.Figure | None:
    g = df.groupby("customer_state").agg(
        n=("order_id", "size"), actual=("actual_late", "mean"), predicted=("predicted_late", "mean"),
    ).reset_index()
    g = g[g["n"] >= cfg.MIN_ORDERS_FOR_STATE_CHART].dropna(subset=["actual"])
    if g.empty:
        return None
    g = g.sort_values("actual", ascending=False).head(top_n)
    fig = go.Figure()
    fig.add_bar(x=g["customer_state"], y=g["actual"] * 100, name="Trễ thực tế", marker_color=TEAL,
                text=[f"{v:.1f}%" for v in g["actual"] * 100], textposition="outside")
    fig.add_bar(x=g["customer_state"], y=g["predicted"] * 100, name="Mô hình dự báo trễ", marker_color=GREY,
                text=[f"{v:.1f}%" for v in g["predicted"] * 100], textposition="outside")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="% đơn")
    fig.update_xaxes(title="Bang khách hàng")
    return _style(fig, f"Tỷ lệ trễ theo bang (top {len(g)}, bang có từ {cfg.MIN_ORDERS_FOR_STATE_CHART} đơn)")


def fig_high_risk_over_time(df: pd.DataFrame) -> go.Figure | None:
    key = "year_month" if has_time(df) else "purchase_month"
    g = df[df["risk_level"] == cfg.RISK_HIGH].groupby(key).size().reset_index(name="n").sort_values(key)
    if g.empty:
        return None
    fig = go.Figure(go.Bar(x=g[key].astype(str), y=g["n"], marker_color=RED))
    fig.update_yaxes(title="Số đơn nguy cơ cao")
    fig.update_xaxes(title="Năm-tháng đặt hàng" if key == "year_month" else "Tháng đặt hàng (gộp mọi năm)")
    return _style(fig, "Số đơn nguy cơ cao theo thời gian")


def fig_late_rate_over_time(df: pd.DataFrame) -> go.Figure | None:
    """Tỷ lệ trễ thật và tỷ lệ dự báo trễ theo năm-tháng (cần có cột year_month)."""
    if not has_time(df):
        return None
    g = df.groupby("year_month").agg(
        n=("order_id", "size"), actual=("actual_late", "mean"), predicted=("predicted_late", "mean"),
    ).reset_index()
    g = g[g["n"] >= cfg.MIN_ORDERS_FOR_MONTH_CHART].sort_values("year_month")
    if g.empty:
        return None
    fig = go.Figure()
    fig.add_scatter(x=g["year_month"], y=g["actual"] * 100, name="Trễ thực tế", mode="lines+markers", line=dict(color=TEAL))
    fig.add_scatter(x=g["year_month"], y=g["predicted"] * 100, name="Mô hình dự báo trễ", mode="lines+markers", line=dict(color=GREY))
    fig.update_yaxes(title="% đơn")
    fig.update_xaxes(title="Năm-tháng đặt hàng")
    return _style(fig, "Tỷ lệ trễ theo thời gian (tháng có từ 30 đơn)")


def top_factor_counts(df_high: pd.DataFrame, medians: dict, top_n: int = 10, max_rows: int = 3000) -> pd.Series:
    """Đếm yếu tố rủi ro chính (top_risk_factor_1) của các đơn nguy cơ cao, dùng nhãn đã diễn giải."""
    if df_high.empty:
        return pd.Series(dtype=int)
    sub = df_high if len(df_high) <= max_rows else df_high.sample(max_rows, random_state=0)
    labels = []
    for _, row in sub.iterrows():
        f = describe_factor(row["top_risk_factor_1"], row, medians)
        if f is not None:
            labels.append(f.short)
    return pd.Series(labels, dtype="object").value_counts().head(top_n)


def fig_top_factors(df_high: pd.DataFrame, medians: dict) -> go.Figure | None:
    counts = top_factor_counts(df_high, medians)
    if counts.empty:
        return None
    counts = counts.iloc[::-1]  # để yếu tố phổ biến nhất nằm trên cùng
    fig = go.Figure(go.Bar(x=counts.values, y=counts.index, orientation="h", marker_color=RED))
    fig.update_xaxes(title="Số đơn (mẫu tối đa 3.000 đơn)")
    return _style(fig, "Yếu tố rủi ro chính của các đơn nguy cơ cao", height=380)
