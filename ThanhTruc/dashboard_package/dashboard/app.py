"""app.py - Dashboard cảnh báo rủi ro giao hàng trễ (Olist) - mục 3.5.

Chạy từ THƯ MỤC GỐC của repo:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import charts, config as cfg, factors, llm
from src.data import load_dashboard_data

st.set_page_config(page_title="Olist - Cảnh báo giao trễ", layout="wide")

# ---------------------------------------------------------------------------
# 1. Tải dữ liệu
# ---------------------------------------------------------------------------
try:
    df = load_dashboard_data()
except Exception as exc:
    st.error("Không tải được dữ liệu từ BigQuery. Hãy kiểm tra quyền truy cập và cấu hình Secrets.")
    with st.expander("Chi tiết lỗi"):
        st.code(f"{type(exc).__name__}: {str(exc)[:1500]}")
    st.stop()

medians = factors.compute_medians(df)

# ---------------------------------------------------------------------------
# 2. Bộ lọc (thanh bên)
# ---------------------------------------------------------------------------
st.sidebar.header("Bộ lọc")
risk_sel = st.sidebar.multiselect(
    "Mức rủi ro", cfg.RISK_ORDER, default=cfg.RISK_ORDER,
    format_func=lambda k: cfg.RISK_LABEL_VI[k],
)
state_sel = st.sidebar.multiselect(
    "Bang khách hàng", sorted(df["customer_state"].dropna().unique()), placeholder="Tất cả bang",
)
cat_sel = st.sidebar.multiselect(
    "Danh mục sản phẩm", sorted(df["product_category_name"].dropna().unique()),
    placeholder="Tất cả danh mục",
)
if charts.has_time(df):
    months = sorted(df["year_month"].dropna().unique())
    m_from, m_to = st.sidebar.select_slider(
        "Khoảng thời gian (năm-tháng)", options=months, value=(months[0], months[-1]),
    )
    month_sel = None
else:
    m_from = m_to = None
    month_sel = st.sidebar.multiselect(
        "Tháng đặt hàng", list(range(1, 13)), placeholder="Tất cả tháng",
    )
only_labeled = st.sidebar.checkbox("Chỉ tính đơn có nhãn thật", value=False,
                                   help="Bỏ các đơn chưa biết đã trễ hay chưa.")

mask = df["risk_level"].isin(risk_sel)
if state_sel:
    mask &= df["customer_state"].isin(state_sel)
if cat_sel:
    mask &= df["product_category_name"].isin(cat_sel)
if m_from is not None:
    mask &= df["year_month"].between(m_from, m_to)
elif month_sel:
    mask &= df["purchase_month"].isin(month_sel)
if only_labeled:
    mask &= df["actual_late"].notna()
df_f = df[mask]

# ---------------------------------------------------------------------------
# 3. Tiêu đề và lưu ý
# ---------------------------------------------------------------------------
st.title("Cảnh báo rủi ro giao hàng trễ - Olist")
st.caption(
    "Bản minh họa trên dữ liệu lịch sử Olist (2016-2018), không phải theo dõi đơn hàng thời gian thực."
)
with st.expander("Cách đọc kết quả (nên xem trước)"):
    st.markdown(
        "- **Xác suất trễ** do mô hình học máy (XGBoost) tính từ thông tin đơn hàng tại thời điểm đặt hàng.\n"
        "- Mô hình cố ý **cảnh báo rộng** để ít bỏ sót đơn trễ, nên tỷ lệ dự báo trễ cao hơn tỷ lệ trễ thực tế. "
        "Hãy coi danh sách cảnh báo là danh sách **cần rà soát**, không phải khẳng định đơn sẽ trễ.\n"
        "- Phần lớn đơn trong dữ liệu đã nằm trong tập mô hình học, nên không dùng các con số ở đây để đánh giá "
        "chất lượng mô hình (xem mục 3.4).\n"
        "- **Yếu tố rủi ro** (từ SHAP) cho biết điều gì làm tăng xác suất dự báo, không chứng minh quan hệ nhân quả."
    )

if df_f.empty:
    st.warning("Không có đơn hàng nào khớp bộ lọc hiện tại.")
    st.stop()

tab_overview, tab_detail = st.tabs(["Tổng quan vận hành", "Chi tiết đơn hàng"])


def _short_factor(row) -> str:
    f = factors.describe_factor(row["top_risk_factor_1"], row, medians)
    return f.short if f else "-"


# ---------------------------------------------------------------------------
# 4. Tab 1 - Tổng quan vận hành
# ---------------------------------------------------------------------------
with tab_overview:
    charts.render_kpis(charts.compute_kpis(df_f))

    left, right = st.columns(2)
    with left:
        fig = charts.fig_state_rates(df_f)
        if fig:
            st.plotly_chart(fig, key="chart_state")
        else:
            st.info("Chưa đủ dữ liệu để vẽ biểu đồ theo bang với bộ lọc này.")
    with right:
        fig = charts.fig_high_risk_over_time(df_f)
        if fig:
            st.plotly_chart(fig, key="chart_time")
        else:
            st.info("Không có đơn nguy cơ cao trong bộ lọc này.")

    left2, right2 = st.columns(2)
    with left2:
        st.plotly_chart(charts.fig_risk_distribution(df_f), key="chart_risk")
    with right2:
        fig = charts.fig_top_factors(df_f[df_f["risk_level"] == cfg.RISK_HIGH], medians)
        if fig:
            st.plotly_chart(fig, key="chart_factors")

    fig = charts.fig_late_rate_over_time(df_f)
    if fig:
        with st.expander("Tỷ lệ trễ theo năm-tháng (kiểm tra yếu tố 'tháng đặt hàng')"):
            st.plotly_chart(fig, key="chart_rate_time")

    st.subheader("Danh sách đơn hàng nguy cơ cao")
    high = df_f[df_f["risk_level"] == cfg.RISK_HIGH].sort_values("late_probability", ascending=False)
    top_high = high.head(cfg.MAX_ORDERS_IN_LIST).reset_index(drop=True)
    if top_high.empty:
        st.info("Không có đơn nguy cơ cao trong bộ lọc hiện tại.")
    else:
        table = pd.DataFrame({
            "Mã đơn": top_high["order_id"],
            "Xác suất trễ (%)": (top_high["late_probability"] * 100).round(1),
            "Bang khách hàng": top_high["customer_state"],
            "Bang người bán": top_high["seller_state"],
            "Khoảng cách (km)": top_high["distance_km"].round(0),
            "Yếu tố rủi ro chính": top_high.apply(_short_factor, axis=1),
        })
        st.caption(
            f"Hiển thị tối đa {cfg.MAX_ORDERS_IN_LIST} đơn có xác suất cao nhất "
            f"(trên tổng {len(high):,} đơn nguy cơ cao). Bấm vào một dòng rồi sang tab 'Chi tiết đơn hàng'."
        )
        try:
            event = st.dataframe(table, hide_index=True, on_select="rerun",
                                 selection_mode="single-row", key="high_risk_table")
            rows = event.selection.rows
            if rows:
                st.session_state["selected_order"] = top_high.loc[rows[0], "order_id"]
        except TypeError:  # phiên bản Streamlit cũ chưa hỗ trợ chọn dòng
            st.dataframe(table, hide_index=True)

# ---------------------------------------------------------------------------
# 5. Tab 2 - Chi tiết đơn hàng
# ---------------------------------------------------------------------------
with tab_detail:
    ranked = df_f.sort_values("late_probability", ascending=False).head(cfg.MAX_ORDERS_IN_LIST)
    options = ranked["order_id"].tolist()
    selected = st.session_state.get("selected_order")
    if selected and selected not in options and selected in set(df["order_id"]):
        options = [selected] + options
    index = options.index(selected) if selected in options else 0

    c_pick, c_search = st.columns(2)
    chosen = c_pick.selectbox("Chọn đơn hàng (xếp theo xác suất trễ giảm dần)", options, index=index)
    typed = c_search.text_input("Hoặc nhập mã đơn bất kỳ (order_id)").strip()
    if typed:
        if typed in set(df["order_id"]):
            chosen = typed
        else:
            c_search.warning("Không tìm thấy mã đơn này trong dữ liệu.")

    row = df.loc[df["order_id"] == chosen].iloc[0]
    order_factors = factors.describe_order(row, medians)

    st.subheader(f"Đơn hàng {chosen}")
    col_a, col_b = st.columns(2)

    with col_a:
        st.metric("Xác suất giao trễ (mô hình dự báo)", factors.fmt_pct(row["late_probability"]))
        color = cfg.RISK_COLORS.get(row["risk_level"], "#444")
        st.markdown(
            f"Mức rủi ro: <b style='color:{color}'>{cfg.RISK_LABEL_VI.get(row['risk_level'], row['risk_level'])}</b>",
            unsafe_allow_html=True,
        )
        st.write("Mô hình dự báo: " + ("**sẽ trễ**" if row["predicted_late"] == 1 else "**đúng hạn**"))
        if pd.isna(row["actual_late"]):
            st.write("Kết quả thực tế trong dữ liệu: **chưa có nhãn**")
        else:
            st.write("Kết quả thực tế trong dữ liệu: " + ("**đã trễ**" if row["actual_late"] == 1 else "**đúng hạn**"))
        st.markdown(
            f"- Bang khách hàng → bang người bán: **{row['customer_state']} → {row['seller_state']}**\n"
            f"- Khoảng cách: **{factors.fmt_number(row['distance_km'])} km**\n"
            f"- Số sản phẩm: **{factors.fmt_number(row['item_count'])}**, "
            f"tổng khối lượng: **{factors.fmt_number(row['total_product_weight_g'])} g**\n"
            f"- Giá trị đơn: **{factors.fmt_number(row['order_value'], 2)} BRL**, "
            f"phí vận chuyển: **{factors.fmt_number(row['freight_value'], 2)} BRL**"
        )

    with col_b:
        st.markdown("**Yếu tố làm tăng rủi ro (từ SHAP)**")
        if not order_factors:
            st.info("Mô hình không ghi nhận yếu tố nào làm tăng rủi ro của đơn này.")
        for i, f in enumerate(order_factors, 1):
            st.markdown(f"{i}. {f.text}")
            if f.caution:
                st.caption("Chỉ cho biết tháng đặt hàng; chưa đủ căn cứ để kết luận đó là mùa cao điểm.")

        st.markdown("**Đề xuất xử lý (Groq - Llama)**")
        rec_key = f"rec::{chosen}"
        if not llm.is_configured():
            st.info("Chưa cấu hình GROQ_API_KEY nên tính năng AI đang tắt.")
        elif not order_factors:
            st.caption("Không có yếu tố rủi ro để AI diễn giải.")
        else:
            if st.button("Tạo đề xuất xử lý", key=f"btn_{chosen}"):
                with st.spinner("Đang hỏi trợ lý AI..."):
                    st.session_state[rec_key] = llm.generate_recommendation(
                        chosen, float(row["late_probability"]), row["risk_level"], order_factors,
                    )
        result = st.session_state.get(rec_key)
        if result:
            text, err = result
            if err:
                st.error(err)
            else:
                st.write(text)
                st.caption("Đề xuất do AI tạo, cần đối chiếu thực tế trước khi áp dụng.")

    # --- Hỏi đáp về đúng đơn đang chọn -----------------------------------
    st.divider()
    st.subheader("Hỏi đáp về đơn hàng này")
    if not llm.is_configured():
        st.caption("Cần cấu hình GROQ_API_KEY để dùng.")
    else:
        history_all = st.session_state.setdefault("qa_history", {})
        history = history_all.setdefault(chosen, [])
        used = st.session_state.get("qa_count", 0)
        history_box = st.container()
        with st.form("qa_form", clear_on_submit=True):
            question = st.text_input("Câu hỏi", placeholder="Ví dụ: Vì sao đơn này có nguy cơ trễ?")
            submitted = st.form_submit_button("Gửi")
        if submitted and question.strip():
            if used >= cfg.MAX_QA_PER_SESSION:
                st.warning(f"Đã dùng hết {cfg.MAX_QA_PER_SESSION} câu hỏi của phiên này.")
            else:
                with st.spinner("Đang hỏi trợ lý AI..."):
                    answer, err = llm.answer_question(
                        llm.order_context(row, order_factors), history, question.strip(),
                    )
                st.session_state["qa_count"] = used + 1
                history.append({"role": "user", "content": question.strip()})
                history.append({"role": "assistant", "content": answer or err})
        with history_box:
            for m in history:
                st.chat_message(m["role"]).write(m["content"])
        st.caption(f"Đã dùng {st.session_state.get('qa_count', 0)}/{cfg.MAX_QA_PER_SESSION} câu hỏi trong phiên này.")
