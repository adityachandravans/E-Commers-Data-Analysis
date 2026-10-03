"""
Olist E-Commerce Data Pipeline & Analysis (Master End-to-End Pipeline)
-----------------------------------------------------------------------
Phase 1: Ingestion & Data Cleaning (data/raw -> data/clean)
Phase 2: Relational Database Loading & Integrity Auditing (data/clean -> db/olist.db)
Phase 3: Exploratory Data Analysis & Visualizations (db/olist.db -> eda_charts/)
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Styling for charts
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.sans-serif': 'Arial', 'font.family': 'sans-serif'})

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
CLEAN_DIR = os.path.join(BASE_DIR, "data", "clean")
DB_PATH = os.path.join(BASE_DIR, "db", "olist.db")
EDA_CHARTS_DIR = os.path.join(BASE_DIR, "eda_charts")

os.makedirs(CLEAN_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(EDA_CHARTS_DIR, exist_ok=True)


def log(msg):
    print(f"[INFO] {msg}", flush=True)


# ==========================================
# PHASE 1: INGESTION & CLEANING
# ==========================================
def run_phase1_ingestion_cleaning():
    log("==========================================")
    log("STARTING PHASE 1: INGESTION & CLEANING")
    log("==========================================")

    log(f"Loading raw CSV files from '{RAW_DIR}'...")
    df_customers = pd.read_csv(os.path.join(RAW_DIR, "olist_customers_dataset.csv"), dtype={"customer_zip_code_prefix": str})
    df_customers["customer_zip_code_prefix"] = df_customers["customer_zip_code_prefix"].str.zfill(5)

    df_sellers = pd.read_csv(os.path.join(RAW_DIR, "olist_sellers_dataset.csv"), dtype={"seller_zip_code_prefix": str})
    df_sellers["seller_zip_code_prefix"] = df_sellers["seller_zip_code_prefix"].str.zfill(5)

    df_geo = pd.read_csv(os.path.join(RAW_DIR, "olist_geolocation_dataset.csv"), dtype={"geolocation_zip_code_prefix": str})
    df_geo["geolocation_zip_code_prefix"] = df_geo["geolocation_zip_code_prefix"].str.zfill(5)

    df_orders = pd.read_csv(os.path.join(RAW_DIR, "olist_orders_dataset.csv"))
    for col in ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        df_orders[col] = pd.to_datetime(df_orders[col], errors="coerce")

    df_items = pd.read_csv(os.path.join(RAW_DIR, "olist_order_items_dataset.csv"))
    df_items["shipping_limit_date"] = pd.to_datetime(df_items["shipping_limit_date"], errors="coerce")

    df_payments = pd.read_csv(os.path.join(RAW_DIR, "olist_order_payments_dataset.csv"))

    df_reviews = pd.read_csv(os.path.join(RAW_DIR, "olist_order_reviews_dataset.csv"))
    for col in ["review_creation_date", "review_answer_timestamp"]:
        df_reviews[col] = pd.to_datetime(df_reviews[col], errors="coerce")

    df_translation = pd.read_csv(os.path.join(RAW_DIR, "product_category_name_translation.csv"))

    df_products = pd.read_csv(os.path.join(RAW_DIR, "olist_products_dataset.csv"))
    df_products = df_products.merge(df_translation, on="product_category_name", how="left")
    df_products["has_missing_category"] = df_products["product_category_name"].isnull()
    df_products["has_missing_dimensions"] = (
        df_products["product_weight_g"].isnull() |
        df_products["product_length_cm"].isnull() |
        df_products["product_height_cm"].isnull() |
        df_products["product_width_cm"].isnull()
    )
    df_products["product_category_name_english_clean"] = df_products["product_category_name_english"].fillna("unknown")

    # Deduplicate order reviews by review_id
    df_reviews = df_reviews.sort_values("review_answer_timestamp").groupby("review_id").last().reset_index()

    # Aggregations for denormalization
    payment_agg = df_payments.groupby("order_id").agg(
        total_payment_value=("payment_value", "sum"),
        max_payment_installments=("payment_installments", "max"),
        primary_payment_type=("payment_type", lambda x: x.mode()[0] if not x.empty else "not_defined"),
        payment_types_list=("payment_type", lambda x: ", ".join(sorted(x.unique())))
    ).reset_index()

    reviews_order_agg = df_reviews.sort_values("review_answer_timestamp").groupby("order_id").last().reset_index()

    # Denormalized analysis tables
    df_analysis_orders = df_orders.merge(df_customers, on="customer_id", how="left")
    df_analysis_orders = df_analysis_orders.merge(payment_agg, on="order_id", how="left")
    df_analysis_orders = df_analysis_orders.merge(reviews_order_agg[["order_id", "review_id", "review_score", "review_comment_title", "review_comment_message", "review_answer_timestamp"]], on="order_id", how="left")

    df_analysis_items = df_items.merge(df_orders, on="order_id", how="left")
    df_analysis_items = df_analysis_items.merge(df_customers, on="customer_id", how="left")
    df_analysis_items = df_analysis_items.merge(df_products, on="product_id", how="left")
    df_analysis_items = df_analysis_items.merge(df_sellers, on="seller_id", how="left")
    df_analysis_items = df_analysis_items.merge(reviews_order_agg[["order_id", "review_score"]], on="order_id", how="left")
    df_analysis_items = df_analysis_items.merge(payment_agg[["order_id", "total_payment_value"]], on="order_id", how="left")

    tables = {
        "olist_customers": df_customers,
        "olist_sellers": df_sellers,
        "olist_geolocation": df_geo,
        "olist_orders": df_orders,
        "olist_order_items": df_items,
        "olist_order_payments": df_payments,
        "olist_order_reviews": df_reviews,
        "olist_products": df_products,
        "product_category_name_translation": df_translation,
        "olist_analysis_orders": df_analysis_orders,
        "olist_analysis_items": df_analysis_items
    }

    log(f"Exporting cleaned tables to '{CLEAN_DIR}'...")
    for name, df in tables.items():
        parquet_path = os.path.join(CLEAN_DIR, f"{name}.parquet")
        csv_path = os.path.join(CLEAN_DIR, f"{name}.csv")
        try:
            df.to_parquet(parquet_path, index=False)
        except Exception:
            pass
        df.to_csv(csv_path, index=False)

    log("Phase 1 Complete.")
    return tables


# ==========================================
# PHASE 2: DATABASE LOADING
# ==========================================
def run_phase2_database_loading(tables=None):
    log("==========================================")
    log("STARTING PHASE 2: DATABASE LOADING (SQLite)")
    log("==========================================")

    if tables is None:
        clean_tables = {
            "customers": pd.read_csv(os.path.join(CLEAN_DIR, "olist_customers.csv"), dtype={"customer_zip_code_prefix": str}),
            "sellers": pd.read_csv(os.path.join(CLEAN_DIR, "olist_sellers.csv"), dtype={"seller_zip_code_prefix": str}),
            "products": pd.read_csv(os.path.join(CLEAN_DIR, "olist_products.csv")),
            "orders": pd.read_csv(os.path.join(CLEAN_DIR, "olist_orders.csv")),
            "order_items": pd.read_csv(os.path.join(CLEAN_DIR, "olist_order_items.csv")),
            "order_payments": pd.read_csv(os.path.join(CLEAN_DIR, "olist_order_payments.csv")),
            "order_reviews": pd.read_csv(os.path.join(CLEAN_DIR, "olist_order_reviews.csv")),
            "geolocation": pd.read_csv(os.path.join(CLEAN_DIR, "olist_geolocation.csv"), dtype={"geolocation_zip_code_prefix": str}),
            "category_translation": pd.read_csv(os.path.join(CLEAN_DIR, "product_category_name_translation.csv"))
        }
    else:
        clean_tables = {
            "customers": tables["olist_customers"],
            "sellers": tables["olist_sellers"],
            "products": tables["olist_products"],
            "orders": tables["olist_orders"],
            "order_items": tables["olist_order_items"],
            "order_payments": tables["olist_order_payments"],
            "order_reviews": tables["olist_order_reviews"],
            "geolocation": tables["olist_geolocation"],
            "category_translation": tables["product_category_name_translation"]
        }

    missing_cats = set(clean_tables["products"]["product_category_name"].dropna()) - set(clean_tables["category_translation"]["product_category_name"])
    if missing_cats:
        new_rows = [{"product_category_name": cat, "product_category_name_english": cat.replace("_", " ")} for cat in missing_cats]
        clean_tables["category_translation"] = pd.concat([clean_tables["category_translation"], pd.DataFrame(new_rows)], ignore_index=True)

    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    ddl_statements = [
        "CREATE TABLE customers (customer_id TEXT PRIMARY KEY, customer_unique_id TEXT NOT NULL, customer_zip_code_prefix TEXT, customer_city TEXT, customer_state TEXT);",
        "CREATE TABLE sellers (seller_id TEXT PRIMARY KEY, seller_zip_code_prefix TEXT, seller_city TEXT, seller_state TEXT);",
        "CREATE TABLE category_translation (product_category_name TEXT PRIMARY KEY, product_category_name_english TEXT);",
        "CREATE TABLE products (product_id TEXT PRIMARY KEY, product_category_name TEXT, product_name_lenght REAL, product_description_lenght REAL, product_photos_qty REAL, product_weight_g REAL, product_length_cm REAL, product_height_cm REAL, product_width_cm REAL, product_category_name_english TEXT, has_missing_category INTEGER, has_missing_dimensions INTEGER, product_category_name_english_clean TEXT, FOREIGN KEY (product_category_name) REFERENCES category_translation (product_category_name));",
        "CREATE TABLE orders (order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, order_status TEXT, order_purchase_timestamp TEXT, order_approved_at TEXT, order_delivered_carrier_date TEXT, order_delivered_customer_date TEXT, order_estimated_delivery_date TEXT, FOREIGN KEY (customer_id) REFERENCES customers (customer_id));",
        "CREATE TABLE order_items (order_id TEXT NOT NULL, order_item_id INTEGER NOT NULL, product_id TEXT NOT NULL, seller_id TEXT NOT NULL, shipping_limit_date TEXT, price REAL, freight_value REAL, PRIMARY KEY (order_id, order_item_id), FOREIGN KEY (order_id) REFERENCES orders (order_id), FOREIGN KEY (product_id) REFERENCES products (product_id), FOREIGN KEY (seller_id) REFERENCES sellers (seller_id));",
        "CREATE TABLE order_payments (order_id TEXT NOT NULL, payment_sequential INTEGER NOT NULL, payment_type TEXT, payment_installments INTEGER, payment_value REAL, PRIMARY KEY (order_id, payment_sequential), FOREIGN KEY (order_id) REFERENCES orders (order_id));",
        "CREATE TABLE order_reviews (review_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, review_score INTEGER, review_comment_title TEXT, review_comment_message TEXT, review_creation_date TEXT, review_answer_timestamp TEXT, FOREIGN KEY (order_id) REFERENCES orders (order_id));",
        "CREATE TABLE geolocation (geolocation_zip_code_prefix TEXT, geolocation_lat REAL, geolocation_lng REAL, geolocation_city TEXT, geolocation_state TEXT);"
    ]

    for ddl in ddl_statements:
        cursor.execute(ddl)

    load_order = ["customers", "sellers", "category_translation", "products", "orders", "order_items", "order_payments", "order_reviews", "geolocation"]
    for tbl in load_order:
        df_copy = clean_tables[tbl].copy()
        for col in df_copy.columns:
            if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        df_copy.to_sql(tbl, conn, if_exists="append", index=False)

    indexes = [
        "CREATE INDEX idx_orders_customer_id ON orders(customer_id);",
        "CREATE INDEX idx_orders_purchase_timestamp ON orders(order_purchase_timestamp);",
        "CREATE INDEX idx_order_items_order_id ON order_items(order_id);",
        "CREATE INDEX idx_order_items_product_id ON order_items(product_id);",
        "CREATE INDEX idx_order_items_seller_id ON order_items(seller_id);",
        "CREATE INDEX idx_order_payments_order_id ON order_payments(order_id);",
        "CREATE INDEX idx_order_reviews_order_id ON order_reviews(order_id);",
        "CREATE INDEX idx_products_category ON products(product_category_name);",
        "CREATE INDEX idx_geolocation_zip ON geolocation(geolocation_zip_code_prefix);"
    ]
    for idx_sql in indexes:
        cursor.execute(idx_sql)

    conn.commit()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Sanity Checks
    query1 = "SELECT 'customers' AS tbl, COUNT(*) FROM customers UNION ALL SELECT 'sellers', COUNT(*) FROM sellers UNION ALL SELECT 'category_translation', COUNT(*) FROM category_translation UNION ALL SELECT 'products', COUNT(*) FROM products UNION ALL SELECT 'orders', COUNT(*) FROM orders UNION ALL SELECT 'order_items', COUNT(*) FROM order_items UNION ALL SELECT 'order_payments', COUNT(*) FROM order_payments UNION ALL SELECT 'order_reviews', COUNT(*) FROM order_reviews UNION ALL SELECT 'geolocation', COUNT(*) FROM geolocation;"
    df_sc1 = pd.read_sql_query(query1, conn)
    print("\n--- Sanity Check 1: Row Counts ---", flush=True)
    print(df_sc1.to_string(index=False), flush=True)

    query2 = "SELECT COUNT(*) AS orphan_items FROM order_items oi LEFT JOIN orders o ON oi.order_id = o.order_id WHERE o.order_id IS NULL;"
    df_sc2 = pd.read_sql_query(query2, conn)
    print("\n--- Sanity Check 2: Orphan order_items.order_id ---", flush=True)
    print(df_sc2.to_string(index=False), flush=True)

    query3 = "SELECT (SELECT COUNT(*) FROM order_items oi LEFT JOIN products p ON oi.product_id = p.product_id WHERE p.product_id IS NULL) AS orphan_prod, (SELECT COUNT(*) FROM order_items oi LEFT JOIN sellers s ON oi.seller_id = s.seller_id WHERE s.seller_id IS NULL) AS orphan_seller;"
    df_sc3 = pd.read_sql_query(query3, conn)
    print("\n--- Sanity Check 3: Orphan products & sellers ---", flush=True)
    print(df_sc3.to_string(index=False), flush=True)

    query4 = "SELECT (SELECT COUNT(*) FROM order_payments op LEFT JOIN orders o ON op.order_id = o.order_id WHERE o.order_id IS NULL) AS orphan_payments, (SELECT COUNT(*) FROM order_reviews r LEFT JOIN orders o ON r.order_id = o.order_id WHERE o.order_id IS NULL) AS orphan_reviews;"
    df_sc4 = pd.read_sql_query(query4, conn)
    print("\n--- Sanity Check 4: Orphan payments & reviews ---", flush=True)
    print(df_sc4.to_string(index=False), flush=True)

    query5 = "SELECT MIN(order_purchase_timestamp) AS min_date, MAX(order_purchase_timestamp) AS max_date FROM orders;"
    df_sc5 = pd.read_sql_query(query5, conn)
    print("\n--- Sanity Check 5: Date Range ---", flush=True)
    print(df_sc5.to_string(index=False), flush=True)

    conn.close()
    log("Phase 2 Complete.")


# ==========================================
# PHASE 3: EXPLORATORY DATA ANALYSIS
# ==========================================
def run_phase3_eda():
    log("==========================================")
    log("STARTING PHASE 3: EXPLORATORY DATA ANALYSIS")
    log("==========================================")
    conn = sqlite3.connect(DB_PATH)

    # Q1: Monthly Trend
    query1 = "SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS year_month, COUNT(DISTINCT o.order_id) AS order_count, SUM(p.payment_value) AS total_revenue FROM orders o JOIN order_payments p ON o.order_id = p.order_id WHERE o.order_purchase_timestamp IS NOT NULL AND o.order_status NOT IN ('canceled', 'unavailable') GROUP BY year_month HAVING year_month >= '2016-09' AND year_month <= '2018-09' ORDER BY year_month;"
    df_q1 = pd.read_sql_query(query1, conn)
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    sns.lineplot(data=df_q1, x="year_month", y="total_revenue", ax=ax1, color="#1f77b4", marker="o", linewidth=2.5)
    sns.barplot(data=df_q1, x="year_month", y="order_count", ax=ax2, color="#aec7e8", alpha=0.4)
    ax1.set_title("Monthly Revenue & Order Volume Trend (2016–2018)", fontsize=14, fontweight="bold", pad=15)
    ax1.set_xticks(range(len(df_q1)))
    ax1.set_xticklabels(df_q1["year_month"], rotation=45, ha="right")
    fig.tight_layout()
    plt.savefig(os.path.join(EDA_CHARTS_DIR, "eda_1_revenue_order_trend.png"), dpi=300)
    plt.close()

    # Q2: Delivery Performance
    query2 = "SELECT order_id, (julianday(order_delivered_customer_date) - julianday(order_purchase_timestamp)) AS delivery_days, CASE WHEN julianday(order_delivered_customer_date) > julianday(order_estimated_delivery_date) THEN 1 ELSE 0 END AS is_late FROM orders WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL AND order_purchase_timestamp IS NOT NULL;"
    df_q2 = pd.read_sql_query(query2, conn)
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.histplot(df_q2[df_q2["delivery_days"] <= 60]["delivery_days"], bins=60, kde=True, color="#2ca02c", ax=ax)
    ax.axvline(df_q2["delivery_days"].median(), color="red", linestyle="--", label=f"Median: {df_q2['delivery_days'].median():.1f} days")
    ax.set_title("Customer Delivery Duration Distribution (Days)", fontsize=14, fontweight="bold", pad=15)
    ax.legend()
    fig.tight_layout()
    plt.savefig(os.path.join(EDA_CHARTS_DIR, "eda_2_delivery_performance.png"), dpi=300)
    plt.close()

    # Q3: Delay vs Review
    query3 = "SELECT o.order_id, r.review_score, (julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date)) AS delay_days, CASE WHEN julianday(o.order_delivered_customer_date) > julianday(o.order_estimated_delivery_date) THEN 'Late' ELSE 'On-Time' END AS delivery_status FROM orders o JOIN order_reviews r ON o.order_id = r.order_id WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL;"
    df_q3 = pd.read_sql_query(query3, conn)
    def b_delay(days):
        if days <= 0: return "0 (On-Time)"
        elif days <= 3: return "1-3 Days Late"
        elif days <= 7: return "4-7 Days Late"
        else: return "8+ Days Late"
    df_q3["delay_bucket"] = df_q3["delay_days"].apply(b_delay)
    bucket_summary = df_q3.groupby("delay_bucket").agg(avg_review_score=("review_score", "mean"), order_count=("review_score", "count")).reindex(["0 (On-Time)", "1-3 Days Late", "4-7 Days Late", "8+ Days Late"]).reset_index()
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=bucket_summary, x="delay_bucket", y="avg_review_score", hue="delay_bucket", palette="Reds_r", ax=ax, legend=False)
    ax.set_title("Average Review Score by Delivery Delay Bucket", fontsize=14, fontweight="bold", pad=15)
    ax.set_ylim(0, 5.2)
    for idx, row in bucket_summary.iterrows():
        ax.text(idx, row["avg_review_score"] + 0.1, f"{row['avg_review_score']:.2f} stars", ha="center", fontweight="bold")
    fig.tight_layout()
    plt.savefig(os.path.join(EDA_CHARTS_DIR, "eda_3_delivery_delay_vs_review.png"), dpi=300)
    plt.close()

    # Q4: Top Product Categories
    query4 = "SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category_english, COUNT(DISTINCT oi.order_id) AS order_count, SUM(oi.price) AS total_revenue FROM order_items oi JOIN products p ON oi.product_id = p.product_id LEFT JOIN category_translation t ON p.product_category_name = t.product_category_name GROUP BY category_english;"
    df_q4 = pd.read_sql_query(query4, conn)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    sns.barplot(data=df_q4.sort_values("total_revenue", ascending=False).head(15), y="category_english", x="total_revenue", hue="category_english", palette="Blues_r", ax=ax1, legend=False)
    sns.barplot(data=df_q4.sort_values("order_count", ascending=False).head(15), y="category_english", x="order_count", hue="category_english", palette="Greens_r", ax=ax2, legend=False)
    fig.suptitle("Top 15 Product Categories by Revenue and Order Volume", fontsize=15, fontweight="bold")
    fig.tight_layout()
    plt.savefig(os.path.join(EDA_CHARTS_DIR, "eda_4_top_product_categories.png"), dpi=300)
    plt.close()

    # Q5: Top Sellers
    query5 = "SELECT oi.seller_id, SUM(oi.price) AS total_revenue, AVG(r.review_score) AS avg_review_score FROM order_items oi LEFT JOIN order_reviews r ON oi.order_id = r.order_id GROUP BY oi.seller_id ORDER BY total_revenue DESC LIMIT 15;"
    df_q5 = pd.read_sql_query(query5, conn)
    df_q5["seller_short"] = df_q5["seller_id"].str[:8] + "..."
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    sns.barplot(data=df_q5, x="seller_short", y="total_revenue", ax=ax1, color="#3182bd", alpha=0.85)
    sns.lineplot(data=df_q5, x="seller_short", y="avg_review_score", ax=ax2, color="#e6550d", marker="D", linewidth=2.5)
    ax1.set_title("Top 15 Sellers by Revenue and Their Review Scores", fontsize=14, fontweight="bold", pad=15)
    ax1.set_xticks(range(len(df_q5)))
    ax1.set_xticklabels(df_q5["seller_short"], rotation=45, ha="right")
    fig.tight_layout()
    plt.savefig(os.path.join(EDA_CHARTS_DIR, "eda_5_top_sellers.png"), dpi=300)
    plt.close()

    # Q6: Payment Methods
    query6 = "SELECT payment_type, COUNT(DISTINCT order_id) AS order_count, SUM(payment_value) AS total_payment, AVG(payment_installments) AS avg_installments FROM order_payments WHERE payment_type != 'not_defined' GROUP BY payment_type ORDER BY order_count DESC;"
    df_q6 = pd.read_sql_query(query6, conn)
    df_q6["order_share_pct"] = (df_q6["order_count"] / df_q6["order_count"].sum()) * 100
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    sns.barplot(data=df_q6, x="payment_type", y="order_share_pct", hue="payment_type", palette="Purples_r", ax=ax1, legend=False)
    sns.barplot(data=df_q6, x="payment_type", y="avg_installments", hue="payment_type", palette="Oranges_r", ax=ax2, legend=False)
    fig.suptitle("Payment Method Breakdown and Installment Dynamics", fontsize=15, fontweight="bold")
    fig.tight_layout()
    plt.savefig(os.path.join(EDA_CHARTS_DIR, "eda_6_payment_methods.png"), dpi=300)
    plt.close()

    # Q7: Geographic Breakdown
    query7 = "SELECT c.customer_state, COUNT(DISTINCT o.order_id) AS order_count, AVG(p.payment_value) AS avg_order_value FROM orders o JOIN customers c ON o.customer_id = c.customer_id JOIN (SELECT order_id, SUM(payment_value) AS payment_value FROM order_payments GROUP BY order_id) p ON o.order_id = p.order_id GROUP BY c.customer_state ORDER BY order_count DESC;"
    df_q7 = pd.read_sql_query(query7, conn)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    sns.barplot(data=df_q7.head(15), x="customer_state", y="order_count", hue="customer_state", palette="Blues_r", ax=ax1, legend=False)
    sns.barplot(data=df_q7.head(15), x="customer_state", y="avg_order_value", hue="customer_state", palette="YlOrBr_r", ax=ax2, legend=False)
    fig.suptitle("Geographic Breakdown by Customer State", fontsize=15, fontweight="bold")
    fig.tight_layout()
    plt.savefig(os.path.join(EDA_CHARTS_DIR, "eda_7_geographic_breakdown.png"), dpi=300)
    plt.close()

    conn.close()
    log("Phase 3 Complete.")


def main():
    log("Running Master Olist Data Pipeline (Phases 1-3, FR-2, FR-3)...")
    tables = run_phase1_ingestion_cleaning()
    run_phase2_database_loading(tables)
    run_phase3_eda()
    
    # Run FR-2, FR-3, and FR-4 analytics modules
    try:
        from src import fr2_fr3_analytics, fr4_analytics
        fr2_fr3_analytics.main()
        fr4_analytics.main()
    except ImportError:
        import fr2_fr3_analytics
        import fr4_analytics
        fr2_fr3_analytics.main()
        fr4_analytics.main()
        
    log("ALL PIPELINE PHASES (PHASE 1-3, FR-2, FR-3, FR-4) COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()

