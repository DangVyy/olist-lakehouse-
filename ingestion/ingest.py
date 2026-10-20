
import os
import csv
import re
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery


# =========================================================
# 1. XÁC ĐỊNH ĐƯỜNG DẪN PROJECT
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

print("FILE ĐANG CHẠY:", __file__)
print("THƯ MỤC PROJECT:", BASE_DIR)
print("THƯ MỤC DATA:", DATA_DIR)


# =========================================================
# 2. ĐỌC CẤU HÌNH GOOGLE CLOUD TỪ FILE .env
# =========================================================

ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "").strip()
LOCATION = os.getenv("BQ_LOCATION", "US").strip()

if not PROJECT_ID:
    raise ValueError(
        "Chưa cấu hình GCP_PROJECT_ID trong file .env"
    )

print("\nĐã đọc cấu hình Google Cloud!")
print("PROJECT ID:", PROJECT_ID)
print("LOCATION:", LOCATION)


# =========================================================
# 3. KẾT NỐI GOOGLE BIGQUERY
# =========================================================

print("\nĐang kết nối Google BigQuery...")

client = bigquery.Client(
    project=PROJECT_ID,
    location=LOCATION
)

print("Khởi tạo BigQuery Client thành công!")
print("PROJECT:", client.project)


# =========================================================
# 4. TẠO DATASET BRONZE
# =========================================================

BRONZE_DATASET = "olist_bronze"

DATASET_ID = f"{PROJECT_ID}.{BRONZE_DATASET}"

dataset = bigquery.Dataset(DATASET_ID)
dataset.location = LOCATION

client.create_dataset(
    dataset,
    exists_ok=True
)

# Kiểm tra dataset vừa tạo
created_dataset = client.get_dataset(DATASET_ID)

if created_dataset.location.upper() != LOCATION.upper():
    raise ValueError(
        "Location của dataset không khớp cấu hình!"
    )

print("\nTạo/Kiểm tra Bronze Layer thành công!")
print("DATASET:", DATASET_ID)
print("LOCATION:", created_dataset.location)


# =========================================================
# 5. MAPPING FILE CSV -> TABLE
# =========================================================

TABLE_MAPPING = {
    "olist_customers_dataset.csv": "customers",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "olist_order_payments_dataset.csv": "payments",
    "olist_order_reviews_dataset.csv": "reviews",
    "olist_geolocation_dataset.csv": "geolocation",
    "product_category_name_translation.csv": "category_translation",
}


# =========================================================
# 6. KIỂM TRA THƯ MỤC RAW
# =========================================================

if not DATA_DIR.exists():
    raise FileNotFoundError(
        f"Không tìm thấy thư mục data/raw: {DATA_DIR}"
    )

print("\nĐã tìm thấy thư mục data/raw!")


# =========================================================
# 7. INGEST 9 FILE CSV VÀO BIGQUERY BRONZE
# =========================================================

success_count = 0
failed_tables = []

for file_name, table_name in TABLE_MAPPING.items():

    file_path = DATA_DIR / file_name

    table_id = (
        f"{PROJECT_ID}.{BRONZE_DATASET}.{table_name}"
    )

    print("\n========================================")
    print("FILE:", file_name)
    print("TABLE:", table_id)

    if not file_path.exists():
        print("Không tìm thấy file:", file_path)
        failed_tables.append(table_name)
        continue

    try:
        # Đọc header của CSV và đếm số dòng nguồn
        with open(
            file_path,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as csv_file:

            reader = csv.reader(csv_file)
            columns = next(reader)

            # Kiểm tra tên cột tương thích BigQuery
            for col in columns:
                if not re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]*", col
                ):
                    raise ValueError(
                        f"Tên cột không hợp lệ: {col}"
                    )

            if len(set(columns)) != len(columns):
                raise ValueError(
                    "File CSV có tên cột bị trùng!"
                )

            source_rows = sum(
                1 for row in reader if row
            )

        # Giữ dữ liệu gốc ở dạng STRING
        schema = [
            bigquery.SchemaField(col, "STRING")
            for col in columns
        ]

        # Cấu hình nạp CSV vào BigQuery
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            schema=schema,
            source_column_match="POSITION",
            write_disposition="WRITE_TRUNCATE",
            allow_quoted_newlines=True,
            max_bad_records=0
        )

        print("ĐANG NẠP:", table_id)

        # Nạp trực tiếp dữ liệu CSV
        with open(file_path, "rb") as source_file:
            load_job = client.load_table_from_file(
                source_file,
                table_id,
                job_config=job_config,
                location=LOCATION
            )

        # Chờ hoàn thành
        load_job.result()

        # Kiểm tra bảng đã nạp
        table = client.get_table(table_id)

        row_count = table.num_rows
        column_count = len(table.schema)

        print("Số dòng CSV:", source_rows)
        print("Số dòng BigQuery:", row_count)
        print("Số cột:", column_count)

        if row_count != source_rows:
            raise ValueError(
                "Số dòng BigQuery không khớp dữ liệu nguồn!"
            )

        print(
            f"THÀNH CÔNG: {table_id} "
            f"({row_count:,} dòng)"
        )

        success_count += 1

    except Exception as e:
        print(f"LỖI khi nạp {table_name}: {e}")
        failed_tables.append(table_name)


# =========================================================
# 8. KIỂM TRA CÁC BẢNG TRONG BRONZE
# =========================================================

print("\n========================================")
print("KIỂM TRA BIGQUERY BRONZE")
print("========================================")

tables = list(client.list_tables(DATASET_ID))

if not tables:
    print("Không tìm thấy bảng nào trong Bronze")
else:
    for table in sorted(
        tables,
        key=lambda t: t.table_id
    ):
        print(
            f"- {BRONZE_DATASET}.{table.table_id}"
        )


# =========================================================
# 9. TỔNG HỢP KẾT QUẢ INGESTION
# =========================================================

print("\n========================================")
print("KẾT QUẢ INGESTION")
print("========================================")

print(
    f"Thành công: "
    f"{success_count}/{len(TABLE_MAPPING)} bảng"
)

if failed_tables:
    print(
        "Các bảng lỗi/chưa nạp:",
        ", ".join(failed_tables)
    )
else:
    print("Tất cả 9 bảng đã được nạp thành công!")

print("\nHoàn tất BigQuery Bronze Ingestion!")
