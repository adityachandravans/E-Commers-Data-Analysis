"""
Olist E-Commerce Data Analytics Platform — Interactive Streamlit Dashboard
-------------------------------------------------------------------------
IEEE 830 SRS Compliant Web Application integrating FR-1 through FR-4 analysis:
- Sales Trend & Forecasting (FR-2)
- Product & Association Analysis (FR-3)
- Customer Buying Patterns & RFM Segmentation (FR-4)
- Live Filtering, Interactive Visualizations, CSV & PDF Export (FR-5)

Run via terminal:
    streamlit run dashboard.py
"""

import os
import sys
import io
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Add project root directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from src.fr2_fr3_analytics import get_sales_trend, get_category_drilldown
from src.fr4_analytics import get_customer_insights

DB_PATH = os.path.join(BASE_DIR, "db", "olist.db")
FR2_DIR = os.path.join(BASE_DIR, "eda_charts", "fr2_trends")
FR3_DIR = os.path.join(BASE_DIR, "eda_charts", "fr3_products")
FR4_DIR = os.path.join(BASE_DIR, "fr4_customers")

# Streamlit Page Config
st.set_page_config(
    page_title="Olist Analytics Platform",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-box {
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1E3A8A;
    }
    </style>
""", unsafe_allow_html=True)


# ==============================================================================
# CACHED DATABASE HELPER FUNCTIONS
# ==============================================================================
@st.cache_data
def load_filter_options():
    conn = sqlite3.connect(DB_PATH)
    states = pd.read_sql_query("SELECT DISTINCT customer_state FROM customers ORDER BY customer_state;", conn)["customer_state"].tolist()
    categories = pd.read_sql_query("""
        SELECT DISTINCT product_category_name_english 
        FROM products 
        WHERE product_category_name_english IS NOT NULL 
        ORDER BY product_category_name_english;
    """, conn)["product_category_name_english"].tolist()
    conn.close()
    return states, categories


@st.cache_data
def load_rfm_summary_data():
    csv_path = os.path.join(FR4_DIR, "rfm_summary.csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    return pd.DataFrame()


@st.cache_data
def load_association_rules():
    csv_path = os.path.join(FR3_DIR, "association_rules.csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    return pd.DataFrame()


@st.cache_data
def load_forecast_data():
    csv_path = os.path.join(FR2_DIR, "forecast_30d.csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    return pd.DataFrame()


# ==============================================================================
# PDF REPORT GENERATOR (REPORTLAB)
# ==============================================================================
def generate_pdf_summary_report(start_date=None, end_date=None, selected_state="All", selected_category="All"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=6
    )
    story.append(Paragraph("Olist E-Commerce Executive Summary Report", title_style))
    
    sub_style = ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#4B5563'), spaceAfter=12)
    story.append(Paragraph(f"Generated automatically from Olist Analytics Platform | Filters: State={selected_state}, Category={selected_category}", sub_style))
    story.append(Spacer(1, 10))

    # Fetch Headline Metrics
    insights = get_customer_insights(state=selected_state if selected_state != "All" else None)
    
    body_style = styles['BodyText']
    story.append(Paragraph("<b>1. Key Headline Business Metrics</b>", styles['Heading2']))
    story.append(Spacer(1, 6))

    metric_data = [
        ["KPI Metric", "Value"],
        ["Total Unique Customers", f"{insights['total_customers']:,}"],
        ["Total Revenue", f"R$ {insights['total_spend']:,.2f}"],
        ["Total Orders Placed", f"{insights['total_orders']:,}"],
        ["Average Order Value (AOV)", f"R$ {insights['average_order_value']:.2f}"],
        ["Repeat Purchase Rate", f"{insights['repeat_purchase_rate']:.2f}%"]
    ]

    t = Table(metric_data, colWidths=[240, 240])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # Executive Summary Text
    story.append(Paragraph("<b>2. Executive Summary & Findings</b>", styles['Heading2']))
    exec_summary_text = (
        "<b>Customer Retention:</b> Overall customer repeat purchase rate is <b>3.04%</b>, with 96.96% of buyers "
        "placing a single transaction. This indicates an acquisition-driven model where growth relies on top-of-funnel customer acquisition.<br/><br/>"
        "<b>RFM Segmentation:</b> The 'Potential Loyalists' segment drives the largest share of gross revenue (R$ 3.74M, 23.7%), "
        "followed closely by 'Loyal Customers' (R$ 3.65M, 23.2%) and 'At Risk' (R$ 3.04M, 19.3%).<br/><br/>"
        "<b>Peak Shopping Hours:</b> Peak order volume occurs on weekday afternoons, with maximum order density recorded on "
        "<b>Tuesdays at 14:00 (2:00 PM)</b>."
    )
    story.append(Paragraph(exec_summary_text, body_style))
    story.append(Spacer(1, 15))

    # Add Chart Images if available
    story.append(Paragraph("<b>3. Visual Analytics Snapshots</b>", styles['Heading2']))
    story.append(Spacer(1, 6))

    rfm_chart = os.path.join(FR4_DIR, "rfm_revenue.png")
    if os.path.exists(rfm_chart):
        story.append(Paragraph("<b>Figure 1: Revenue Contributed by RFM Segment</b>", body_style))
        story.append(Spacer(1, 4))
        story.append(Image(rfm_chart, width=480, height=220))
        story.append(Spacer(1, 10))

    peak_chart = os.path.join(FR4_DIR, "peak_times_heatmap.png")
    if os.path.exists(peak_chart):
        story.append(Paragraph("<b>Figure 2: Peak Purchase Times Heatmap</b>", body_style))
        story.append(Spacer(1, 4))
        story.append(Image(peak_chart, width=480, height=210))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ==============================================================================
# MAIN APP LAYOUT
# ==============================================================================
def main():
    st.markdown('<div class="main-header">Olist E-Commerce Data Analytics Platform</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Interactive IEEE 830 Analytics Dashboard: Sales Trends, Product Baskets & Customer Retention</div>', unsafe_allow_html=True)

    states, categories = load_filter_options()

    # --------------------------------------------------------------------------
    # SIDEBAR: GLOBAL FILTERS
    # --------------------------------------------------------------------------
    st.sidebar.header("🔍 Global Filter Controls")
    
    # Date Range Filter
    date_range = st.sidebar.date_input(
        "Order Purchase Date Range",
        value=(pd.to_datetime("2016-09-01"), pd.to_datetime("2018-10-31")),
        min_value=pd.to_datetime("2016-09-01"),
        max_value=pd.to_datetime("2018-10-31")
    )
    start_date_str = date_range[0].strftime("%Y-%m-%d") if len(date_range) > 0 else None
    end_date_str = date_range[1].strftime("%Y-%m-%d") if len(date_range) > 1 else None

    # State Filter
    selected_state = st.sidebar.selectbox("Customer State (UF)", ["All"] + states, index=0)
    state_filter = None if selected_state == "All" else selected_state

    # Category Filter
    selected_category = st.sidebar.selectbox("Product Category", ["All"] + categories, index=0)
    category_filter = None if selected_category == "All" else selected_category

    st.sidebar.markdown("---")
    st.sidebar.info("💡 **Tip:** Use the top tabs to navigate between Sales Trends, Product Baskets, Customer Segments, and Report Generation.")

    # --------------------------------------------------------------------------
    # TABS NAVIGATION
    # --------------------------------------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Sales Trends (FR-2)", 
        "📦 Product Insights (FR-3)", 
        "👥 Customer Insights (FR-4)", 
        "📄 Reports & Export (FR-5)"
    ])

    # ==========================================================================
    # TAB 1: SALES TRENDS (FR-2)
    # ==========================================================================
    with tab1:
        st.subheader("Sales Trend & Demand Forecasting Analysis")

        col1, col2, col3 = st.columns(3)
        granularity = col1.selectbox("Time Granularity", ["monthly", "weekly", "daily"], index=0)

        # Fetch Live Sales Trend Data
        df_trend = get_sales_trend(
            start_date=start_date_str,
            end_date=end_date_str,
            category=category_filter,
            state=state_filter,
            granularity=granularity
        )

        tot_rev = df_trend["revenue"].sum() if not df_trend.empty else 0.0
        tot_ord = df_trend["order_count"].sum() if not df_trend.empty else 0
        avg_aov = tot_rev / tot_ord if tot_ord > 0 else 0.0

        col1.metric("Filtered Total Revenue", f"R$ {tot_rev:,.2f}")
        col2.metric("Filtered Order Volume", f"{tot_ord:,}")
        col3.metric("Average Order Value (AOV)", f"R$ {avg_aov:.2f}")

        st.markdown("---")
        st.write(f"### Live Sales Trend ({granularity.capitalize()} Aggregation)")

        if not df_trend.empty:
            fig, ax1 = plt.subplots(figsize=(12, 5))
            ax2 = ax1.twinx()
            
            sns.lineplot(data=df_trend, x="period", y="revenue", ax=ax1, color="#1E3A8A", marker="o", linewidth=2.5, label="Revenue (R$)")
            sns.barplot(data=df_trend, x="period", y="order_count", ax=ax2, color="#93C5FD", alpha=0.35, label="Order Count")
            
            ax1.set_title(f"Revenue & Order Count Trend ({granularity.capitalize()})", fontsize=13, fontweight="bold")
            ax1.set_xlabel("Time Period", fontsize=11)
            ax1.set_ylabel("Revenue (R$)", fontsize=11, color="#1E3A8A")
            ax2.set_ylabel("Order Count", fontsize=11, color="#2563EB")
            
            # Subsample x-ticks if too crowded
            if len(df_trend) > 20:
                step = len(df_trend) // 15
                ax1.set_xticks(range(0, len(df_trend), step))
                ax1.set_xticklabels(df_trend["period"].iloc[::step], rotation=45, ha="right")
            else:
                ax1.set_xticks(range(len(df_trend)))
                ax1.set_xticklabels(df_trend["period"], rotation=45, ha="right")
                
            fig.tight_layout()
            st.pyplot(fig)
            plt.close()
        else:
            st.warning("No sales data available for the selected filter combination.")

        st.markdown("---")
        col_a, col_b = st.columns(2)

        with col_a:
            st.write("### Seasonal Demand Spikes & Outliers")
            spike_img_path = os.path.join(FR2_DIR, "seasonality_spikes.png")
            if os.path.exists(spike_img_path):
                st.image(spike_img_path, use_container_width=True)
            else:
                st.info("Run master pipeline to generate seasonality spike chart.")

        with col_b:
            st.write("### 30-Day Revenue Forecast")
            forecast_img_path = os.path.join(FR2_DIR, "sales_forecast.png")
            if os.path.exists(forecast_img_path):
                st.image(forecast_img_path, use_container_width=True)
            else:
                st.info("Run master pipeline to generate 30-day sales forecast chart.")

        with st.expander("📌 View 30-Day Forecast Numerical Projection Table"):
            df_forecast = load_forecast_data()
            if not df_forecast.empty:
                st.dataframe(df_forecast, use_container_width=True)

    # ==========================================================================
    # TAB 2: PRODUCT INSIGHTS (FR-3)
    # ==========================================================================
    with tab2:
        st.subheader("Product Performance & Market-Basket Association Rules")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Active Categories", f"{len(categories):,}")
        c2.metric("Top Revenue Category", "health_beauty (R$ 1.26M)")
        c3.metric("Top Association Rule Lift", "34.5x (art & decor items)")

        st.markdown("---")
        st.write("### Category Product Drill-Down")
        
        selected_drill_cat = st.selectbox(
            "Select Product Category to Drill-Down",
            options=categories,
            index=categories.index("health_beauty") if "health_beauty" in categories else 0
        )

        df_drill = get_category_drilldown(selected_drill_cat, top_n=15)
        
        if not df_drill.empty:
            col_chart, col_table = st.columns([1, 1])
            
            with col_chart:
                df_drill["product_short"] = df_drill["product_id"].str[:8] + "..."
                fig, ax = plt.subplots(figsize=(8, 5))
                sns.barplot(data=df_drill, y="product_short", x="total_revenue", palette="Blues_r", ax=ax, hue="product_short", legend=False)
                ax.set_title(f"Top 15 Products by Revenue: '{selected_drill_cat}'", fontsize=12, fontweight="bold")
                ax.set_xlabel("Total Revenue (R$)", fontsize=10)
                ax.set_ylabel("Product ID", fontsize=10)
                fig.tight_layout()
                st.pyplot(fig)
                plt.close()
                
            with col_table:
                st.write(f"#### Product Performance Table ('{selected_drill_cat}')")
                st.dataframe(df_drill[["product_id", "total_revenue", "total_units_sold", "avg_price", "avg_review_score"]], height=380, use_container_width=True)
        else:
            st.info("No product data available for this category.")

        st.markdown("---")
        st.write("### Frequently Bought Together — Market-Basket Association Rules")
        df_rules = load_association_rules()
        if not df_rules.empty:
            st.dataframe(df_rules.head(10), use_container_width=True)
            st.caption("Association rules calculated using Apriori algorithm on multi-category customer baskets with minimum lift > 1.0.")
        else:
            st.info("Run master pipeline to generate market-basket association rules.")

    # ==========================================================================
    # TAB 3: CUSTOMER INSIGHTS (FR-4)
    # ==========================================================================
    with tab3:
        st.subheader("Customer Buying Pattern Analysis & RFM Segmentation")

        # Fetch Customer Insights filtered by active sidebar selections
        st.markdown("#### Filtered Customer Key Performance Indicators")
        
        c_seg_filter = st.selectbox("Filter Customer View by RFM Segment", ["All", "Champions", "Loyal Customers", "Potential Loyalists", "New Customers", "Promising", "At Risk", "Hibernating", "Lost"], index=0)
        
        seg_filter_val = None if c_seg_filter == "All" else c_seg_filter
        
        insights = get_customer_insights(state=state_filter, segment=seg_filter_val)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Filtered Unique Customers", f"{insights['total_customers']:,}")
        m2.metric("Repeat Purchase Rate", f"{insights['repeat_purchase_rate']:.2f}%")
        m3.metric("Average Order Value (AOV)", f"R$ {insights['average_order_value']:.2f}")
        m4.metric("Total Spend (Revenue)", f"R$ {insights['total_spend']:,.2f}")

        st.markdown("---")
        st.write("### RFM Customer Segment Breakdown (Recency, Frequency, Monetary)")

        col_rfm1, col_rfm2 = st.columns(2)

        with col_rfm1:
            rfm_cnt_img = os.path.join(FR4_DIR, "rfm_customer_count.png")
            if os.path.exists(rfm_cnt_img):
                st.image(rfm_cnt_img, use_container_width=True)

        with col_rfm2:
            rfm_rev_img = os.path.join(FR4_DIR, "rfm_revenue.png")
            if os.path.exists(rfm_rev_img):
                st.image(rfm_rev_img, use_container_width=True)

        st.markdown("#### RFM Segment Revenue & Engagement Summary Table")
        df_rfm_summary = load_rfm_summary_data()
        if not df_rfm_summary.empty:
            st.dataframe(df_rfm_summary, use_container_width=True)

        st.markdown("---")
        st.write("### Peak Purchase Times Heatmap")
        peak_img_path = os.path.join(FR4_DIR, "peak_times_heatmap.png")
        if os.path.exists(peak_img_path):
            st.image(peak_img_path, use_container_width=True)
            st.caption("Order volume density across days of the week and hours of the day (Peak: Tuesday 14:00).")

    # ==========================================================================
    # TAB 4: REPORTS & EXPORT (FR-5.3)
    # ==========================================================================
    with tab4:
        st.subheader("Data Export & Automated Report Generation")

        col_exp1, col_exp2 = st.columns(2)

        with col_exp1:
            st.markdown("### 📊 Export Filtered Datasets (CSV)")
            st.write("Download the underlying dataset driving the active dashboard view for custom reporting or offline analysis.")

            dataset_option = st.selectbox(
                "Select Dataset to Export",
                ["Sales Trends Data", "Category Drill-Down Data", "RFM Customer Segmentation Data", "RFM Summary Table"]
            )

            if dataset_option == "Sales Trends Data":
                export_df = get_sales_trend(start_date=start_date_str, end_date=end_date_str, category=category_filter, state=state_filter, granularity="monthly")
                file_name = "filtered_sales_trends.csv"
            elif dataset_option == "Category Drill-Down Data":
                cat_to_export = category_filter if category_filter else "health_beauty"
                export_df = get_category_drilldown(cat_to_export, top_n=50)
                file_name = f"drilldown_{cat_to_export}.csv"
            elif dataset_option == "RFM Customer Segmentation Data":
                rfm_csv_path = os.path.join(FR4_DIR, "rfm_segments.csv")
                export_df = pd.read_csv(rfm_csv_path) if os.path.exists(rfm_csv_path) else pd.DataFrame()
                file_name = "rfm_customer_segments.csv"
            else:
                export_df = load_rfm_summary_data()
                file_name = "rfm_summary_report.csv"

            if not export_df.empty:
                csv_bytes = export_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"📥 Download {dataset_option} (CSV)",
                    data=csv_bytes,
                    file_name=file_name,
                    mime="text/csv"
                )
            else:
                st.info("Selected dataset is empty.")

        with col_exp2:
            st.markdown("### 📄 Generate PDF Executive Summary")
            st.write("Generate a publication-ready PDF document containing key KPI tiles, executive findings, and high-resolution chart snapshots.")

            if st.button("🚀 Generate PDF Report"):
                pdf_buffer = generate_pdf_summary_report(
                    start_date=start_date_str,
                    end_date=end_date_str,
                    selected_state=selected_state,
                    selected_category=selected_category
                )

                st.download_button(
                    label="📥 Download Executive Summary (PDF)",
                    data=pdf_buffer,
                    file_name="Olist_Executive_Summary_Report.pdf",
                    mime="application/pdf"
                )
                st.success("PDF Executive Report generated successfully!")


if __name__ == "__main__":
    main()
