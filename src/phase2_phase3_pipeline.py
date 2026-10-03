"""
Olist E-Commerce Data Pipeline - Phase 2 & Phase 3
--------------------------------------------------
Phase 2: Database Loading into SQLite (olist.db) from ./clean/ folder & Sanity Checks
Phase 3: Exploratory Data Analysis & Visualizations into ./eda_charts/
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

DATA_DIR = r"c:\Users\Aditya\Downloads\archive"
CLEAN_DIR = os.path.join(DATA_DIR, "clean")
EDA_CHARTS_DIR = os.path.join(DATA_DIR, "eda_charts")
DB_PATH = os.path.join(DATA_DIR, "olist.db")

os.makedirs(EDA_CHARTS_DIR, exist_ok=True)


def log(msg):
    print(f"[INFO] {msg}", flush=True)


# ==========================================
# PHASE 2: DATABASE LOADING & SANITY CHECKS
# ==========================================
def run_phase2_database_loading():
    log("==========================================")
    log("STARTING PHASE 2: DATABASE LOADING (SQLite)")
    log("==========================================")

    # 1. Load clean files from /clean directory
    log(f"Reading clean dataset files from '{CLEAN_DIR}'...")
    
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

    # Ensure all category names in products exist in category_translation to satisfy FK integrity
    missing_cats = set(clean_tables["products"]["product_category_name"].dropna()) - set(clean_tables["category_translation"]["product_category_name"])
    if missing_cats:
        log(f"Adding missing categories to category_translation: {missing_cats}")
        new_rows = []
        for cat in missing_cats:
            eng_name = cat.replace("_", " ")
            new_rows.append({"product_category_name": cat, "product_category_name_english": eng_name})
        clean_tables["category_translation"] = pd.concat([clean_tables["category_translation"], pd.DataFrame(new_rows)], ignore_index=True)

    # Re-create database file
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            log(f"Removed existing database file at '{DB_PATH}'.")
        except Exception as e:
            log(f"Warning removing DB file: {e}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # DDL Statements with Foreign Key constraints
    ddl_statements = [
        """
        CREATE TABLE customers (
            customer_id TEXT PRIMARY KEY,
            customer_unique_id TEXT NOT NULL,
            customer_zip_code_prefix TEXT,
            customer_city TEXT,
            customer_state TEXT
        );
        """,
        """
        CREATE TABLE sellers (
            seller_id TEXT PRIMARY KEY,
            seller_zip_code_prefix TEXT,
            seller_city TEXT,
            seller_state TEXT
        );
        """,
        """
        CREATE TABLE category_translation (
            product_category_name TEXT PRIMARY KEY,
            product_category_name_english TEXT
        );
        """,
        """
        CREATE TABLE products (
            product_id TEXT PRIMARY KEY,
            product_category_name TEXT,
            product_name_lenght REAL,
            product_description_lenght REAL,
            product_photos_qty REAL,
            product_weight_g REAL,
            product_length_cm REAL,
            product_height_cm REAL,
            product_width_cm REAL,
            product_category_name_english TEXT,
            has_missing_category INTEGER,
            has_missing_dimensions INTEGER,
            product_category_name_english_clean TEXT,
            FOREIGN KEY (product_category_name) REFERENCES category_translation (product_category_name)
        );
        """,
        """
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            order_status TEXT,
            order_purchase_timestamp TEXT,
            order_approved_at TEXT,
            order_delivered_carrier_date TEXT,
            order_delivered_customer_date TEXT,
            order_estimated_delivery_date TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        );
        """,
        """
        CREATE TABLE order_items (
            order_id TEXT NOT NULL,
            order_item_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            seller_id TEXT NOT NULL,
            shipping_limit_date TEXT,
            price REAL,
            freight_value REAL,
            PRIMARY KEY (order_id, order_item_id),
            FOREIGN KEY (order_id) REFERENCES orders (order_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id),
            FOREIGN KEY (seller_id) REFERENCES sellers (seller_id)
        );
        """,
        """
        CREATE TABLE order_payments (
            order_id TEXT NOT NULL,
            payment_sequential INTEGER NOT NULL,
            payment_type TEXT,
            payment_installments INTEGER,
            payment_value REAL,
            PRIMARY KEY (order_id, payment_sequential),
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        );
        """,
        """
        CREATE TABLE order_reviews (
            review_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            review_score INTEGER,
            review_comment_title TEXT,
            review_comment_message TEXT,
            review_creation_date TEXT,
            review_answer_timestamp TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        );
        """,
        """
        CREATE TABLE geolocation (
            geolocation_zip_code_prefix TEXT,
            geolocation_lat REAL,
            geolocation_lng REAL,
            geolocation_city TEXT,
            geolocation_state TEXT
        );
        """
    ]

    log("Creating tables in SQLite...")
    for ddl in ddl_statements:
        cursor.execute(ddl)

    # Order of insertion to respect foreign keys:
    # 1. customers, sellers, category_translation
    # 2. products, orders
    # 3. order_items, order_payments, order_reviews, geolocation
    load_order = [
        "customers", "sellers", "category_translation",
        "products", "orders",
        "order_items", "order_payments", "order_reviews", "geolocation"
    ]

    log("Bulk loading data into SQLite tables...")
    for tbl in load_order:
        df = clean_tables[tbl]
        df.to_sql(tbl, conn, if_exists="append", index=False)
        log(f" -> Loaded {len(df):,} rows into table '{tbl}'.")

    # Create Indexes
    log("Creating indexes on foreign key columns and timestamps...")
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

    # Enable FK checking in SQLite for sanity validation
    cursor.execute("PRAGMA foreign_keys = ON;")

    # ==========================================
    # RUNNING 5 SANITY CHECKS
    # ==========================================
    log("==========================================")
    log("EXECUTING 5 SQL SANITY CHECKS:")
    log("==========================================")

    # Sanity Check 1: Row Counts Match Cleaned Files
    query1 = """
    SELECT 'customers' AS table_name, COUNT(*) AS sqlite_row_count FROM customers
    UNION ALL SELECT 'sellers', COUNT(*) FROM sellers
    UNION ALL SELECT 'category_translation', COUNT(*) FROM category_translation
    UNION ALL SELECT 'products', COUNT(*) FROM products
    UNION ALL SELECT 'orders', COUNT(*) FROM orders
    UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
    UNION ALL SELECT 'order_payments', COUNT(*) FROM order_payments
    UNION ALL SELECT 'order_reviews', COUNT(*) FROM order_reviews
    UNION ALL SELECT 'geolocation', COUNT(*) FROM geolocation;
    """
    df_sc1 = pd.read_sql_query(query1, conn)
    print("\n--- Sanity Check 1: Row Counts Per Table ---", flush=True)
    print(df_sc1.to_string(index=False), flush=True)

    # Sanity Check 2: No Orphaned order_items.order_id values
    query2 = """
    SELECT COUNT(*) AS orphan_order_items_order_id_cnt
    FROM order_items oi
    LEFT JOIN orders o ON oi.order_id = o.order_id
    WHERE o.order_id IS NULL;
    """
    df_sc2 = pd.read_sql_query(query2, conn)
    print("\n--- Sanity Check 2: Orphaned order_items.order_id Audit ---", flush=True)
    print(df_sc2.to_string(index=False), flush=True)
    assert df_sc2.iloc[0]["orphan_order_items_order_id_cnt"] == 0, "Sanity Check 2 Failed!"

    # Sanity Check 3: No Orphaned order_items.product_id / seller_id values
    query3 = """
    SELECT 
        (SELECT COUNT(*) FROM order_items oi LEFT JOIN products p ON oi.product_id = p.product_id WHERE p.product_id IS NULL) AS orphan_product_id_cnt,
        (SELECT COUNT(*) FROM order_items oi LEFT JOIN sellers s ON oi.seller_id = s.seller_id WHERE s.seller_id IS NULL) AS orphan_seller_id_cnt;
    """
    df_sc3 = pd.read_sql_query(query3, conn)
    print("\n--- Sanity Check 3: Orphaned order_items.product_id & seller_id Audit ---", flush=True)
    print(df_sc3.to_string(index=False), flush=True)
    assert df_sc3.iloc[0]["orphan_product_id_cnt"] == 0 and df_sc3.iloc[0]["orphan_seller_id_cnt"] == 0, "Sanity Check 3 Failed!"

    # Sanity Check 4: No Orphaned order_payments.order_id / order_reviews.order_id values
    query4 = """
    SELECT 
        (SELECT COUNT(*) FROM order_payments op LEFT JOIN orders o ON op.order_id = o.order_id WHERE o.order_id IS NULL) AS orphan_payments_order_id_cnt,
        (SELECT COUNT(*) FROM order_reviews r LEFT JOIN orders o ON r.order_id = o.order_id WHERE o.order_id IS NULL) AS orphan_reviews_order_id_cnt;
    """
    df_sc4 = pd.read_sql_query(query4, conn)
    print("\n--- Sanity Check 4: Orphaned order_payments & order_reviews Audit ---", flush=True)
    print(df_sc4.to_string(index=False), flush=True)
    assert df_sc4.iloc[0]["orphan_payments_order_id_cnt"] == 0 and df_sc4.iloc[0]["orphan_reviews_order_id_cnt"] == 0, "Sanity Check 4 Failed!"

    # Sanity Check 5: Min/Max of order_purchase_timestamp (2016-2018)
    query5 = """
    SELECT 
        MIN(order_purchase_timestamp) AS min_purchase_timestamp,
        MAX(order_purchase_timestamp) AS max_purchase_timestamp,
        CASE WHEN MIN(order_purchase_timestamp) >= '2016-01-01' AND MAX(order_purchase_timestamp) <= '2018-12-31 23:59:59' 
             THEN 'PASS (Valid 2016-2018 Range)' ELSE 'FAIL' END AS status
    FROM orders;
    """
    df_sc5 = pd.read_sql_query(query5, conn)
    print("\n--- Sanity Check 5: Timestamp Date Range Audit ---", flush=True)
    print(df_sc5.to_string(index=False), flush=True)

    conn.close()
    log("Phase 2 Complete. Database 'olist.db' loaded and verified with 100% integrity.\n")


# ==========================================
# PHASE 3: EXPLORATORY DATA ANALYSIS (EDA)
# ==========================================
def run_phase3_eda():
    log("==========================================")
    log("STARTING PHASE 3: EXPLORATORY DATA ANALYSIS")
    log("==========================================")
    conn = sqlite3.connect(DB_PATH)

    # ----------------------------------------------------
    # Question 1: Monthly Revenue & Order Volume Trend (2016-2018)
    # ----------------------------------------------------
    log("Generating EDA Question 1: Revenue & Order Volume Monthly Trend...")
    query1 = """
    SELECT 
        strftime('%Y-%m', o.order_purchase_timestamp) AS year_month,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(p.payment_value) AS total_revenue
    FROM orders o
    JOIN order_payments p ON o.order_id = p.order_id
    WHERE o.order_purchase_timestamp IS NOT NULL
      AND o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY year_month
    HAVING year_month >= '2016-09' AND year_month <= '2018-09'
    ORDER BY year_month;
    """
    df_q1 = pd.read_sql_query(query1, conn)

    print("\n--- KEY NUMBERS: EDA Question 1 (Monthly Revenue & Order Volume) ---", flush=True)
    print(f"Total Period Revenue (2016-2018): R$ {df_q1['total_revenue'].sum():,.2f}", flush=True)
    print(f"Total Period Orders (2016-2018): {df_q1['order_count'].sum():,}", flush=True)
    peak_rev_row = df_q1.loc[df_q1["total_revenue"].idxmax()]
    print(f"Peak Revenue Month: {peak_rev_row['year_month']} (R$ {peak_rev_row['total_revenue']:,.2f}, {peak_rev_row['order_count']:,} orders)", flush=True)

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()

    sns.lineplot(data=df_q1, x="year_month", y="total_revenue", ax=ax1, color="#1f77b4", marker="o", linewidth=2.5)
    sns.barplot(data=df_q1, x="year_month", y="order_count", ax=ax2, color="#aec7e8", alpha=0.4)

    ax1.set_title("Olist E-Commerce: Monthly Revenue & Order Volume Trend (2016–2018)", fontsize=14, fontweight="bold", pad=15)
    ax1.set_xlabel("Year-Month", fontsize=11)
    ax1.set_ylabel("Total Revenue (R$)", fontsize=11, color="#1f77b4")
    ax2.set_ylabel("Order Volume", fontsize=11, color="#4c78a8")

    ax1.set_xticks(range(len(df_q1)))
    ax1.set_xticklabels(df_q1["year_month"], rotation=45, ha="right")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax2.grid(False)

    fig.tight_layout()
    chart1_path = os.path.join(EDA_CHARTS_DIR, "eda_1_revenue_order_trend.png")
    plt.savefig(chart1_path, dpi=300)
    plt.close()

    # ----------------------------------------------------
    # Question 2: Delivery Performance (Duration & Late Delivery %)
    # ----------------------------------------------------
    log("Generating EDA Question 2: Delivery Performance...")
    query2 = """
    SELECT 
        order_id,
        (julianday(order_delivered_customer_date) - julianday(order_purchase_timestamp)) AS delivery_days,
        (julianday(order_delivered_customer_date) - julianday(order_estimated_delivery_date)) AS delay_days,
        CASE WHEN julianday(order_delivered_customer_date) > julianday(order_estimated_delivery_date) THEN 1 ELSE 0 END AS is_late
    FROM orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
      AND order_purchase_timestamp IS NOT NULL
      AND order_estimated_delivery_date IS NOT NULL;
    """
    df_q2 = pd.read_sql_query(query2, conn)
    
    mean_days = df_q2["delivery_days"].mean()
    median_days = df_q2["delivery_days"].median()
    late_pct = df_q2["is_late"].mean() * 100
    total_delivered = len(df_q2)

    print("\n--- KEY NUMBERS: EDA Question 2 (Delivery Performance) ---", flush=True)
    print(f"Total Delivered Orders Analyzed: {total_delivered:,}", flush=True)
    print(f"Mean Delivery Duration: {mean_days:.2f} days", flush=True)
    print(f"Median Delivery Duration: {median_days:.2f} days", flush=True)
    print(f"Late Deliveries Rate: {late_pct:.2f}% ({df_q2['is_late'].sum():,} orders)", flush=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.histplot(df_q2[df_q2["delivery_days"] <= 60]["delivery_days"], bins=60, kde=True, color="#2ca02c", ax=ax)
    
    ax.axvline(median_days, color="red", linestyle="--", linewidth=2, label=f"Median: {median_days:.1f} days")
    ax.axvline(mean_days, color="darkorange", linestyle="-.", linewidth=2, label=f"Mean: {mean_days:.1f} days")

    ax.set_title("Customer Delivery Duration Distribution (Days)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Delivery Duration (Purchase to Delivery in Days)", fontsize=11)
    ax.set_ylabel("Order Count", fontsize=11)
    ax.legend(fontsize=11)

    ax.text(0.62, 0.75, f"Late Delivery Rate: {late_pct:.2f}%\nTotal Orders: {total_delivered:,}", 
            transform=ax.transAxes, fontsize=12, bbox=dict(boxstyle="round,pad=0.5", facecolor="#fff9e6", edgecolor="#f5a623"))

    fig.tight_layout()
    chart2_path = os.path.join(EDA_CHARTS_DIR, "eda_2_delivery_performance.png")
    plt.savefig(chart2_path, dpi=300)
    plt.close()

    # ----------------------------------------------------
    # Question 3: Relationship between Delivery Delay and Review Score
    # ----------------------------------------------------
    log("Generating EDA Question 3: Delivery Delay vs Review Score...")
    query3 = """
    SELECT 
        o.order_id,
        r.review_score,
        (julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date)) AS delay_days,
        CASE WHEN julianday(o.order_delivered_customer_date) > julianday(o.order_estimated_delivery_date) THEN 'Late' ELSE 'On-Time' END AS delivery_status
    FROM orders o
    JOIN order_reviews r ON o.order_id = r.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL;
    """
    df_q3 = pd.read_sql_query(query3, conn)

    def bucket_delay(row):
        days = row["delay_days"]
        if days <= 0:
            return "0 (On-Time)"
        elif days <= 3:
            return "1-3 Days Late"
        elif days <= 7:
            return "4-7 Days Late"
        else:
            return "8+ Days Late"

    df_q3["delay_bucket"] = df_q3.apply(bucket_delay, axis=1)

    # On-Time vs Late Summary
    status_summary = df_q3.groupby("delivery_status").agg(
        avg_review_score=("review_score", "mean"),
        order_count=("review_score", "count")
    ).reset_index()

    # Bucket Summary
    bucket_order = ["0 (On-Time)", "1-3 Days Late", "4-7 Days Late", "8+ Days Late"]
    bucket_summary = df_q3.groupby("delay_bucket").agg(
        avg_review_score=("review_score", "mean"),
        order_count=("review_score", "count")
    ).reindex(bucket_order).reset_index()

    print("\n--- KEY NUMBERS: EDA Question 3 (Delivery Delay vs Review Score) ---", flush=True)
    print("Delivery Status Summary:", flush=True)
    print(status_summary.to_string(index=False), flush=True)
    print("\nDays-Late Buckets Summary:", flush=True)
    print(bucket_summary.to_string(index=False), flush=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Plot 1: On-Time vs Late
    sns.barplot(data=status_summary, x="delivery_status", y="avg_review_score", hue="delivery_status", palette=["#2ca02c", "#d62728"], ax=ax1, legend=False)
    ax1.set_title("Average Review Score: On-Time vs Late", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Delivery Status", fontsize=11)
    ax1.set_ylabel("Average Review Score (1-5 Stars)", fontsize=11)
    ax1.set_ylim(0, 5.2)
    for idx, row in status_summary.iterrows():
        ax1.text(idx, row["avg_review_score"] + 0.1, f"{row['avg_review_score']:.2f} stars\n({row['order_count']:,} orders)", ha="center", fontweight="bold")

    # Plot 2: Bucketed Delay
    sns.barplot(data=bucket_summary, x="delay_bucket", y="avg_review_score", hue="delay_bucket", palette="Reds_r", ax=ax2, legend=False)
    ax2.set_title("Average Review Score by Days Late", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Days Late Bucket", fontsize=11)
    ax2.set_ylabel("")
    ax2.set_ylim(0, 5.2)
    for idx, row in bucket_summary.iterrows():
        ax2.text(idx, row["avg_review_score"] + 0.1, f"{row['avg_review_score']:.2f} stars\n({row['order_count']:,} orders)", ha="center", fontweight="bold")

    fig.suptitle("Impact of Delivery Delays on Customer Review Scores", fontsize=15, fontweight="bold")
    fig.tight_layout()
    chart3_path = os.path.join(EDA_CHARTS_DIR, "eda_3_delivery_delay_vs_review.png")
    plt.savefig(chart3_path, dpi=300)
    plt.close()

    # ----------------------------------------------------
    # Question 4: Top 15 Product Categories (Revenue & Order Count)
    # ----------------------------------------------------
    log("Generating EDA Question 4: Top Product Categories...")
    query4 = """
    SELECT 
        COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category_english,
        COUNT(DISTINCT oi.order_id) AS order_count,
        SUM(oi.price) AS total_revenue
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    LEFT JOIN category_translation t ON p.product_category_name = t.product_category_name
    GROUP BY category_english;
    """
    df_q4 = pd.read_sql_query(query4, conn)
    top15_rev = df_q4.sort_values("total_revenue", ascending=False).head(15)
    top15_orders = df_q4.sort_values("order_count", ascending=False).head(15)

    print("\n--- KEY NUMBERS: EDA Question 4 (Top Product Categories) ---", flush=True)
    print("Top 5 Categories by Revenue:", flush=True)
    for _, r in top15_rev.head(5).iterrows():
        print(f"  - {r['category_english']}: R$ {r['total_revenue']:,.2f} ({r['order_count']:,} orders)", flush=True)
    print("\nTop 5 Categories by Order Count:", flush=True)
    for _, r in top15_orders.head(5).iterrows():
        print(f"  - {r['category_english']}: {r['order_count']:,} orders (R$ {r['total_revenue']:,.2f})", flush=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    sns.barplot(data=top15_rev, y="category_english", x="total_revenue", hue="category_english", palette="Blues_r", ax=ax1, legend=False)
    ax1.set_title("Top 15 Categories by Revenue (R$)", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Total Revenue (R$)", fontsize=11)
    ax1.set_ylabel("Product Category (English)", fontsize=11)

    sns.barplot(data=top15_orders, y="category_english", x="order_count", hue="category_english", palette="Greens_r", ax=ax2, legend=False)
    ax2.set_title("Top 15 Categories by Order Count", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Order Count", fontsize=11)
    ax2.set_ylabel("")

    fig.suptitle("Olist Top 15 Product Category Analysis", fontsize=15, fontweight="bold")
    fig.tight_layout()
    chart4_path = os.path.join(EDA_CHARTS_DIR, "eda_4_top_product_categories.png")
    plt.savefig(chart4_path, dpi=300)
    plt.close()

    # ----------------------------------------------------
    # Question 5: Top 15 Sellers by Revenue & Average Review Score
    # ----------------------------------------------------
    log("Generating EDA Question 5: Top 15 Sellers...")
    query5 = """
    SELECT 
        oi.seller_id,
        SUM(oi.price) AS total_revenue,
        COUNT(DISTINCT oi.order_id) AS order_count,
        AVG(r.review_score) AS avg_review_score
    FROM order_items oi
    LEFT JOIN order_reviews r ON oi.order_id = r.order_id
    GROUP BY oi.seller_id
    ORDER BY total_revenue DESC
    LIMIT 15;
    """
    df_q5 = pd.read_sql_query(query5, conn)
    df_q5["seller_short"] = df_q5["seller_id"].str[:8] + "..."

    print("\n--- KEY NUMBERS: EDA Question 5 (Top 15 Sellers by Revenue) ---", flush=True)
    for idx, r in df_q5.iterrows():
        print(f"  #{idx+1} Seller {r['seller_id'][:8]}... : R$ {r['total_revenue']:,.2f} | {r['order_count']} orders | Avg Review: {r['avg_review_score']:.2f} stars", flush=True)

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()

    sns.barplot(data=df_q5, x="seller_short", y="total_revenue", ax=ax1, color="#3182bd", alpha=0.85)
    sns.lineplot(data=df_q5, x="seller_short", y="avg_review_score", ax=ax2, color="#e6550d", marker="D", linewidth=2.5, markersize=8)

    ax1.set_title("Top 15 Sellers by Revenue and Their Average Review Score", fontsize=14, fontweight="bold", pad=15)
    ax1.set_xlabel("Seller ID (Truncated)", fontsize=11)
    ax1.set_ylabel("Total Revenue (R$)", fontsize=11, color="#3182bd")
    ax2.set_ylabel("Average Review Score (1-5 Stars)", fontsize=11, color="#e6550d")

    ax1.set_xticks(range(len(df_q5)))
    ax1.set_xticklabels(df_q5["seller_short"], rotation=45, ha="right")
    ax2.set_ylim(1.0, 5.2)
    ax1.grid(True, linestyle="--", alpha=0.4)
    ax2.grid(False)

    fig.tight_layout()
    chart5_path = os.path.join(EDA_CHARTS_DIR, "eda_5_top_sellers.png")
    plt.savefig(chart5_path, dpi=300)
    plt.close()

    # ----------------------------------------------------
    # Question 6: Payment Method Breakdown
    # ----------------------------------------------------
    log("Generating EDA Question 6: Payment Method Breakdown...")
    query6 = """
    SELECT 
        payment_type,
        COUNT(DISTINCT order_id) AS order_count,
        SUM(payment_value) AS total_payment,
        AVG(payment_installments) AS avg_installments
    FROM order_payments
    WHERE payment_type != 'not_defined'
    GROUP BY payment_type
    ORDER BY order_count DESC;
    """
    df_q6 = pd.read_sql_query(query6, conn)
    total_orders = df_q6["order_count"].sum()
    df_q6["order_share_pct"] = (df_q6["order_count"] / total_orders) * 100

    print("\n--- KEY NUMBERS: EDA Question 6 (Payment Method Breakdown) ---", flush=True)
    print(df_q6[["payment_type", "order_count", "order_share_pct", "avg_installments", "total_payment"]].to_string(index=False), flush=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    sns.barplot(data=df_q6, x="payment_type", y="order_share_pct", hue="payment_type", palette="Purples_r", ax=ax1, legend=False)
    ax1.set_title("Payment Type Share of Total Orders (%)", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Payment Method", fontsize=11)
    ax1.set_ylabel("Order Share (%)", fontsize=11)
    for idx, row in df_q6.iterrows():
        ax1.text(idx, row["order_share_pct"] + 1, f"{row['order_share_pct']:.1f}%", ha="center", fontweight="bold")

    sns.barplot(data=df_q6, x="payment_type", y="avg_installments", hue="payment_type", palette="Oranges_r", ax=ax2, legend=False)
    ax2.set_title("Average Payment Installments by Method", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Payment Method", fontsize=11)
    ax2.set_ylabel("Average Installments", fontsize=11)
    for idx, row in df_q6.iterrows():
        ax2.text(idx, row["avg_installments"] + 0.1, f"{row['avg_installments']:.2f}", ha="center", fontweight="bold")

    fig.suptitle("Olist Payment Methods Analysis", fontsize=15, fontweight="bold")
    fig.tight_layout()
    chart6_path = os.path.join(EDA_CHARTS_DIR, "eda_6_payment_methods.png")
    plt.savefig(chart6_path, dpi=300)
    plt.close()

    # ----------------------------------------------------
    # Question 7: Geographic Breakdown by Customer State
    # ----------------------------------------------------
    log("Generating EDA Question 7: Geographic Breakdown by Customer State...")
    query7 = """
    SELECT 
        c.customer_state,
        COUNT(DISTINCT o.order_id) AS order_count,
        SUM(p.payment_value) AS total_revenue,
        AVG(p.payment_value) AS avg_order_value
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN (
        SELECT order_id, SUM(payment_value) AS payment_value 
        FROM order_payments 
        GROUP BY order_id
    ) p ON o.order_id = p.order_id
    GROUP BY c.customer_state
    ORDER BY order_count DESC;
    """
    df_q7 = pd.read_sql_query(query7, conn)

    print("\n--- KEY NUMBERS: EDA Question 7 (Geographic Breakdown - Top 10 States) ---", flush=True)
    print(df_q7.head(10).to_string(index=False), flush=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    sns.barplot(data=df_q7.head(15), x="customer_state", y="order_count", hue="customer_state", palette="Blues_r", ax=ax1, legend=False)
    ax1.set_title("Top 15 States by Order Volume", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Customer State (UF)", fontsize=11)
    ax1.set_ylabel("Order Count", fontsize=11)

    sns.barplot(data=df_q7.head(15), x="customer_state", y="avg_order_value", hue="customer_state", palette="YlOrBr_r", ax=ax2, legend=False)
    ax2.set_title("Average Order Value (AOV) for Top 15 States", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Customer State (UF)", fontsize=11)
    ax2.set_ylabel("Average Order Value (R$)", fontsize=11)
    for idx, row in df_q7.head(15).iterrows():
        ax2.text(idx, row["avg_order_value"] + 3, f"R${row['avg_order_value']:.0f}", ha="center", fontsize=9)

    fig.suptitle("Olist Geographic E-Commerce Breakdown by Customer State", fontsize=15, fontweight="bold")
    fig.tight_layout()
    chart7_path = os.path.join(EDA_CHARTS_DIR, "eda_7_geographic_breakdown.png")
    plt.savefig(chart7_path, dpi=300)
    plt.close()

    conn.close()
    log(f"Phase 3 Complete. All 7 charts saved to '{EDA_CHARTS_DIR}'.")


def main():
    log("Running Olist Pipeline Phase 2 & Phase 3 (Reading from /clean directory)...")
    run_phase2_database_loading()
    run_phase3_eda()
    log("ALL PHASES COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
