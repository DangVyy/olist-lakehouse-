# Dashboard cảnh báo rủi ro giao hàng trễ (mục 3.5)

Streamlit đọc bảng dự đoán của TV3 từ BigQuery, hiển thị KPI, biểu đồ, danh sách đơn nguy cơ cao,
và dùng Groq (Llama) để diễn giải yếu tố rủi ro thành đề xuất xử lý.

## Cấu trúc

```
.streamlit/            config.toml (giao diện), secrets.toml.example (mẫu), secrets.toml (khóa thật, KHÔNG commit)
dashboard/
  app.py               điểm vào: 2 tab (Tổng quan vận hành, Chi tiết đơn hàng)
  requirements.txt     thư viện riêng của Dashboard
  src/
    config.py          tên bảng, ngưỡng, tên model Groq (đổi ở một chỗ)
    data.py            kết nối BigQuery, JOIN bảng dự đoán với Wide Table, cache
    factors.py         diễn giải top_risk_factor thành tiếng Việt (xử lý biến one-hot)
    charts.py          tính KPI và dựng biểu đồ Plotly
    llm.py             gọi Groq: prompt, xử lý lỗi, model dự phòng, hỏi đáp
  notebooks/
    01_check_data.ipynb     kiểm tra dữ liệu thật trên BigQuery (chạy ĐẦU TIÊN)
    02_groq_models.ipynb    kiểm tra API key và model Groq
    03_dev_dashboard.ipynb  xem từng bước của app, chụp hình cho báo cáo
```

## Chạy lần đầu (PowerShell, đứng ở thư mục gốc repo, đã bật `.venv-1`)

1. Cài thư viện: `pip install -r dashboard/requirements.txt ipykernel`
2. Đăng nhập Google bằng tài khoản được cấp quyền BigQuery: `gcloud auth application-default login`
3. Mở và chạy lần lượt notebook `01`, `02`, `03` (chọn kernel `.venv-1`).
4. Tạo `.streamlit/secrets.toml` từ file `.example`, điền `GROQ_API_KEY`.
5. Chạy app: `streamlit run dashboard/app.py`

## Việc cần làm trước khi commit

Thêm vào `.gitignore` ở thư mục gốc:

```
.venv*/
.env
.streamlit/secrets.toml
service-account*.json
*-key*.json
```

Kiểm tra chưa có file nhạy cảm nào bị theo dõi: `git ls-files | Select-String -Pattern "\.env|secrets|venv|key"`

## Deploy (Streamlit Community Cloud)

1. Đẩy code lên GitHub (branch riêng, Pull Request vào `develop`, lead duyệt).
2. Trên Streamlit Cloud: chọn repo, branch, file chạy chính `dashboard/app.py`.
3. Mục **Secrets** (Settings), dán nội dung như `secrets.toml.example`, gồm `GROQ_API_KEY` và mục
   `[gcp_service_account]` (khóa JSON của Service Account **chỉ quyền đọc** do nhóm trưởng cấp).
4. Xem log cài thư viện để chắc app dùng đúng `dashboard/requirements.txt`.
5. Mở URL, kiểm tra: dữ liệu tải được, KPI, bảng cảnh báo, nút tạo đề xuất.

Service Account cần: BigQuery Data Viewer trên `olist_ml` và `olist_gold`, BigQuery Job User ở mức project.

## Lỗi thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `DefaultCredentialsError` | Chạy `gcloud auth application-default login` |
| `403 Access Denied` | Chưa được cấp quyền; nhờ nhóm trưởng thêm tài khoản |
| `Not found: Table ...` | Kiểm tra tên bảng trong `src/config.py` và notebook 01 |
| Không có biểu đồ theo năm-tháng | Chưa có quyền đọc `olist_gold.fct_orders`; app vẫn chạy, chỉ thiếu phần thời gian |
| Nút AI báo "Chưa cấu hình GROQ_API_KEY" | Điền key vào `.streamlit/secrets.toml` hoặc biến môi trường |
| Báo model Groq không tồn tại | Đổi `GROQ_MODEL` (xem notebook 02); app tự thử model dự phòng |
