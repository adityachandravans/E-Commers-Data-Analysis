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

print("Total Unique Customers:", len(df))
repeat_count = (df["total_orders"] > 1).sum()
repeat_rate = (repeat_count / len(df)) * 100
total_spend_all = df["total_spend"].sum()
total_orders_all = df["total_orders"].sum()
overall_aov = total_spend_all / total_orders_all

print(f"Repeat Customers (>1 order): {repeat_count:,}")
print(f"Repeat Purchase Rate: {repeat_rate:.2f}%")
print(f"Overall AOV (Total Spend / Total Orders): R$ {overall_aov:.2f}")
print("Order distribution count:")
print(df["total_orders"].value_counts().sort_index())

# Max date in dataset
max_date = pd.to_datetime(df["last_purchase"]).max()
print("Max Purchase Date in Dataset:", max_date)

df["last_purchase_dt"] = pd.to_datetime(df["last_purchase"])
df["recency_days"] = (max_date - df["last_purchase_dt"]).dt.total_seconds() / (24 * 3600)
df["recency_days"] = df["recency_days"].round(1)

print("\nRecency summary:")
print(df["recency_days"].describe())

conn.close()
