"""config.py - Cấu hình tập trung của Dashboard (đổi ở một chỗ, cả app tự cập nhật)."""
import os

# --- BigQuery -------------------------------------------------------------
PROJECT_ID = "olist-lakehouse-511407"
DATASET_ML = "olist_ml"      # bảng dự đoán (TV3) và Wide Table (TV2)
DATASET_GOLD = "olist_gold"  # fct_orders: lấy năm-tháng đặt hàng và trạng thái đơn

PRED_TABLE = f"{PROJECT_ID}.{DATASET_ML}.order_predictions"
WIDE_TABLE = f"{PROJECT_ID}.{DATASET_ML}.ml_wide_table"
ORDERS_TABLE = f"{PROJECT_ID}.{DATASET_GOLD}.fct_orders"

CACHE_TTL_SECONDS = 3600  # dữ liệu được lưu tạm 1 giờ, không truy vấn BigQuery mỗi lần đổi bộ lọc

# --- Mức rủi ro (khớp với train_model.py của TV3) --------------------------
RISK_HIGH = "High Risk"
RISK_MEDIUM = "Medium Risk"
RISK_LOW = "Low Risk"
RISK_ORDER = [RISK_HIGH, RISK_MEDIUM, RISK_LOW]
RISK_LABEL_VI = {RISK_HIGH: "Cao", RISK_MEDIUM: "Trung bình", RISK_LOW: "Thấp"}
RISK_COLORS = {RISK_HIGH: "#8F1D14", RISK_MEDIUM: "#B7791F", RISK_LOW: "#0F766E"}

THRESHOLD_HIGH = 0.65     # late_probability >= 0.65  -> High Risk
THRESHOLD_MEDIUM = 0.35   # 0.35 <= p < 0.65          -> Medium Risk
THRESHOLD_PREDICT = 0.50  # p >= 0.5 -> predicted_late = 1

# --- Hiển thị -------------------------------------------------------------
MAX_ORDERS_IN_LIST = 500          # số đơn tối đa trong bảng cảnh báo / ô chọn đơn
MIN_ORDERS_FOR_STATE_CHART = 200  # bang có ít đơn hơn mức này không đưa vào biểu đồ (tránh số nhiễu)
MIN_ORDERS_FOR_MONTH_CHART = 30

# --- Groq / Llama ---------------------------------------------------------
# Tên model có thể đổi bằng biến môi trường hoặc Secrets mà không cần sửa code.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
GROQ_MAX_TOKENS = 1500
GROQ_REASONING_EFFORT = "low"
GROQ_TEMPERATURE = 0.2
GROQ_CACHE_TTL_SECONDS = 24 * 3600
MAX_QA_PER_SESSION = 8  # giới hạn số câu hỏi đáp mỗi phiên để không cạn lượt gọi API miễn phí
