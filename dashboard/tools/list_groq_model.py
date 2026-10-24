"""
list_groq_models.py - Liệt kê model Groq đang dùng được với API key của bạn và thử gọi 1 lần.

Cài thư viện (một lần, trong .venv-1):   pip install groq
Chạy:                                    python dashboard/list_groq_models.py
Key được đọc từ biến môi trường GROQ_API_KEY; nếu chưa có, script hỏi và ẨN ký tự khi gõ.
Không ghi key vào file, không in key ra màn hình.
"""
import getpass
import os

from groq import Groq

key = os.environ.get("GROQ_API_KEY") or getpass.getpass("Dán GROQ_API_KEY (ẩn khi gõ): ").strip()
client = Groq(api_key=key)

ids = sorted(m.id for m in client.models.list().data)
print(f"\nCó {len(ids)} model. Các model liên quan Llama:")
for i in ids:
    if "llama" in i.lower():
        print("  -", i)

print("\nToàn bộ danh sách:")
for i in ids:
    print("  ", i)

# Thử gọi 1 lần với model dự kiến dùng
PREFERRED = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
model = next((m for m in PREFERRED if m in ids), None)
if model is None:
    print("\nKhông thấy model dự kiến trong danh sách, hãy chọn một model Llama ở trên.")
else:
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Trả lời đúng một từ: OK"}],
        max_tokens=10,
        temperature=0,
    )
    print(f"\nThử gọi model {model}: {r.choices[0].message.content!r}")