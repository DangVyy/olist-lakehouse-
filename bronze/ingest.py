import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv


# =========================================================
# 1. XÁC ĐỊNH ĐƯỜNG DẪN PROJECT
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

print("FILE ĐANG CHẠY:", __file__)
print("THƯ MỤC PROJECT:", BASE_DIR)
print("THƯ MỤC DATA:", DATA_DIR)


# =========================================================
# 2. ĐỌC TOKEN TỪ FILE .env
# =========================================================

ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

token = os.getenv("MOTHERDUCK_TOKEN")

if not token:
    raise ValueError(
        "Không tìm thấy MOTHERDUCK_TOKEN trong file .env"
    )

print("Đã đọc MOTHERDUCK_TOKEN thành công")


# =========================================================
# 3. KẾT NỐI MOTHERDUCK
# =========================================================

DATABASE_NAME = "olist_lakehouse"

print("\nĐang kết nối MotherDuck...")
print("DATABASE:", DATABASE_NAME)

con = duckdb.connect(
    f"md:{DATABASE_NAME}?motherduck_token={token}"
)

print("Kết nối MotherDuck thành công!")


# =========================================================
# 4. TẠO SCHEMA BRONZE
# =========================================================

con.execute("""
    CREATE SCHEMA IF NOT EXISTS bronze
""")

# Đặt bronze làm schema hiện tại
con.execute("""
    SET schema = 'bronze'
""")

current_schema = con.execute(
    "SELECT current_schema()"
).fetchone()[0]

print("SCHEMA HIỆN TẠI:", current_schema)


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


# =========================================================
# 7. INGEST 9 FILE CSV VÀO BRONZE
# =========================================================

success_count = 0
failed_tables = []

for file_name, table_name in TABLE_MAPPING.items():

    file_path = DATA_DIR / file_name

    print("\n========================================")
    print("FILE:", file_name)
    print("TABLE:", f"bronze.{table_name}")

    if not file_path.exists():

        print("Không tìm thấy file:", file_path)

        failed_tables.append(table_name)

        continue

    try:

        csv_path = file_path.as_posix()

        print(f"ĐANG TẠO: bronze.{table_name}")

        con.execute(
            f"""
            CREATE OR REPLACE TABLE bronze.{table_name} AS
            SELECT *
            FROM read_csv_auto(
                '{csv_path}',
                HEADER = TRUE
            )
            """
        )

        row_count = con.execute(
            f"""
            SELECT COUNT(*)
            FROM bronze.{table_name}
            """
        ).fetchone()[0]

        print(
            f"THÀNH CÔNG: bronze.{table_name} "
            f"({row_count:,} dòng)"
        )

        success_count += 1

    except Exception as e:

        print(
            f"LỖI khi tạo bronze.{table_name}: {e}"
        )

        failed_tables.append(table_name)


# =========================================================
# 8. KIỂM TRA CÁC BẢNG TRONG BRONZE
# =========================================================

print("\n========================================")
print("KIỂM TRA SCHEMA BRONZE")
print("========================================")

tables = con.execute(
    """
    SELECT
        table_schema,
        table_name
    FROM information_schema.tables
    WHERE table_schema = 'bronze'
    ORDER BY table_name
    """
).fetchall()

if not tables:

    print("Không tìm thấy bảng nào trong bronze")

else:

    for schema_name, table_name in tables:
        print(f"- {schema_name}.{table_name}")


# =========================================================
# 9. KIỂM TRA CÁC BẢNG TRONG MAIN
# =========================================================

print("\n========================================")
print("KIỂM TRA SCHEMA MAIN")
print("========================================")

main_tables = con.execute(
    """
    SELECT
        table_schema,
        table_name
    FROM information_schema.tables
    WHERE table_schema = 'main'
    ORDER BY table_name
    """
).fetchall()

if not main_tables:

    print("Schema main không có bảng dữ liệu")

else:

    print("Các bảng hiện đang có trong main:")

    for schema_name, table_name in main_tables:
        print(f"- {schema_name}.{table_name}")


# =========================================================
# 10. KẾT QUẢ CUỐI
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


# =========================================================
# 11. ĐÓNG KẾT NỐI
# =========================================================

con.close()

print("\nĐã đóng kết nối MotherDuck.")
print("Hoàn tất ingestion!")
