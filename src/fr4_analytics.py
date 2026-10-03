"""
Olist E-Commerce - FR-4 (Customer Buying Pattern Analysis) Module
------------------------------------------------------------------
Implementation of purchase frequency, Average Order Value (AOV), repeat-purchase rate,
RFM segmentation (Recency, Frequency, Monetary), peak purchase time analysis,
and reusable customer insights function with geographic and segment filters.
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Styling
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.sans-serif': 'Arial', 'font.family': 'sans-serif'})

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "olist.db")
FR4_DIR = os.path.join(BASE_DIR, "fr4_customers")

os.makedirs(FR4_DIR, exist_ok=True)


def log(msg):
    print(f"[INFO] {msg}", flush=True)


# ==============================================================================
# PART A1: PURCHASE FREQUENCY, AOV, REPEAT-PURCHASE RATE
# ==============================================================================
def run_customer_purchase_summary(db_path=DB_PATH):
    """
    Computes per-customer purchase frequency, total spend, AOV, first/last purchase dates.
    Saves results to fr4_customers/customer_purchase_summary.csv and charts order distribution.
    """
    log("Running A1: Computing Customer Purchase Summary & Repeat Rate...")
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT 
        c.customer_unique_id,
        MAX(c.customer_state) AS customer_state,
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(op.order_payment) AS total_spend,
        MIN(o.order_purchase_timestamp) AS first_purchase,
        MAX(o.order_purchase_timestamp) AS last_purchase
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN (
        SELECT order_id, SUM(payment_value) AS order_payment
        FROM order_payments
        GROUP BY order_id
    ) op ON o.order_id = op.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
      AND o.order_purchase_timestamp IS NOT NULL
    GROUP BY c.customer_unique_id;
    """
    
    df_cust = pd.read_sql_query(query, conn)
    conn.close()
    
    df_cust["average_order_value"] = (df_cust["total_spend"] / df_cust["total_orders"]).round(2)
    
    total_customers = len(df_cust)
    repeat_customers = (df_cust["total_orders"] > 1).sum()
    repeat_rate = (repeat_customers / total_customers) * 100
    overall_aov = df_cust["total_spend"].sum() / df_cust["total_orders"].sum()
    
    print("\n==========================================", flush=True)
    print("CUSTOMER PURCHASE SUMMARY HEADLINE METRICS:", flush=True)
    print("==========================================", flush=True)
    print(f"Total Unique Customers: {total_customers:,}", flush=True)
    print(f"Repeat Customers (>1 order): {repeat_customers:,}", flush=True)
    print(f"Overall Repeat Purchase Rate: {repeat_rate:.2f}%", flush=True)
    print(f"Overall Average Order Value (AOV): R$ {overall_aov:.2f}", flush=True)
    print("==========================================\n", flush=True)
    
    csv_path = os.path.join(FR4_DIR, "customer_purchase_summary.csv")
    df_cust.to_csv(csv_path, index=False)
    log(f"Saved customer purchase summary to '{csv_path}'")
    
    # Chart distribution of orders per customer
    order_counts = df_cust["total_orders"].value_counts().sort_index().reset_index()
    order_counts.columns = ["orders_count", "customer_num"]
    order_counts["percentage"] = (order_counts["customer_num"] / total_customers) * 100
    
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=order_counts.head(5), x="orders_count", y="customer_num", palette="Blues_r", ax=ax, hue="orders_count", legend=False)
    ax.set_title("Distribution of Orders per Customer (Olist E-Commerce)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Number of Orders Placed", fontsize=11)
    ax.set_ylabel("Number of Customers", fontsize=11)
    
    for idx, row in order_counts.head(5).iterrows():
        ax.text(idx, row["customer_num"] + 1000, f"{row['customer_num']:,}\n({row['percentage']:.2f}%)", 
                ha="center", fontsize=10, fontweight="bold")
        
    fig.tight_layout()
    chart_path = os.path.join(FR4_DIR, "orders_per_customer_dist.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    log(f"Saved order distribution chart to '{chart_path}'")
    
    return df_cust, repeat_rate, overall_aov


# ==============================================================================
# PART A2: RFM SEGMENTATION
# ==============================================================================
def assign_rfm_segment(row):
    """
    Rule set for RFM segment assignment:
    - Champions: R >= 4, F >= 4, M >= 4
    - Loyal Customers: F >= 4 and M >= 3 (consistent high engagement)
    - Potential Loyalists: R >= 4 and (F >= 3 or M >= 3)
    - New Customers: R >= 4 (recent buyers, lower F/M)
    - At Risk: R <= 2 and (F >= 4 or M >= 4) (previously high value, but absent)
    - Hibernating: R <= 2 and (F >= 2 or M >= 2)
    - Lost: R <= 2 (lowest recency, lowest engagement)
    - Promising: R == 3 (moderate recency)
    """
    r, f, m = row["R_score"], row["F_score"], row["M_score"]
    
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    elif f >= 4 and m >= 3:
        return "Loyal Customers"
    elif r >= 4 and (f >= 3 or m >= 3):
        return "Potential Loyalists"
    elif r >= 4:
        return "New Customers"
    elif r <= 2 and (f >= 4 or m >= 4):
        return "At Risk"
    elif r <= 2 and (f >= 2 or m >= 2):
        return "Hibernating"
    elif r <= 2:
        return "Lost"
    else:
        return "Promising"


def run_rfm_segmentation(df_cust=None, db_path=DB_PATH):
    """
    Computes R, F, M scores using pandas qcut + rank (tie breaking).
    Assigns segment labels and produces segment summary & bar charts.
    """
    log("Running A2: Computing RFM Segmentation...")
    if df_cust is None:
        conn = sqlite3.connect(db_path)
        query = """
        SELECT 
            c.customer_unique_id,
            MAX(c.customer_state) AS customer_state,
            COUNT(DISTINCT o.order_id) AS total_orders,
            SUM(op.order_payment) AS total_spend,
            MIN(o.order_purchase_timestamp) AS first_purchase,
            MAX(o.order_purchase_timestamp) AS last_purchase
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN (
            SELECT order_id, SUM(payment_value) AS order_payment
            FROM order_payments
            GROUP BY order_id
        ) op ON o.order_id = op.order_id
        WHERE o.order_status NOT IN ('canceled', 'unavailable')
          AND o.order_purchase_timestamp IS NOT NULL
        GROUP BY c.customer_unique_id;
        """
        df_cust = pd.read_sql_query(query, conn)
        conn.close()
        
    max_date = pd.to_datetime(df_cust["last_purchase"]).max()
    df_cust["recency_days"] = (max_date - pd.to_datetime(df_cust["last_purchase"])).dt.total_seconds() / (24 * 3600)
    
    # Quintile scoring with rank tie-breaking
    # Note: pandas qcut with rank(method='first') ensures exact equal 20% quintile split across tied ranks.
    df_cust["R_score"] = pd.qcut(df_cust["recency_days"].rank(method="first", ascending=True), q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    df_cust["F_score"] = pd.qcut(df_cust["total_orders"].rank(method="first", ascending=True), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    df_cust["M_score"] = pd.qcut(df_cust["total_spend"].rank(method="first", ascending=True), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    
    df_cust["rfm_segment"] = df_cust.apply(assign_rfm_segment, axis=1)
    
    # Export rfm_segments.csv
    export_cols = ["customer_unique_id", "customer_state", "recency_days", "total_orders", "total_spend", "R_score", "F_score", "M_score", "rfm_segment"]
    df_cust[export_cols].to_csv(os.path.join(FR4_DIR, "rfm_segments.csv"), index=False)
    log(f"Saved RFM customer scores to '{os.path.join(FR4_DIR, 'rfm_segments.csv')}'")
    
    # Summary Table
    rfm_summary = df_cust.groupby("rfm_segment").agg(
        customer_count=("customer_unique_id", "count"),
        total_revenue=("total_spend", "sum"),
        avg_spend=("total_spend", "mean"),
        avg_orders=("total_orders", "mean"),
        avg_recency=("recency_days", "mean")
    ).reset_index()
    
    total_revenue_all = df_cust["total_spend"].sum()
    rfm_summary["customer_pct"] = (rfm_summary["customer_count"] / len(df_cust)) * 100
    rfm_summary["revenue_pct"] = (rfm_summary["total_revenue"] / total_revenue_all) * 100
    rfm_summary = rfm_summary.sort_values("total_revenue", ascending=False)
    
    rfm_summary.to_csv(os.path.join(FR4_DIR, "rfm_summary.csv"), index=False)
    
    print("\n--- RFM SEGMENT SUMMARY TABLE ---", flush=True)
    print(rfm_summary[["rfm_segment", "customer_count", "customer_pct", "total_revenue", "revenue_pct", "avg_spend"]].to_string(index=False), flush=True)
    print("---------------------------------\n", flush=True)
    
    # Chart 1: Customer Count by Segment
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=rfm_summary, x="rfm_segment", y="customer_count", palette="viridis", ax=ax, hue="rfm_segment", legend=False)
    ax.set_title("Customer Count by RFM Segment", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("RFM Segment", fontsize=11)
    ax.set_ylabel("Customer Count", fontsize=11)
    plt.xticks(rotation=30, ha="right")
    
    for idx, row in rfm_summary.reset_index().iterrows():
        ax.text(idx, row["customer_count"] + 300, f"{row['customer_count']:,}\n({row['customer_pct']:.1f}%)", ha="center", fontsize=9)
        
    fig.tight_layout()
    plt.savefig(os.path.join(FR4_DIR, "rfm_customer_count.png"), dpi=300)
    plt.close()
    
    # Chart 2: Revenue by Segment
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=rfm_summary, x="rfm_segment", y="total_revenue", palette="magma", ax=ax, hue="rfm_segment", legend=False)
    ax.set_title("Total Revenue Contributed by RFM Segment (R$)", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("RFM Segment", fontsize=11)
    ax.set_ylabel("Total Revenue (R$)", fontsize=11)
    plt.xticks(rotation=30, ha="right")
    
    for idx, row in rfm_summary.reset_index().iterrows():
        ax.text(idx, row["total_revenue"] + 50000, f"R${row['total_revenue']/1e6:.2f}M\n({row['revenue_pct']:.1f}%)", ha="center", fontsize=9)
        
    fig.tight_layout()
    plt.savefig(os.path.join(FR4_DIR, "rfm_revenue.png"), dpi=300)
    plt.close()
    
    log(f"Saved RFM charts to '{FR4_DIR}'")
    return df_cust, rfm_summary


# ==============================================================================
# PART A3: PEAK PURCHASE TIMES
# ==============================================================================
def run_peak_purchase_times(db_path=DB_PATH):
    """
    Analyzes order_purchase_timestamp for day-of-week x hour-of-day purchase distribution.
    Generates peak times heatmap and notes per-segment breakdown feasibility.
    """
    log("Running A3: Analyzing Peak Purchase Times & Generating Heatmap...")
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT 
        o.order_id,
        c.customer_unique_id,
        o.order_purchase_timestamp,
        op.order_payment
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN (
        SELECT order_id, SUM(payment_value) AS order_payment
        FROM order_payments
        GROUP BY order_id
    ) op ON o.order_id = op.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
      AND o.order_purchase_timestamp IS NOT NULL;
    """
    df_orders = pd.read_sql_query(query, conn)
    conn.close()
    
    df_orders["timestamp"] = pd.to_datetime(df_orders["order_purchase_timestamp"])
    df_orders["hour"] = df_orders["timestamp"].dt.hour
    df_orders["day_of_week"] = df_orders["timestamp"].dt.day_name()
    
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    pivot_vol = df_orders.pivot_table(index="day_of_week", columns="hour", values="order_id", aggfunc="count", fill_value=0)
    pivot_vol = pivot_vol.reindex(days_order)
    
    # Heatmap
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(pivot_vol, cmap="YlGnBu", annot=True, fmt="d", cbar_kws={'label': 'Order Volume'}, ax=ax)
    ax.set_title("Olist Peak Purchase Times: Order Volume by Day of Week x Hour of Day", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Hour of Day (0 - 23)", fontsize=11)
    ax.set_ylabel("Day of Week", fontsize=11)
    
    fig.tight_layout()
    chart_path = os.path.join(FR4_DIR, "peak_times_heatmap.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    
    log(f"Saved peak purchase times heatmap to '{chart_path}'")
    return pivot_vol


# ==============================================================================
# PART A4: REUSABLE CUSTOMER INSIGHTS FUNCTION
# ==============================================================================
def get_customer_insights(state=None, segment=None, db_path=DB_PATH):
    """
    Returns purchase frequency, AOV, repeat-purchase rate, and revenue summary
    filtered by customer_state and/or RFM segment.
    
    Parameters:
        state (str): Customer state code filter (e.g. 'SP', 'RJ')
        segment (str): RFM segment name filter (e.g. 'Champions', 'At Risk')
        db_path (str): Path to SQLite database file
        
    Returns:
        dict: Summary metrics dictionary containing:
            - total_customers
            - repeat_customers
            - repeat_purchase_rate
            - total_orders
            - total_spend
            - average_order_value
            - filtered_df (pd.DataFrame)
    """
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT 
        c.customer_unique_id,
        MAX(c.customer_state) AS customer_state,
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(op.order_payment) AS total_spend,
        MIN(o.order_purchase_timestamp) AS first_purchase,
        MAX(o.order_purchase_timestamp) AS last_purchase
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN (
        SELECT order_id, SUM(payment_value) AS order_payment
        FROM order_payments
        GROUP BY order_id
    ) op ON o.order_id = op.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
      AND o.order_purchase_timestamp IS NOT NULL
    GROUP BY c.customer_unique_id;
    """
    df_cust = pd.read_sql_query(query, conn)
    conn.close()
    
    # Recency & RFM Scoring
    max_date = pd.to_datetime(df_cust["last_purchase"]).max()
    df_cust["recency_days"] = (max_date - pd.to_datetime(df_cust["last_purchase"])).dt.total_seconds() / (24 * 3600)
    
    df_cust["R_score"] = pd.qcut(df_cust["recency_days"].rank(method="first", ascending=True), q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    df_cust["F_score"] = pd.qcut(df_cust["total_orders"].rank(method="first", ascending=True), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    df_cust["M_score"] = pd.qcut(df_cust["total_spend"].rank(method="first", ascending=True), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    df_cust["rfm_segment"] = df_cust.apply(assign_rfm_segment, axis=1)
    
    # Filtering
    filtered_df = df_cust.copy()
    if state and state != "All":
        filtered_df = filtered_df[filtered_df["customer_state"] == state]
    if segment and segment != "All":
        filtered_df = filtered_df[filtered_df["rfm_segment"] == segment]
        
    total_cust = len(filtered_df)
    if total_cust == 0:
        return {
            "total_customers": 0,
            "repeat_customers": 0,
            "repeat_purchase_rate": 0.0,
            "total_orders": 0,
            "total_spend": 0.0,
            "average_order_value": 0.0,
            "filtered_df": filtered_df
        }
        
    repeat_cust = (filtered_df["total_orders"] > 1).sum()
    repeat_rate = (repeat_cust / total_cust) * 100
    tot_orders = filtered_df["total_orders"].sum()
    tot_spend = filtered_df["total_spend"].sum()
    aov = tot_spend / tot_orders if tot_orders > 0 else 0.0
    
    return {
        "total_customers": total_cust,
        "repeat_customers": repeat_cust,
        "repeat_purchase_rate": round(repeat_rate, 2),
        "total_orders": tot_orders,
        "total_spend": round(tot_spend, 2),
        "average_order_value": round(aov, 2),
        "filtered_df": filtered_df
    }


def main():
    log("Running FR-4 Customer Buying Pattern Analysis...")
    df_cust, repeat_rate, overall_aov = run_customer_purchase_summary()
    df_cust, rfm_summary = run_rfm_segmentation(df_cust)
    run_peak_purchase_times()
    
    # Test get_customer_insights
    insights_sp_champions = get_customer_insights(state="SP", segment="Champions")
    log(f"Verification call get_customer_insights(state='SP', segment='Champions'): {insights_sp_champions['total_customers']} customers, AOV R$ {insights_sp_champions['average_order_value']:.2f}")
    
    log("FR-4 COMPLETED SUCCESSFULLY! All deliverables saved to 'fr4_customers/'.")


if __name__ == "__main__":
    main()
