import sqlite3
import pandas as pd
import numpy as np

conn = sqlite3.connect("db/olist.db")

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

df = pd.read_sql_query(query, conn)
conn.close()

max_date = pd.to_datetime(df["last_purchase"]).max()
df["recency_days"] = (max_date - pd.to_datetime(df["last_purchase"])).dt.total_seconds() / (24 * 3600)

# Quintile scoring using pandas qcut + rank for tie-breaking
# Recency: lower recency days = higher score 5
df["R_score"] = pd.qcut(df["recency_days"].rank(method="first", ascending=True), q=5, labels=[5, 4, 3, 2, 1]).astype(int)

# Frequency: higher total_orders = higher score 5
df["F_score"] = pd.qcut(df["total_orders"].rank(method="first", ascending=True), q=5, labels=[1, 2, 3, 4, 5]).astype(int)

# Monetary: higher total_spend = higher score 5
df["M_score"] = pd.qcut(df["total_spend"].rank(method="first", ascending=True), q=5, labels=[1, 2, 3, 4, 5]).astype(int)

print("Score Distributions:")
print("R score:\n", df["R_score"].value_counts().sort_index())
print("F score:\n", df["F_score"].value_counts().sort_index())
print("M score:\n", df["M_score"].value_counts().sort_index())

# Segment mapping rules:
def assign_segment(row):
    r, f, m = row["R_score"], row["F_score"], row["M_score"]
    
    # Champions: High R, F, M
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    # Loyal Customers: High F & M, moderate-to-high R
    elif f >= 4 and m >= 3:
        return "Loyal Customers"
    # Potential Loyalists: Recent buyers with decent spend/freq
    elif r >= 4 and (f >= 3 or m >= 3):
        return "Potential Loyalists"
    # New Customers: Recent buyers, lower freq/spend
    elif r >= 4:
        return "New Customers"
    # At Risk: Low R, but were frequent/high spenders
    elif r <= 2 and (f >= 4 or m >= 4):
        return "At Risk"
    # Hibernating: Low R, moderate F/M
    elif r <= 2 and (f >= 2 or m >= 2):
        return "Hibernating"
    # Lost: Lowest R, lowest F, lowest M
    elif r <= 2:
        return "Lost"
    # Promising / About to Sleep: Middle R (3)
    else:
        return "Promising"

df["rfm_segment"] = df.apply(assign_segment, axis=1)

summary = df.groupby("rfm_segment").agg(
    customer_count=("customer_unique_id", "count"),
    total_revenue=("total_spend", "sum"),
    avg_spend=("total_spend", "mean"),
    avg_orders=("total_orders", "mean"),
    avg_recency=("recency_days", "mean")
).reset_index()

summary["customer_pct"] = (summary["customer_count"] / len(df)) * 100
summary["revenue_pct"] = (summary["total_revenue"] / df["total_spend"].sum()) * 100
summary = summary.sort_values("total_revenue", ascending=False)

print("\n--- RFM SEGMENT SUMMARY ---")
print(summary.to_string(index=False))
