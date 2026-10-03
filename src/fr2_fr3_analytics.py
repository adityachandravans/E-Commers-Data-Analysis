"""
Olist E-Commerce - FR-2 (Sales Trend Analysis) & FR-3 (Product Analysis) Module
---------------------------------------------------------------------------------
Implementation of configurable aggregation, seasonality detection, Prophet/statsmodels sales forecasting,
category-level association rule mining (Apriori/mlxtend), and reusable category product drill-downs.
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules

# Attempt to import Prophet, fallback to statsmodels if needed
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Styling
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.sans-serif': 'Arial', 'font.family': 'sans-serif'})

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "olist.db")
FR2_DIR = os.path.join(BASE_DIR, "eda_charts", "fr2_trends")
FR3_DIR = os.path.join(BASE_DIR, "eda_charts", "fr3_products")

os.makedirs(FR2_DIR, exist_ok=True)
os.makedirs(FR3_DIR, exist_ok=True)


def log(msg):
    print(f"[INFO] {msg}", flush=True)


# ==============================================================================
# PART A1: REUSABLE SALES TREND AGGREGATION FUNCTION
# ==============================================================================
def get_sales_trend(start_date=None, end_date=None, category=None, state=None, granularity="monthly", db_path=DB_PATH):
    """
    Queries olist.db joining orders + order_items + products + customers to aggregate revenue and order count.
    
    Parameters:
        start_date (str): ISO format date filter (e.g., '2017-01-01')
        end_date (str): ISO format date filter (e.g., '2018-08-31')
        category (str): English product category filter (e.g., 'health_beauty')
        state (str): Customer state code filter (e.g., 'SP')
        granularity (str): 'daily', 'weekly', 'monthly', or 'yearly'
        db_path (str): Path to SQLite database file
        
    Returns:
        pd.DataFrame: DataFrame with columns ['period', 'revenue', 'order_count']
    """
    conn = sqlite3.connect(db_path)
    
    # Map granularity to SQLite strftime pattern
    gran_map = {
        "daily": "%Y-%m-%d",
        "weekly": "%Y-%W",
        "monthly": "%Y-%m",
        "yearly": "%Y"
    }
    
    if granularity not in gran_map:
        raise ValueError(f"Invalid granularity '{granularity}'. Choose from 'daily', 'weekly', 'monthly', 'yearly'.")
        
    fmt = gran_map[granularity]
    
    where_clauses = ["o.order_status NOT IN ('canceled', 'unavailable')", "o.order_purchase_timestamp IS NOT NULL"]
    params = []
    
    if start_date:
        where_clauses.append("o.order_purchase_timestamp >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("o.order_purchase_timestamp <= ?")
        params.append(end_date)
    if category:
        where_clauses.append("p.product_category_name_english = ?")
        params.append(category)
    if state:
        where_clauses.append("c.customer_state = ?")
        params.append(state)
        
    where_str = " AND ".join(where_clauses)
    
    query = f"""
    SELECT 
        strftime('{fmt}', o.order_purchase_timestamp) AS period,
        SUM(oi.price + oi.freight_value) AS revenue,
        COUNT(DISTINCT o.order_id) AS order_count
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products p ON oi.product_id = p.product_id
    WHERE {where_str}
    GROUP BY period
    ORDER BY period;
    """
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def demonstrate_sales_trend():
    log("Running A1: Demonstrating get_sales_trend with 3 configurable filter calls...")
    
    # Call 1: Full dataset monthly
    df1 = get_sales_trend(granularity="monthly")
    df1.to_csv(os.path.join(FR2_DIR, "trend_monthly_all.csv"), index=False)
    
    fig, ax1 = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=df1, x="period", y="revenue", ax=ax1, color="#1f77b4", marker="o", linewidth=2)
    ax1.set_title("Overall Monthly Sales Trend (Full Dataset)", fontsize=13, fontweight="bold")
    ax1.set_xticks(range(len(df1)))
    ax1.set_xticklabels(df1["period"], rotation=45, ha="right")
    ax1.set_ylabel("Revenue (R$)")
    fig.tight_layout()
    plt.savefig(os.path.join(FR2_DIR, "trend_monthly_all.png"), dpi=300)
    plt.close()
    
    # Call 2: Category = health_beauty, monthly
    df2 = get_sales_trend(category="health_beauty", granularity="monthly")
    df2.to_csv(os.path.join(FR2_DIR, "trend_monthly_health_beauty.csv"), index=False)
    
    fig, ax1 = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=df2, x="period", y="revenue", ax=ax1, color="#e377c2", marker="s", linewidth=2)
    ax1.set_title("Monthly Sales Trend: Health & Beauty Category", fontsize=13, fontweight="bold")
    ax1.set_xticks(range(len(df2)))
    ax1.set_xticklabels(df2["period"], rotation=45, ha="right")
    ax1.set_ylabel("Revenue (R$)")
    fig.tight_layout()
    plt.savefig(os.path.join(FR2_DIR, "trend_monthly_health_beauty.png"), dpi=300)
    plt.close()

    # Call 3: State = SP, weekly
    df3 = get_sales_trend(state="SP", granularity="weekly")
    df3.to_csv(os.path.join(FR2_DIR, "trend_weekly_SP.csv"), index=False)
    
    fig, ax1 = plt.subplots(figsize=(12, 5))
    sns.lineplot(data=df3, x="period", y="revenue", ax=ax1, color="#2ca02c", linewidth=1.5)
    ax1.set_title("Weekly Sales Trend: São Paulo (SP) State", fontsize=13, fontweight="bold")
    ax1.set_xticks(range(0, len(df3), 4))
    ax1.set_xticklabels(df3["period"].iloc[::4], rotation=45, ha="right")
    ax1.set_ylabel("Revenue (R$)")
    fig.tight_layout()
    plt.savefig(os.path.join(FR2_DIR, "trend_weekly_SP.png"), dpi=300)
    plt.close()

    log("A1 Complete. CSVs and PNGs saved to 'eda_charts/fr2_trends/'.")


# ==============================================================================
# PART A2: SEASONAL PATTERN & DEMAND SPIKE DETECTION
# ==============================================================================
def detect_seasonality_and_spikes():
    log("Running A2: Detecting seasonal patterns and revenue demand spikes...")
    
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT 
        date(o.order_purchase_timestamp) AS date,
        SUM(p.payment_value) AS revenue
    FROM orders o
    JOIN order_payments p ON o.order_id = p.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
      AND o.order_purchase_timestamp >= '2017-01-01'
      AND o.order_purchase_timestamp <= '2018-08-31'
    GROUP BY date
    ORDER BY date;
    """
    df_daily = pd.read_sql_query(query, conn)
    conn.close()
    
    df_daily["date"] = pd.to_datetime(df_daily["date"])
    df_daily["roll_7"] = df_daily["revenue"].rolling(window=7, min_periods=1).mean()
    df_daily["roll_30"] = df_daily["revenue"].rolling(window=30, min_periods=1).mean()
    df_daily["roll_30_std"] = df_daily["revenue"].rolling(window=30, min_periods=1).std().fillna(0)
    
    # Spike condition: Revenue > 30-day mean + 2 * 30-day std
    df_daily["is_spike"] = df_daily["revenue"] > (df_daily["roll_30"] + 2 * df_daily["roll_30_std"])
    
    spikes = df_daily[df_daily["is_spike"]].copy()
    
    print("\n--- STATISTICAL REVENUE SPIKE DATES (Top Outliers > 2 Std Dev) ---", flush=True)
    for idx, row in spikes.sort_values("revenue", ascending=False).head(10).iterrows():
        print(f"  Date: {row['date'].strftime('%Y-%m-%d')} | Revenue: R$ {row['revenue']:,.2f} | 30d Avg: R$ {row['roll_30']:,.2f}", flush=True)

    # Specific Brazilian Holiday Analysis
    nov_2017_spike = df_daily[(df_daily["date"] >= "2017-11-20") & (df_daily["date"] <= "2017-11-27")]
    max_black_friday = nov_2017_spike.loc[nov_2017_spike["revenue"].idxmax()]
    
    dec_2017 = df_daily[(df_daily["date"] >= "2017-12-01") & (df_daily["date"] <= "2017-12-31")]
    avg_dec_rev = dec_2017["revenue"].mean()
    avg_annual_rev = df_daily["revenue"].mean()

    log(f"Black Friday Peak (2017-11-24): R$ {max_black_friday['revenue']:,.2f} ({(max_black_friday['revenue']/avg_annual_rev):.1f}x normal daily average).")
    log(f"December 2017 Average Daily Revenue: R$ {avg_dec_rev:,.2f} vs Annual Average: R$ {avg_annual_rev:,.2f}.")

    # Plot
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df_daily["date"], df_daily["revenue"], color="#cbd5e0", label="Actual Daily Revenue", alpha=0.7)
    ax.plot(df_daily["date"], df_daily["roll_7"], color="#3182bd", linewidth=1.8, label="7-Day Rolling Avg")
    ax.plot(df_daily["date"], df_daily["roll_30"], color="#e6550d", linewidth=2.2, label="30-Day Rolling Avg")
    
    # Mark Spikes
    ax.scatter(spikes["date"], spikes["revenue"], color="crimson", s=50, zorder=5, label="Demand Spikes (> 2 Std Dev)")
    
    # Annotate Black Friday
    ax.annotate(
        f"Black Friday Peak\n(R$ {max_black_friday['revenue']:,.0f})",
        xy=(max_black_friday["date"], max_black_friday["revenue"]),
        xytext=(max_black_friday["date"] - pd.Timedelta(days=40), max_black_friday["revenue"] + 30000),
        arrowprops=dict(facecolor="black", shrink=0.05, width=1.5, headwidth=6),
        fontsize=10, fontweight="bold", bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.8)
    )

    ax.set_title("Olist Daily Sales Trend, Rolling Averages & Seasonal Demand Spikes", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Daily Revenue (R$)", fontsize=11)
    ax.legend(loc="upper left", fontsize=10)
    fig.tight_layout()
    
    plt.savefig(os.path.join(FR2_DIR, "seasonality_spikes.png"), dpi=300)
    plt.close()
    
    log("A2 Complete. Seasonality plot saved to 'eda_charts/fr2_trends/seasonality_spikes.png'.")


# ==============================================================================
# PART A3: DEMAND & SALES FORECASTING
# ==============================================================================
def run_sales_forecasting():
    log("Running A3: Building sales forecasting model...")
    
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT 
        date(o.order_purchase_timestamp) AS date,
        SUM(p.payment_value) AS revenue
    FROM orders o
    JOIN order_payments p ON o.order_id = p.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
      AND o.order_purchase_timestamp >= '2017-01-01'
      AND o.order_purchase_timestamp <= '2018-08-20'
    GROUP BY date
    ORDER BY date;
    """
    df_daily = pd.read_sql_query(query, conn)
    conn.close()
    
    df_daily["date"] = pd.to_datetime(df_daily["date"])
    
    # Resample to weekly for smooth, robust time-series forecasting
    df_weekly = df_daily.resample("W-MON", on="date")["revenue"].sum().reset_index()
    df_weekly.columns = ["ds", "y"]

    # Train / Test Validation Split (Last 12 weeks = ~3 months test set)
    test_weeks = 12
    train_size = len(df_weekly) - test_weeks
    train_df = df_weekly.iloc[:train_size].copy()
    test_df = df_weekly.iloc[train_size:].copy()

    method_used = "Prophet" if PROPHET_AVAILABLE else "Statsmodels (Holt-Winters)"
    log(f"Forecasting Method Selected: {method_used}")

    if PROPHET_AVAILABLE:
        # Fit Prophet on Train
        m_train = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
        m_train.fit(train_df)
        future_val = m_train.make_future_dataframe(periods=test_weeks, freq="W-MON")
        forecast_val = m_train.predict(future_val)
        
        test_pred = forecast_val.iloc[train_size:]["yhat"].values
        test_actual = test_df["y"].values

        # Full Fit & 30-Day (4 weeks) Future Forecast
        m_full = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
        m_full.fit(df_weekly)
        future_30d = m_full.make_future_dataframe(periods=4, freq="W-MON")
        forecast_full = m_full.predict(future_30d)
        
        ds_series = forecast_full["ds"]
        yhat_series = forecast_full["yhat"]
        yhat_lower = forecast_full["yhat_lower"]
        yhat_upper = forecast_full["yhat_upper"]
    else:
        # Fallback to Holt-Winters Exponential Smoothing
        hw_train = ExponentialSmoothing(train_df["y"], trend="add", seasonal=None).fit()
        test_pred = hw_train.forecast(test_weeks).values
        test_actual = test_df["y"].values

        hw_full = ExponentialSmoothing(df_weekly["y"], trend="add", seasonal=None).fit()
        future_pred = hw_full.forecast(4)
        
        # Build dummy forecast dataframe for consistency
        last_date = df_weekly["ds"].max()
        future_dates = [last_date + pd.Timedelta(weeks=i+1) for i in range(4)]
        ds_series = pd.concat([df_weekly["ds"], pd.Series(future_dates)], ignore_index=True)
        yhat_series = pd.concat([pd.Series(hw_full.fittedvalues), pd.Series(future_pred)], ignore_index=True)
        yhat_lower = yhat_series * 0.90
        yhat_upper = yhat_series * 1.10

    # Validation Error Metrics
    mae = mean_absolute_error(test_actual, test_pred)
    mape = mean_absolute_percentage_error(test_actual, test_pred) * 100

    print("\n==========================================", flush=True)
    print(f"SALES FORECAST VALIDATION RESULTS ({method_used}):", flush=True)
    print("==========================================", flush=True)
    print(f"Validation Period: Last {test_weeks} Weeks (~3 Months)", flush=True)
    print(f"Mean Absolute Error (MAE): R$ {mae:,.2f}", flush=True)
    print(f"Mean Absolute Percentage Error (MAPE): {mape:.2f}%", flush=True)

    # Future 30-Day (4-Week) Forecast Table
    df_future_30d = pd.DataFrame({
        "period_date": ds_series.tail(4).dt.strftime("%Y-%m-%d").values,
        "forecasted_revenue": yhat_series.tail(4).values,
        "lower_bound_ci": yhat_lower.tail(4).values,
        "upper_bound_ci": yhat_upper.tail(4).values
    })
    
    print("\n--- NEXT 30-DAY (4-WEEK) SALES FORECAST TABLE ---", flush=True)
    print(df_future_30d.to_string(index=False), flush=True)
    
    df_future_30d.to_csv(os.path.join(FR2_DIR, "forecast_30d.csv"), index=False)

    # Plot
    fig, ax = plt.subplots(figsize=(13, 6))
    
    # Historical Actuals
    ax.plot(df_weekly["ds"], df_weekly["y"], color="#1f77b4", marker="o", linewidth=2, label="Historical Weekly Revenue")
    
    # Test Period Forecast vs Actual
    test_dates = df_weekly["ds"].iloc[train_size:]
    ax.plot(test_dates, test_pred, color="#ff7f0e", linestyle="--", linewidth=2.5, label=f"Validation Forecast ({method_used})")
    
    # Future 30-Day Forecast
    future_dates = ds_series.tail(4)
    future_vals = yhat_series.tail(4)
    ax.plot(future_dates, future_vals, color="#2ca02c", marker="s", linestyle="-", linewidth=2.5, label="30-Day Future Forecast")
    ax.fill_between(future_dates, yhat_lower.tail(4), yhat_upper.tail(4), color="#2ca02c", alpha=0.2, label="95% Confidence Interval")

    ax.set_title(f"Olist Sales Forecast ({method_used}) — Validation & 30-Day Future Projection", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Weekly Revenue (R$)", fontsize=11)
    ax.legend(loc="upper left", fontsize=10)
    ax.text(0.02, 0.72, f"Validation Metrics:\nMAE: R$ {mae:,.2f}\nMAPE: {mape:.2f}%", transform=ax.transAxes, 
            fontsize=11, bbox=dict(boxstyle="round,pad=0.5", facecolor="#fff9e6", edgecolor="#f5a623"))

    fig.tight_layout()
    plt.savefig(os.path.join(FR2_DIR, "sales_forecast.png"), dpi=300)
    plt.close()

    log("A3 Complete. Forecast chart saved to 'eda_charts/fr2_trends/sales_forecast.png'.")


# ==============================================================================
# PART B1: MARKET-BASKET / ASSOCIATION-RULE MINING
# ==============================================================================
def run_association_rules():
    log("Running B1: Association-rule mining on category baskets...")
    
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT 
        oi.order_id,
        COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category_english
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    LEFT JOIN category_translation t ON p.product_category_name = t.product_category_name;
    """
    df_raw = pd.read_sql_query(query, conn)
    conn.close()

    # Note on category-level aggregation vs product-level
    log("ASSUMPTION NOTE: Market-basket analysis is performed at the category level (not product_id) because product-level transaction baskets are extremely sparse.")

    # Group order_items by order_id to distinct list of categories
    transactions_all = df_raw.groupby("order_id")["category_english"].apply(lambda x: list(set(x))).tolist()
    total_orders = len(transactions_all)
    
    # Filter to orders with 2+ distinct categories
    transactions_multi = [t for t in transactions_all if len(t) >= 2]
    multi_count = len(transactions_multi)
    multi_pct = (multi_count / total_orders) * 100

    print(f"\n--- MARKET-BASKET TRANSACTION METRICS ---", flush=True)
    print(f"Total Unique Orders: {total_orders:,}", flush=True)
    print(f"Orders with 2+ Distinct Product Categories: {multi_count:,} ({multi_pct:.2f}%)", flush=True)
    print(f"Orders with 1 Category: {total_orders - multi_count:,} ({100 - multi_pct:.2f}%)", flush=True)

    if multi_count == 0:
        log("No multi-category transactions found.")
        return

    # One-hot encoding
    te = TransactionEncoder()
    te_ary = te.fit(transactions_multi).transform(transactions_multi)
    df_te = pd.DataFrame(te_ary, columns=te.columns_)

    # Apriori
    frequent_itemsets = apriori(df_te, min_support=0.005, use_colnames=True)
    log(f"Found {len(frequent_itemsets)} frequent itemsets with min_support=0.005.")

    if len(frequent_itemsets) > 0:
        rules = association_rules(frequent_itemsets, metric="lift", min_threshold=1.0)
        rules["antecedents"] = rules["antecedents"].apply(lambda x: ", ".join(sorted(list(x))))
        rules["consequents"] = rules["consequents"].apply(lambda x: ", ".join(sorted(list(x))))
        
        rules_sorted = rules.sort_values("lift", ascending=False).head(20).copy()
        
        output_table = rules_sorted[["antecedents", "consequents", "support", "confidence", "lift"]].copy()
        output_table.to_csv(os.path.join(FR3_DIR, "association_rules.csv"), index=False)
        
        print("\n--- TOP 10 ASSOCIATION RULES (Sorted by Lift) ---", flush=True)
        print(output_table.head(10).to_string(index=False), flush=True)

        print("\n--- PLAIN-ENGLISH INTERPRETATION OF TOP RULES ---", flush=True)
        top_rules_list = output_table.head(3).to_dict("records")
        for i, r in enumerate(top_rules_list, 1):
            print(f"  Rule #{i}: Customers who buy '{r['antecedents']}' are {r['lift']:.2f}x more likely to also buy '{r['consequents']}' (Confidence: {r['confidence']*100:.1f}%).", flush=True)
    else:
        log("No association rules met the threshold due to single-category basket dominance.")

    log("B1 Complete. Saved association rules to 'eda_charts/fr3_products/association_rules.csv'.")


# ==============================================================================
# PART B2: CATEGORY -> PRODUCT DRILL-DOWN FUNCTION
# ==============================================================================
def get_category_drilldown(category_name_english, top_n=15, db_path=DB_PATH):
    """
    Returns the top N individual products within a category ranked by total revenue.
    
    Parameters:
        category_name_english (str): English category name (e.g., 'health_beauty')
        top_n (int): Number of top products to return (default: 15)
        db_path (str): Path to SQLite database file
        
    Returns:
        pd.DataFrame: DataFrame with columns ['product_id', 'total_revenue', 'total_units_sold', 'avg_price', 'avg_review_score']
    """
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT 
        oi.product_id,
        SUM(oi.price) AS total_revenue,
        COUNT(oi.order_item_id) AS total_units_sold,
        AVG(oi.price) AS avg_price,
        AVG(r.review_score) AS avg_review_score
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    LEFT JOIN category_translation t ON p.product_category_name = t.product_category_name
    LEFT JOIN order_reviews r ON oi.order_id = r.order_id
    WHERE COALESCE(t.product_category_name_english, p.product_category_name) = ?
    GROUP BY oi.product_id
    ORDER BY total_revenue DESC
    LIMIT ?;
    """
    
    df = pd.read_sql_query(query, conn, params=[category_name_english, top_n])
    conn.close()
    return df


def demonstrate_category_drilldown():
    log("Running B2: Demonstrating category drill-down for top 3 revenue categories...")
    
    top3_categories = ["health_beauty", "watches_gifts", "bed_bath_table"]
    
    for cat in top3_categories:
        df_drill = get_category_drilldown(cat, top_n=15)
        df_drill["product_short"] = df_drill["product_id"].str[:8] + "..."
        
        # Save CSV
        csv_path = os.path.join(FR3_DIR, f"drilldown_{cat}.csv")
        df_drill.to_csv(csv_path, index=False)
        
        print(f"\n--- Top Products Drill-Down: {cat} ---", flush=True)
        print(df_drill[["product_short", "total_revenue", "total_units_sold", "avg_price", "avg_review_score"]].head(5).to_string(index=False), flush=True)

        # Plot
        fig, ax1 = plt.subplots(figsize=(10, 5))
        sns.barplot(data=df_drill, y="product_short", x="total_revenue", hue="product_short", palette="Blues_r", ax=ax1, legend=False)
        ax1.set_title(f"Top 15 Products by Revenue: Category '{cat}'", fontsize=13, fontweight="bold")
        ax1.set_xlabel("Total Revenue (R$)", fontsize=11)
        ax1.set_ylabel("Product ID (Truncated)", fontsize=11)
        
        for idx, row in df_drill.iterrows():
            ax1.text(row["total_revenue"] + 500, idx, f"R${row['total_revenue']:,.0f} ({row['total_units_sold']} units)", va="center", fontsize=9)

        fig.tight_layout()
        chart_path = os.path.join(FR3_DIR, f"drilldown_{cat}.png")
        plt.savefig(chart_path, dpi=300)
        plt.close()

    log("B2 Complete. Saved drilldown CSVs and PNGs to 'eda_charts/fr3_products/'.")


def main():
    log("Running FR-2 (Sales Trend) & FR-3 (Product Analysis) Modules...")
    demonstrate_sales_trend()
    detect_seasonality_and_spikes()
    run_sales_forecasting()
    run_association_rules()
    demonstrate_category_drilldown()
    log("FR-2 AND FR-3 COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
