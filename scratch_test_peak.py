import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

conn = sqlite3.connect("db/olist.db")

query = """
SELECT 
    o.order_id,
    c.customer_unique_id,
    c.customer_state,
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

# Order days in standard Monday-Sunday order
days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

pivot_vol = df_orders.pivot_table(index="day_of_week", columns="hour", values="order_id", aggfunc="count", fill_value=0)
pivot_vol = pivot_vol.reindex(days_order)

print("Peak purchase volume by day-of-week x hour-of-day pivot sample:")
print(pivot_vol.iloc[:, :6])

# Peak hour overall
peak_day_hour = df_orders.groupby(["day_of_week", "hour"]).size().idxmax()
print("\nPeak Volume Slot:", peak_day_hour)
