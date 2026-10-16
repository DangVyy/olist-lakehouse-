"""
=============================================================================
MACHINE LEARNING PIPELINE: LATE DELIVERY PREDICTION & EXPLAINABILITY
=============================================================================
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import (
    classification_report, roc_auc_score, average_precision_score,
    confusion_matrix, accuracy_score, precision_score, recall_score, f1_score,
    roc_curve, precision_recall_curve
)
import joblib
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# Ensure UTF-8 output in Windows console
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")

# Cấu hình đường dẫn lưu trữ mô hình và biểu đồ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLOTS_DIR = os.path.join(BASE_DIR, "plots")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

PROJECT_ID = "olist-lakehouse-511407"
SOURCE_TABLE = f"`{PROJECT_ID}.olist_ml.ml_wide_table`"
TARGET_TABLE_ML = f"{PROJECT_ID}.olist_ml.order_predictions"
TARGET_TABLE_GOLD = f"{PROJECT_ID}.olist_gold.order_predictions"

# Danh sách đặc trưng đầu vào theo lược đồ bảng phẳng đã phê duyệt
NUM_COLS = [
    "item_count", "order_value", "freight_value", "total_product_weight_g",
    "max_product_weight_g", "max_product_length_cm", "max_product_height_cm",
    "max_product_width_cm", "purchase_month", "purchase_weekday",
    "seller_prep_days", "distance_km"
]
CAT_COLS = ["customer_state", "seller_state", "product_category_name"]
TARGET_COL = "late_delivery"
ID_COL = "order_id"


def main():
    start_time = time.time()
    print("=" * 75)
    print("BẮT ĐẦU QUY TRÌNH HỌC MÁY — DỰ BÁO NGUY CƠ GIAO HÀNG TRỄ (TV3)")
    print("=" * 75)

    # -------------------------------------------------------------------------
    # 3.4.1. Môi trường tính toán: Kết nối Google BigQuery và nạp bảng phẳng
    # -------------------------------------------------------------------------
    print(f"\n[3.4.1] Đang kết nối kho dữ liệu BigQuery dự án '{PROJECT_ID}'...")
    client = bigquery.Client(project=PROJECT_ID)

    query = f"SELECT * FROM {SOURCE_TABLE}"
    print(f"Đang trích xuất dữ liệu từ bảng phẳng: {SOURCE_TABLE}...")
    df_all = client.query(query).to_dataframe()
    total_rows = len(df_all)
    print(f"-> Nạp dữ liệu thành công: {total_rows} dòng, {df_all.shape[1]} cột.")

    # Chuyển đổi định dạng số thực cho các cột giá trị tiền tệ
    for col in ["order_value", "freight_value"]:
        df_all[col] = df_all[col].astype(float)

    # Lọc và tạo bản sao độc lập cho tập dữ liệu đã có nhãn
    df_labeled = df_all[df_all[TARGET_COL].isin([0, 1])].copy()
    df_labeled[TARGET_COL] = df_labeled[TARGET_COL].astype(int)
    labeled_count = len(df_labeled)
    late_count = int(df_labeled[TARGET_COL].sum())
    ontime_count = labeled_count - late_count
    late_rate = late_count / labeled_count

    print(f"-> Đơn hàng đã có nhãn hoàn tất: {labeled_count} đơn.")
    print(f"   + Giao đúng hạn hoặc sớm (0): {ontime_count} đơn ({1 - late_rate:.2%})")
    print(f"   + Giao trễ hạn (1): {late_count} đơn ({late_rate:.2%})")
    print(f"-> Đơn hàng chưa xác định nhãn: {total_rows - labeled_count} đơn.")

    # -------------------------------------------------------------------------
    # 3.4.2. Huấn luyện thuật toán
    # -------------------------------------------------------------------------
    print("\n[3.4.2] Chuẩn bị dữ liệu và huấn luyện mô hình...")

    X = df_labeled[NUM_COLS + CAT_COLS]
    y = df_labeled[TARGET_COL]
    order_ids_labeled = df_labeled[ID_COL]

    # Train/Test Split (80/20 Stratified)
    X_train, X_test, y_train, y_test, id_train, id_test = train_test_split(
        X, y, order_ids_labeled, test_size=0.20, random_state=42, stratify=y
    )
    print(f"-> Phân chia Train/Test (80/20):")
    print(f"   + Tập huấn luyện (Train): {len(X_train)} dòng (Trễ: {y_train.sum()} — {y_train.mean():.2%})")
    print(f"   + Tập kiểm tra (Test):     {len(X_test)} dòng (Trễ: {y_test.sum()} — {y_test.mean():.2%})")

    # Pipeline Preprocessing (ColumnTransformer)
    num_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])
    cat_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_transformer, NUM_COLS),
            ("cat", cat_transformer, CAT_COLS)
        ]
    )

    print("-> Fit ColumnTransformer trên tập Train...")
    X_train_trans = preprocessor.fit_transform(X_train)
    X_test_trans = preprocessor.transform(X_test)

    cat_feature_names = preprocessor.named_transformers_["cat"]["onehot"].get_feature_names_out(CAT_COLS)
    all_feature_names = NUM_COLS + list(cat_feature_names)
    print(f"-> Tổng số đặc trưng sau mã hóa OneHot: {len(all_feature_names)}")

    # Lưu preprocessor
    joblib.dump(preprocessor, os.path.join(MODELS_DIR, "preprocessor.joblib"))

    # Huấn luyện Model 1: Random Forest
    print("\n-> Đang huấn luyện Mô hình 1: Random Forest Classifier (class_weight='balanced')...")
    rf_model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        class_weight="balanced",
        min_samples_split=10,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train_trans, y_train)

    # Huấn luyện Model 2: XGBoost
    scale_pos_weight = (len(y_train) - sum(y_train)) / sum(y_train)
    print(f"-> Đang huấn luyện Mô hình 2: XGBoost Classifier (scale_pos_weight={scale_pos_weight:.2f})...")
    xgb_model = XGBClassifier(
        n_estimators=250,
        max_depth=6,
        learning_rate=0.07,
        scale_pos_weight=scale_pos_weight,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        eval_metric="auc"
    )
    xgb_model.fit(X_train_trans, y_train)

    # Đánh giá hiệu năng chi tiết
    def compute_metrics(model, X_tr, y_tr, X_te, y_te, name):
        tr_prob = model.predict_proba(X_tr)[:, 1]
        te_prob = model.predict_proba(X_te)[:, 1]
        tr_pred = (tr_prob >= 0.5).astype(int)
        te_pred = (te_prob >= 0.5).astype(int)

        return {
            "Mô hình": name,
            "Train ROC-AUC": roc_auc_score(y_tr, tr_prob),
            "Test ROC-AUC": roc_auc_score(y_te, te_prob),
            "Train PR-AUC": average_precision_score(y_tr, tr_prob),
            "Test PR-AUC": average_precision_score(y_te, te_prob),
            "Test Accuracy": accuracy_score(y_te, te_pred),
            "Test Precision": precision_score(y_te, te_pred),
            "Test Recall": recall_score(y_te, te_pred),
            "Test F1-score": f1_score(y_te, te_pred)
        }, tr_pred, te_pred, tr_prob, te_prob

    rf_eval, rf_tr_pred, rf_te_pred, rf_tr_prob, rf_te_prob = compute_metrics(
        rf_model, X_train_trans, y_train, X_test_trans, y_test, "Random Forest"
    )
    xgb_eval, xgb_tr_pred, xgb_te_pred, xgb_tr_prob, xgb_te_prob = compute_metrics(
        xgb_model, X_train_trans, y_train, X_test_trans, y_test, "XGBoost"
    )

    metrics_df = pd.DataFrame([rf_eval, xgb_eval])
    print("\n" + "=" * 75)
    print("BẢNG TỔNG HỢP HIỆU NĂNG CÁC MÔ HÌNH HỌC MÁY:")
    print("=" * 75)
    print(metrics_df.round(4).to_string(index=False))

    # Lưu mô hình đã huấn luyện
    joblib.dump(rf_model, os.path.join(MODELS_DIR, "random_forest_model.joblib"))
    joblib.dump(xgb_model, os.path.join(MODELS_DIR, "xgboost_model.joblib"))
    xgb_model.save_model(os.path.join(MODELS_DIR, "xgboost_model.json"))

    # Vẽ và lưu biểu đồ đánh giá
    print("\n-> Xuất các biểu đồ trực quan hóa đánh giá...")

    # 1. Confusion Matrix - RF
    plt.figure(figsize=(6, 5))
    cm_rf = confusion_matrix(y_test, rf_te_pred)
    sns.heatmap(cm_rf, annot=True, fmt="d", cmap="Blues", cbar=False,
                xticklabels=["Đúng hạn (0)", "Giao trễ (1)"], yticklabels=["Đúng hạn (0)", "Giao trễ (1)"])
    plt.title("Ma trận nhầm lẫn — Random Forest (Tập Test)")
    plt.xlabel("Nhãn dự đoán")
    plt.ylabel("Nhãn thực tế")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "01_confusion_matrix_rf.png"), dpi=300)
    plt.close()

    # 2. Confusion Matrix - XGBoost
    plt.figure(figsize=(6, 5))
    cm_xgb = confusion_matrix(y_test, xgb_te_pred)
    sns.heatmap(cm_xgb, annot=True, fmt="d", cmap="Greens", cbar=False,
                xticklabels=["Đúng hạn (0)", "Giao trễ (1)"], yticklabels=["Đúng hạn (0)", "Giao trễ (1)"])
    plt.title("Ma trận nhầm lẫn — XGBoost (Tập Test)")
    plt.xlabel("Nhãn dự đoán")
    plt.ylabel("Nhãn thực tế")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "02_confusion_matrix_xgb.png"), dpi=300)
    plt.close()

    # 3. ROC & PR Curves
    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    fpr_rf, tpr_rf, _ = roc_curve(y_test, rf_te_prob)
    fpr_xgb, tpr_xgb, _ = roc_curve(y_test, xgb_te_prob)
    plt.plot(fpr_rf, tpr_rf, label=f"Random Forest (AUC = {rf_eval['Test ROC-AUC']:.3f})", color="#1f77b4")
    plt.plot(fpr_xgb, tpr_xgb, label=f"XGBoost (AUC = {xgb_eval['Test ROC-AUC']:.3f})", color="#2ca02c", linewidth=2)
    plt.plot([0, 1], [0, 1], "k--", alpha=0.5)
    plt.xlabel("Tỷ lệ dương tính giả (FPR)")
    plt.ylabel("Tỷ lệ dương tính thật (TPR)")
    plt.title("Đường cong ROC")
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.subplot(1, 2, 2)
    prec_rf, rec_rf, _ = precision_recall_curve(y_test, rf_te_prob)
    prec_xgb, rec_xgb, _ = precision_recall_curve(y_test, xgb_te_prob)
    plt.plot(rec_rf, prec_rf, label=f"Random Forest (PR-AUC = {rf_eval['Test PR-AUC']:.3f})", color="#1f77b4")
    plt.plot(rec_xgb, prec_xgb, label=f"XGBoost (PR-AUC = {xgb_eval['Test PR-AUC']:.3f})", color="#2ca02c", linewidth=2)
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Đường cong Precision-Recall")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "03_roc_pr_curves.png"), dpi=300)
    plt.close()

    # 4. Feature Importance - Random Forest
    rf_imp = pd.Series(rf_model.feature_importances_, index=all_feature_names).sort_values(ascending=False).head(20)
    plt.figure(figsize=(10, 6))
    rf_imp.plot(kind="barh", color="#1f77b4").invert_yaxis()
    plt.title("Top 20 Đặc trưng quan trọng nhất — Random Forest")
    plt.xlabel("Mức độ quan trọng")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "04_feature_importance_rf.png"), dpi=300)
    plt.close()

    # 5. Feature Importance - XGBoost
    xgb_imp = pd.Series(xgb_model.feature_importances_, index=all_feature_names).sort_values(ascending=False).head(20)
    plt.figure(figsize=(10, 6))
    xgb_imp.plot(kind="barh", color="#2ca02c").invert_yaxis()
    plt.title("Top 20 Đặc trưng quan trọng nhất — XGBoost (Gain)")
    plt.xlabel("Độ tăng lợi ích (Gain)")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "05_feature_importance_xgb.png"), dpi=300)
    plt.close()

    # -------------------------------------------------------------------------
    # 3.4.3. Giải thích mô hình (SHAP)
    # -------------------------------------------------------------------------
    print("\n[3.4.3] Khởi tạo SHAP TreeExplainer và phân tích tác động đặc trưng...")
    explainer = shap.TreeExplainer(xgb_model)

    # Chạy SHAP trên mẫu 5.000 dòng test để vẽ đồ thị đại diện
    shap_sample_size = min(5000, len(X_test_trans))
    X_test_sample = X_test_trans[:shap_sample_size]
    shap_values_sample = explainer.shap_values(X_test_sample)

    # 6. SHAP Beeswarm Summary Plot
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values_sample, X_test_sample, feature_names=all_feature_names, show=False, max_display=15)
    plt.title("Biểu đồ SHAP Summary Plot (Beeswarm) — XGBoost", fontsize=13)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "06_shap_summary_beeswarm.png"), dpi=300)
    plt.close()

    # 7. SHAP Bar Plot
    plt.figure(figsize=(10, 6))
    shap.summary_plot(shap_values_sample, X_test_sample, feature_names=all_feature_names, plot_type="bar", show=False, max_display=15)
    plt.title("Biểu đồ mức độ đóng góp tuyệt đối của đặc trưng qua SHAP", fontsize=13)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, "07_shap_summary_bar.png"), dpi=300)
    plt.close()

    # -------------------------------------------------------------------------
    # 3.4.4. Cập nhật kết quả dự báo ngược lại kho dữ liệu (Write-back)
    # Cấu trúc chuẩn 7 cột theo đúng phân công trong CHƯƠNG 3.docx:
    # order_id, prediction_date, late_probability, predicted_late, risk_level,
    # top_risk_factor_1, top_risk_factor_2
    # -------------------------------------------------------------------------
    print("\n[3.4.4] Tạo bảng kết quả dự báo order_predictions và đẩy lên BigQuery...")

    # Transform toàn bộ 99.441 đơn hàng
    X_full = df_all[NUM_COLS + CAT_COLS]
    X_full_trans = preprocessor.transform(X_full)

    # Dự báo xác suất
    full_probs = xgb_model.predict_proba(X_full_trans)[:, 1]

    # Tính SHAP cho toàn bộ dữ liệu
    print("-> Đang tính toán SHAP values cho toàn bộ 99.441 đơn hàng...")
    t_shap = time.time()
    full_shap_vals = explainer.shap_values(X_full_trans)
    print(f"-> Hoàn tất tính SHAP sau {time.time() - t_shap:.2f}s.")

    # Trích xuất đúng Top 2 tác nhân rủi ro hàng đầu theo đúng CHƯƠNG 3
    print("-> Đang trích xuất top_risk_factor_1 và top_risk_factor_2...")
    top_factor_1_list = []
    top_factor_2_list = []

    for i in range(len(df_all)):
        sv = full_shap_vals[i]
        top_idx = np.argsort(sv)[::-1][:2]
        f_list = [all_feature_names[idx] for idx in top_idx]
        top_factor_1_list.append(f_list[0])
        top_factor_2_list.append(f_list[1])

    # Gán Risk Level theo ngưỡng xác suất chuẩn
    def assign_risk_level(p):
        if p >= 0.65:
            return "High Risk"
        elif p >= 0.35:
            return "Medium Risk"
        else:
            return "Low Risk"

    risk_levels = [assign_risk_level(p) for p in full_probs]
    predicted_late = (full_probs >= 0.5).astype(int)

    predictions_df = pd.DataFrame({
        "order_id": df_all[ID_COL].values,
        "late_probability": np.round(full_probs, 4),
        "predicted_late": predicted_late,
        "risk_level": risk_levels,
        "top_risk_factor_1": top_factor_1_list,
        "top_risk_factor_2": top_factor_2_list
    })

    print(f"-> Bảng kết quả dự báo có {len(predictions_df)} dòng (đúng 6 cột theo CHƯƠNG 3):")
    print(predictions_df.head())
    print(predictions_df["risk_level"].value_counts())

    # Ghi dữ liệu vào BigQuery dataset olist_ml và olist_gold
    print(f"\n-> Đang xuất bảng kết quả vào BigQuery: {TARGET_TABLE_ML}...")
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job_ml = client.load_table_from_dataframe(predictions_df, TARGET_TABLE_ML, job_config=job_config)
    job_ml.result()
    print(f"-> Ghi thành công vào {TARGET_TABLE_ML}!")

    print(f"-> Đang đồng bộ hóa sang tầng Gold: {TARGET_TABLE_GOLD}...")
    job_gold = client.load_table_from_dataframe(predictions_df, TARGET_TABLE_GOLD, job_config=job_config)
    job_gold.result()
    print(f"-> Ghi thành công vào {TARGET_TABLE_GOLD}!")

    # Mẫu 5 dòng đầu
    print("\n--- MẪU 5 DÒNG ĐẦU BẢNG KẾT QUẢ DỰ BÁO ---")
    print(predictions_df.head(5).to_string())

    total_duration = time.time() - start_time
    print(f"\n{'=' * 75}")
    print(f"HOÀN TẤT TOÀN BỘ PIPELINE ML CỦA THÀNH VIÊN 3 TRONG {total_duration:.2f} GIÂY!")
    print(f"{'=' * 75}")

if __name__ == "__main__":
    main()
