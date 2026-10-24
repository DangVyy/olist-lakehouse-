"""llm.py - Gọi Groq (Llama) để sinh đề xuất xử lý và trả lời câu hỏi về MỘT đơn hàng.

Nguyên tắc:
  * API key đọc từ Streamlit Secrets (GROQ_API_KEY) hoặc biến môi trường, KHÔNG viết trong code.
  * Chỉ đưa vào prompt các thông tin của đơn đang chọn; không đưa kết quả thực tế (đã trễ hay chưa).
  * Lỗi (thiếu key, hết lượt, mất mạng) được trả về dạng thông báo, không làm sập app.
  * Kết quả đề xuất được lưu tạm (cache) để cùng một đơn không gọi API lại.
"""
from __future__ import annotations

import os

import streamlit as st

from . import config as cfg
from .factors import Factor, fmt_pct

SYSTEM_PROMPT = (
    "Bạn là trợ lý hỗ trợ vận hành logistics cho sàn thương mại điện tử Olist (Brazil). "
    "Chỉ dựa vào thông tin được cung cấp trong yêu cầu; không bịa số liệu, không suy diễn nguyên nhân ngoài dữ liệu. "
    "Các yếu tố rủi ro cho biết điều gì làm tăng xác suất mô hình dự báo, không chứng minh quan hệ nhân quả. "
    "Trả lời bằng tiếng Việt, ngắn gọn, thực tế, dành cho nhân viên điều phối vận hành."
)

QA_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + " Bạn đang trả lời câu hỏi về MỘT đơn hàng duy nhất, chỉ dựa trên dữ liệu đơn hàng được cung cấp. "
    "Nếu câu hỏi cần thông tin không có trong dữ liệu đó, hãy nói rõ là không có dữ liệu thay vì đoán. "
    "Từ chối lịch sự các câu hỏi không liên quan đến đơn hàng này."
    + " Xác suất do mô hình tính chỉ dùng để xếp hạng đơn cần rà soát, không phải khả năng thật: trong nhóm nguy cơ cao chỉ khoảng một phần ba đơn thực sự trễ. Không nói chắc chắn đơn sẽ trễ."
)

CAUTION_NOTE = (
    "Lưu ý: yếu tố 'tháng đặt hàng' chỉ cho biết tháng; không được suy luận đó là mùa cao điểm hay sự kiện nào."
)


class MissingKeyError(RuntimeError):
    pass


def _get_key() -> str | None:
    try:
        if "GROQ_API_KEY" in st.secrets:
            return str(st.secrets["GROQ_API_KEY"]).strip() or None
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY", "").strip() or None


def _get_model() -> str:
    try:
        if "GROQ_MODEL" in st.secrets:
            return str(st.secrets["GROQ_MODEL"]).strip()
    except Exception:
        pass
    return cfg.GROQ_MODEL


def is_configured() -> bool:
    return _get_key() is not None


# --- Dựng prompt ------------------------------------------------------------
def build_user_prompt(order_id: str, probability: float, risk_level: str, factors: list[Factor]) -> str:
    lines = [
        "Thông tin đơn hàng:",
        f"- Mã đơn: {order_id}",
        f"- Xác suất giao trễ do mô hình dự báo: {fmt_pct(probability)}",
        f"- Mức rủi ro: {cfg.RISK_LABEL_VI.get(risk_level, risk_level)}",
        "- Các yếu tố làm tăng rủi ro (theo thứ tự quan trọng):",
    ]
    for i, f in enumerate(factors, 1):
        lines.append(f"  {i}. {f.text}")
    if any(f.caution for f in factors):
        lines.append(CAUTION_NOTE)
    lines += [
        "",
        "Yêu cầu:",
        "1. Giải thích 1-2 câu vì sao đơn này cần được chú ý.",
        "2. Đề xuất 1-3 hành động cụ thể cho bộ phận vận hành "
        "(ví dụ: nhắc người bán chuẩn bị hàng sớm, chủ động báo khách thời gian giao dự kiến, theo dõi tuyến vận chuyển).",
        "3. Không thêm dữ kiện không có ở trên.",
        "4. Trả lời bằng tiếng Việt, tối đa 120 từ.",
    ]
    return "\n".join(lines)


def order_context(row, factors: list[Factor]) -> str:
    """Dữ liệu của một đơn để làm ngữ cảnh cho phần hỏi đáp (không gồm kết quả thực tế)."""
    from .factors import NUMERIC_FEATURES, fmt_number

    parts = [
        f"Mã đơn: {row.get('order_id')}",
        f"Xác suất giao trễ (mô hình dự báo): {fmt_pct(row.get('late_probability'))}",
        f"Mức rủi ro: {cfg.RISK_LABEL_VI.get(row.get('risk_level'), row.get('risk_level'))}",
        f"Bang khách hàng: {row.get('customer_state')}; bang người bán: {row.get('seller_state')}",
        f"Danh mục sản phẩm: {row.get('product_category_name')}",
    ]
    for col in ("distance_km", "seller_prep_days", "item_count", "total_product_weight_g",
                "order_value", "freight_value"):
        label, unit, dec = NUMERIC_FEATURES[col]
        parts.append(f"{label}: {fmt_number(row.get(col), dec)} {unit}".rstrip())
    if factors:
        parts.append("Yếu tố làm tăng rủi ro: " + "; ".join(f.text for f in factors))
    return "\n".join(parts)


# --- Gọi Groq ---------------------------------------------------------------
def _client():
    key = _get_key()
    if not key:
        raise MissingKeyError("Chưa cấu hình GROQ_API_KEY")
    from groq import Groq

    return Groq(api_key=key)


@st.cache_data(ttl=cfg.GROQ_CACHE_TTL_SECONDS, show_spinner=False)
def _create(model: str, messages: list[dict]) -> str:
    resp = _client().chat.completions.create(
        model=model, messages=messages,
        temperature=cfg.GROQ_TEMPERATURE,
        max_completion_tokens=cfg.GROQ_MAX_TOKENS,
        reasoning_effort=cfg.GROQ_REASONING_EFFORT,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("Groq trả về nội dung rỗng")
    return text


@st.cache_data(ttl=cfg.GROQ_CACHE_TTL_SECONDS, show_spinner=False)
def _complete_cached(model: str, system: str, user: str) -> str:
    return _create(model, [{"role": "system", "content": system}, {"role": "user", "content": user}])


def _complete_messages(model: str, messages: list[dict]) -> str:
    return _create(model, messages)


def _friendly_error(exc: Exception) -> str:
    import groq

    if isinstance(exc, MissingKeyError):
        return "Chưa cấu hình GROQ_API_KEY nên chưa dùng được tính năng AI."
    if isinstance(exc, groq.AuthenticationError):
        return "GROQ_API_KEY không hợp lệ hoặc đã bị thu hồi."
    if isinstance(exc, groq.RateLimitError):
        return "Đã hết lượt gọi Groq tạm thời. Hãy thử lại sau ít phút."
    if isinstance(exc, groq.APIConnectionError):
        return "Không kết nối được tới Groq. Kiểm tra mạng rồi thử lại."
    if isinstance(exc, groq.APIStatusError):
        return f"Groq trả về lỗi (mã {exc.status_code}). Hãy thử lại sau."
    return f"Lỗi không xác định khi gọi AI ({type(exc).__name__})."


_DEAD_MODELS: set[str] = set()  # model đã báo "không tồn tại / ngừng hỗ trợ" trong lần chạy này


def _with_fallback(call):
    """Thử model chính; nếu model không còn tồn tại thì chuyển sang model dự phòng và nhớ model hỏng."""
    import groq

    models = [_get_model()]
    if cfg.GROQ_FALLBACK_MODEL not in models:
        models.append(cfg.GROQ_FALLBACK_MODEL)
    candidates = [m for m in models if m not in _DEAD_MODELS] or models
    last_exc: Exception | None = None
    for model in candidates:
        try:
            return call(model), None
        except (groq.NotFoundError, groq.BadRequestError) as exc:
            last_exc = exc
            if "model" in str(exc).lower():  # lỗi do model không dùng được -> bỏ qua ở các lần sau
                _DEAD_MODELS.add(model)
            continue
        except Exception as exc:
            return None, _friendly_error(exc)
    return None, _friendly_error(last_exc) if last_exc else "Không gọi được AI."


def generate_recommendation(order_id: str, probability: float, risk_level: str,
                            factors: list[Factor]) -> tuple[str | None, str | None]:
    """Trả về (nội dung đề xuất, thông báo lỗi). Đúng một trong hai khác None."""
    user = build_user_prompt(order_id, probability, risk_level, factors)
    return _with_fallback(lambda model: _complete_cached(model, SYSTEM_PROMPT, user))


def answer_question(context: str, history: list[dict], question: str) -> tuple[str | None, str | None]:
    """Trả lời câu hỏi về đơn đang chọn. history là danh sách {'role','content'} các lượt trước."""
    messages = [
        {"role": "system", "content": QA_SYSTEM_PROMPT},
        {"role": "user", "content": "Dữ liệu đơn hàng:\n" + context},
        {"role": "assistant", "content": "Đã nhận dữ liệu đơn hàng. Bạn muốn hỏi gì?"},
    ] + history[-6:] + [{"role": "user", "content": question}]
    return _with_fallback(lambda model: _complete_messages(model, messages))
