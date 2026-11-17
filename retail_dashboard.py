import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

# 1. Page Setup
st.set_page_config(page_title="RetailMart Dashboard", layout="wide")
st.title("🛍️ RetailMart Sales Dashboard")

# 2. Connect to Database
con = duckdb.connect("retailmart.duckdb")

# 3. Slicer (Get list of cities)
cities_df = con.sql("SELECT DISTINCT city FROM dim_stores").df()
city_list = ["All Cities"] + cities_df['city'].tolist()
selected_city = st.sidebar.selectbox("Select a City", city_list)

# 4. Build SQL Filter based on Slicer
if selected_city == "All Cities":
    filter_sql = "1=1"
else:
    filter_sql = f"s.city = '{selected_city}'"

# 5. KPI Cards
kpi_query = f"""
    SELECT 
        (SELECT SUM(quantity * unit_price) FROM fact_transactions f JOIN dim_stores s ON f.store_id = s.store_id WHERE {filter_sql}) AS total_revenue,
        (SELECT COUNT(DISTINCT transaction_id) FROM fact_transactions f JOIN dim_stores s ON f.store_id = s.store_id WHERE {filter_sql}) AS total_transactions,
        (SELECT SUM(quantity) FROM fact_transactions f JOIN dim_stores s ON f.store_id = s.store_id WHERE {filter_sql}) AS total_items
"""
kpi_df = con.sql(kpi_query).df()

col1, col2, col3 = st.columns(3)
col1.metric("Total Revenue (₹)", f"{kpi_df['total_revenue'][0]:,.2f}")
col2.metric("Total Transactions", f"{kpi_df['total_transactions'][0]:,}")
col3.metric("Total Items Sold", f"{kpi_df['total_items'][0]:,}")

# 6. Chart 1: Revenue by City
st.subheader("Revenue by City")
city_query = f"""
    SELECT s.city, SUM(f.quantity * f.unit_price) AS revenue
    FROM fact_transactions f
    JOIN dim_stores s ON f.store_id = s.store_id
    WHERE {filter_sql}
    GROUP BY s.city
"""
city_df = con.sql(city_query).df()
fig1 = px.bar(city_df, x='city', y='revenue', text='revenue', color='city')
st.plotly_chart(fig1, use_container_width=True)

# 7. Chart 2: Top 5 Products
st.subheader("Top 5 Best-Selling Products")
product_query = f"""
    SELECT p.product_name, SUM(f.quantity) AS total_sold
    FROM fact_transactions f
    JOIN dim_products p ON f.product_id = p.product_id
    JOIN dim_stores s ON f.store_id = s.store_id
    WHERE {filter_sql}
    GROUP BY p.product_name
    ORDER BY total_sold DESC
    LIMIT 5
"""
product_df = con.sql(product_query).df()
fig2 = px.bar(product_df, x='total_sold', y='product_name', orientation='h', text='total_sold', color='product_name')
st.plotly_chart(fig2, use_container_width=True)

con.close()