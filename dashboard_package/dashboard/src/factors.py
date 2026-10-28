"""factors.py - Diễn giải yếu tố rủi ro (top_risk_factor) thành câu tiếng Việt dễ hiểu.

Vì sao cần file này?
  TV3 lưu top_risk_factor là TÊN ĐẶC TRƯNG sau mã hóa, ví dụ `distance_km`, `purchase_month`,
  `customer_state_SP`. Với biến one-hot như `customer_state_SP`, điểm SHAP dương có thể có nghĩa là
  khách hàng "KHÔNG ở SP" (biểu đồ SHAP beeswarm cho thấy khách ở SP làm GIẢM rủi ro).
  Vì vậy ta không dịch cứng, mà so với giá trị thật của đơn (lấy từ Wide Table) rồi mới diễn giải.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}

# tên đặc trưng -> (mô tả tiếng Việt, đơn vị, số chữ số thập phân)
NUMERIC_FEATURES = {
    "item_count": ("số sản phẩm trong đơn", "sản phẩm", 0),
    "order_value": ("giá trị đơn hàng", "BRL", 2),
    "freight_value": ("phí vận chuyển", "BRL", 2),
    "total_product_weight_g": ("tổng khối lượng hàng", "g", 0),
    "max_product_weight_g": ("khối lượng của sản phẩm nặng nhất", "g", 0),
    "max_product_length_cm": ("chiều dài lớn nhất của sản phẩm", "cm", 0),
    "max_product_height_cm": ("chiều cao lớn nhất của sản phẩm", "cm", 0),
    "max_product_width_cm": ("chiều rộng lớn nhất của sản phẩm", "cm", 0),
    "purchase_month": ("tháng đặt hàng", "", 0),
    "purchase_weekday": ("ngày trong tuần khi đặt hàng", "", 0),
    "seller_prep_days": ("thời gian người bán được phép chuẩn bị hàng", "ngày", 1),
    "distance_km": ("khoảng cách giữa người bán và khách hàng", "km", 0),
}

# tiền tố của biến one-hot -> (cột gốc trong Wide Table, danh từ chủ thể)
ONEHOT_PREFIXES = {
    "customer_state_": ("customer_state", "Khách hàng"),
    "seller_state_": ("seller_state", "Người bán"),
    "product_category_name_": ("product_category_name", "Sản phẩm"),
}

# BigQuery: DAYOFWEEK - 1, nên 0 = Chủ nhật (khớp ml_wide_table.sql của TV2)
WEEKDAYS = ["Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"]


@dataclass
class Factor:
    feature: str      # tên đặc trưng gốc từ bảng dự đoán
    text: str         # câu diễn giải đầy đủ (kèm giá trị thật của đơn)
    short: str        # nhãn ngắn, dùng cho biểu đồ và bảng
    kind: str         # numeric | state | category | unknown
    caution: bool = False  # True nếu không nên suy diễn thêm (ví dụ tháng đặt hàng)


# --- Định dạng số theo kiểu Việt Nam: 1.234,5 ---------------------------------
def fmt_number(x, decimals: int = 0) -> str:
    if x is None or pd.isna(x):
        return "không rõ"
    s = f"{float(x):,.{decimals}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_pct(x, decimals: int = 1) -> str:
    """x là tỷ lệ 0..1 -> '82,3%'."""
    if x is None or pd.isna(x):
        return "–"
    return fmt_number(float(x) * 100, decimals) + "%"


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def compute_medians(df: pd.DataFrame) -> dict:
    """Trung vị toàn bộ đơn của từng biến số, dùng để nói 'cao hơn / thấp hơn mức thường'."""
    return {c: float(df[c].median()) for c in NUMERIC_FEATURES if c in df.columns}


def _compare(value, median) -> str | None:
    if pd.isna(value) or median is None or pd.isna(median) or median <= 0:
        return None
    ratio = value / median
    if ratio >= 1.25:
        return "cao hơn mức trung vị"
    if ratio <= 0.8:
        return "thấp hơn mức trung vị"
    return "gần mức trung vị"


def is_known_feature(feature) -> bool:
    if feature is None or pd.isna(feature):
        return False
    return feature in NUMERIC_FEATURES or any(feature.startswith(p) for p in ONEHOT_PREFIXES)


def describe_factor(feature, row, medians: dict | None = None) -> Factor | None:
    """Biến một top_risk_factor thành câu tiếng Việt, dựa trên giá trị thật của đơn (row)."""
    if feature is None or pd.isna(feature):
        return None
    medians = medians or {}

    # 1) Biến one-hot: khách hàng / người bán ở bang nào, sản phẩm thuộc danh mục nào
    for prefix, (col, who) in ONEHOT_PREFIXES.items():
        if feature.startswith(prefix):
            code = feature[len(prefix):]
            actual = row.get(col)
            actual = None if actual is None or pd.isna(actual) else str(actual)
            same = actual == code
            if col == "product_category_name":
                if code == "unknown":
                    text = ("Đơn không xác định được danh mục sản phẩm" if same
                            else f"Đơn có danh mục sản phẩm xác định ({(actual or 'không rõ').replace('_', ' ')})")
                    return Factor(feature, text, _cap(text.split(" (")[0]), "category")
                pretty = code.replace("_", " ")
                if same:
                    text = f"Sản phẩm thuộc danh mục {pretty}"
                    short = text
                else:
                    now = (actual or "không rõ").replace("_", " ")
                    text = f"Sản phẩm không thuộc danh mục {pretty} (đơn thuộc danh mục {now})"
                    short = f"Sản phẩm không thuộc danh mục {pretty}"
                return Factor(feature, text, short, "category")
            name = STATE_NAMES.get(code, code)
            if same:
                text = f"{who} ở bang {code} ({name})"
                short = f"{who} ở bang {code}"
            else:
                where = f", hiện ở bang {actual}" if actual else ""
                text = f"{who} ở ngoài bang {code} ({name}){where}"
                short = f"{who} ở ngoài bang {code}"
            return Factor(feature, text, short, "state")

    # 2) Biến số
    if feature in NUMERIC_FEATURES:
        label, unit, decimals = NUMERIC_FEATURES[feature]
        value = row.get(feature)
        short = _cap(label)
        if value is None or pd.isna(value):
            return Factor(feature, f"{short}: không có dữ liệu", short, "numeric")
        if feature == "purchase_month":
            return Factor(feature, f"Đơn được đặt vào tháng {int(value)}", short, "numeric", caution=True)
        if feature == "purchase_weekday":
            day = WEEKDAYS[int(value) % 7]
            return Factor(feature, f"Đơn được đặt vào {day}", short, "numeric")
        text = f"{short}: {fmt_number(value, decimals)} {unit}".rstrip()
        comp = _compare(value, medians.get(feature))
        if comp:
            text += f" ({comp} {fmt_number(medians.get(feature), decimals)} {unit})".replace(" )", ")")
        return Factor(feature, text, short, "numeric")

    # 3) Tên lạ (phòng khi TV3 thêm đặc trưng mới)
    pretty = str(feature).replace("_", " ")
    return Factor(feature, pretty, _cap(pretty), "unknown")


def describe_order(row, medians: dict | None = None, max_factors: int = 2) -> list[Factor]:
    """Danh sách tối đa 2 yếu tố rủi ro (đã diễn giải) của một đơn hàng."""
    out = []
    for col in ("top_risk_factor_1", "top_risk_factor_2")[:max_factors]:
        f = describe_factor(row.get(col), row, medians)
        if f is not None:
            out.append(f)
    return out


def unknown_features(series: pd.Series) -> list[str]:
    """Các tên đặc trưng trong bảng dự đoán mà file này chưa biết cách diễn giải."""
    vals = series.dropna().unique()
    return sorted(v for v in vals if not is_known_feature(v))
