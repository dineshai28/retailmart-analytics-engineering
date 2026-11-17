import duckdb
import pandas as pd

print("Starting RetailMart Pipeline...")

con = duckdb.connect("retailmart.duckdb")

customers_df = pd.read_csv(r"C:\Users\dines\clean_customers.csv")
products_df = pd.read_csv(r"C:\Users\dines\clean_products.csv")
stores_df = pd.read_csv(r"C:\Users\dines\clean_stores.csv")
transactions_df = pd.read_csv(r"C:\Users\dines\clean_transactions.csv")

con.execute("CREATE OR REPLACE TABLE raw_customers AS SELECT * FROM customers_df")
con.execute("CREATE OR REPLACE TABLE raw_products AS SELECT * FROM products_df")
con.execute("CREATE OR REPLACE TABLE raw_stores AS SELECT * FROM stores_df")
con.execute("CREATE OR REPLACE TABLE raw_transactions AS SELECT * FROM transactions_df")
print("Raw data loaded.")

con.execute("""
    CREATE OR REPLACE TABLE quarantine_transactions AS
    SELECT 
        *,
        CASE 
            WHEN quantity IS NULL OR quantity <= 0 THEN 'Quantity missing or invalid'
            WHEN unit_price IS NULL OR unit_price <= 0 THEN 'Price missing or invalid'
            WHEN CAST(transaction_date AS DATE) > CURRENT_DATE THEN 'Date in the future'
            WHEN store_id NOT IN (SELECT store_id FROM raw_stores) THEN 'Orphan store_id'
            WHEN product_id NOT IN (SELECT product_id FROM raw_products) THEN 'Orphan product_id'
            WHEN customer_id NOT IN (SELECT customer_id FROM raw_customers) THEN 'Orphan customer_id'
            WHEN customer_id IS NULL THEN 'Missing customer_id'
            WHEN payment_method NOT IN ('Card', 'Cash', 'Upi', 'Unknown') THEN 'Invalid payment method'
            WHEN transaction_id IN (
                SELECT transaction_id FROM raw_transactions GROUP BY transaction_id HAVING COUNT(*) > 1
            ) THEN 'Duplicate transaction_id'
        END AS bad_reason
    FROM raw_transactions
    WHERE 
        quantity IS NULL OR quantity <= 0
        OR unit_price IS NULL OR unit_price <= 0
        OR CAST(transaction_date AS DATE) > CURRENT_DATE
        OR store_id NOT IN (SELECT store_id FROM raw_stores)
        OR product_id NOT IN (SELECT product_id FROM raw_products)
        OR customer_id NOT IN (SELECT customer_id FROM raw_customers)
        OR customer_id IS NULL
        OR payment_method NOT IN ('Card', 'Cash', 'Upi', 'Unknown')
        OR transaction_id IN (
            SELECT transaction_id FROM raw_transactions GROUP BY transaction_id HAVING COUNT(*) > 1
        )
""")
print("Quarantine table built.")

con.execute("""
    CREATE OR REPLACE TABLE clean_transactions AS
    SELECT * FROM raw_transactions
    WHERE transaction_id NOT IN (SELECT transaction_id FROM quarantine_transactions)
""")
print("Clean table built.")

con.execute("""
    CREATE OR REPLACE TABLE pipeline_summary AS
    SELECT 
        'raw_transactions' AS table_name,
        (SELECT COUNT(*) FROM raw_transactions) AS rows_in,
        (SELECT COUNT(*) FROM clean_transactions) AS rows_passed,
        (SELECT COUNT(*) FROM quarantine_transactions) AS rows_quarantined;
""")

print("\nPipeline Complete! Here is the summary:")
summary = con.sql("SELECT * FROM pipeline_summary").df()
print(summary.to_string(index=False))

print("\nBuilding Star Schema...")

con.execute("CREATE OR REPLACE TABLE dim_customers AS SELECT * FROM raw_customers")
con.execute("CREATE OR REPLACE TABLE dim_products AS SELECT * FROM raw_products")
con.execute("CREATE OR REPLACE TABLE dim_stores AS SELECT * FROM raw_stores")

con.execute("""
    CREATE OR REPLACE TABLE fact_transactions AS
    SELECT 
        transaction_id,
        store_id,
        product_id,
        customer_id,
        quantity,
        unit_price,
        transaction_date
    FROM clean_transactions
""")

print("Star Schema Complete!")

print("\nRunning Data Quality Checks...")

con.execute("CREATE OR REPLACE TABLE dq_results (check_name VARCHAR, bad_rows INT, status VARCHAR)")
con.execute("""
    INSERT INTO dq_results
    SELECT 'Duplicate transaction_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM (SELECT transaction_id FROM raw_transactions GROUP BY transaction_id HAVING COUNT(*) > 1)
    UNION ALL SELECT 'Missing/Invalid quantity', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM raw_transactions WHERE quantity IS NULL OR quantity <= 0
    UNION ALL SELECT 'Missing/Invalid unit_price', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM raw_transactions WHERE unit_price IS NULL OR unit_price <= 0
    UNION ALL SELECT 'Future transaction_date', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM raw_transactions WHERE CAST(transaction_date AS DATE) > CURRENT_DATE
    UNION ALL SELECT 'Orphan store_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM raw_transactions WHERE store_id NOT IN (SELECT store_id FROM raw_stores)
    UNION ALL SELECT 'Orphan product_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM raw_transactions WHERE product_id NOT IN (SELECT product_id FROM raw_products)
    UNION ALL SELECT 'Orphan customer_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM raw_transactions WHERE customer_id NOT IN (SELECT customer_id FROM raw_customers)
    UNION ALL SELECT 'Missing customer_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM raw_transactions WHERE customer_id IS NULL
    UNION ALL SELECT 'Invalid payment_method', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM raw_transactions WHERE payment_method NOT IN ('Card', 'Cash', 'Upi', 'Unknown')
""")

con.execute("CREATE OR REPLACE TABLE clean_dq_results (check_name VARCHAR, bad_rows INT, status VARCHAR)")
con.execute("""
    INSERT INTO clean_dq_results
    SELECT 'Duplicate transaction_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM (SELECT transaction_id FROM clean_transactions GROUP BY transaction_id HAVING COUNT(*) > 1)
    UNION ALL SELECT 'Missing/Invalid quantity', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM clean_transactions WHERE quantity IS NULL OR quantity <= 0
    UNION ALL SELECT 'Missing/Invalid unit_price', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM clean_transactions WHERE unit_price IS NULL OR unit_price <= 0
    UNION ALL SELECT 'Future transaction_date', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM clean_transactions WHERE CAST(transaction_date AS DATE) > CURRENT_DATE
    UNION ALL SELECT 'Orphan store_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM clean_transactions WHERE store_id NOT IN (SELECT store_id FROM raw_stores)
    UNION ALL SELECT 'Orphan product_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM clean_transactions WHERE product_id NOT IN (SELECT product_id FROM raw_products)
    UNION ALL SELECT 'Orphan customer_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM clean_transactions WHERE customer_id NOT IN (SELECT customer_id FROM raw_customers)
    UNION ALL SELECT 'Missing customer_id', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM clean_transactions WHERE customer_id IS NULL
    UNION ALL SELECT 'Invalid payment_method', COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM clean_transactions WHERE payment_method NOT IN ('Card', 'Cash', 'Upi', 'Unknown')
""")

print("\n--- RAW DATA QUALITY REPORT ---")
print(con.sql("SELECT * FROM dq_results").df().to_string(index=False))

print("\n--- CLEAN DATA QUALITY REPORT ---")
print(con.sql("SELECT * FROM clean_dq_results").df().to_string(index=False))

print("\nBuilding Metric Layer...")

con.execute("""
    CREATE OR REPLACE VIEW metric_total_revenue AS
    SELECT SUM(quantity * unit_price) AS total_revenue
    FROM fact_transactions
""")

con.execute("""
    CREATE OR REPLACE VIEW metric_total_transactions AS
    SELECT COUNT(DISTINCT transaction_id) AS total_transactions
    FROM fact_transactions
""")

con.execute("""
    CREATE OR REPLACE VIEW metric_total_items_sold AS
    SELECT SUM(quantity) AS total_items_sold
    FROM fact_transactions
""")

con.execute("""
    CREATE OR REPLACE TABLE metric_catalog AS
    SELECT 'R01' AS metric_id, 'Total Revenue' AS metric_name, 'SUM(quantity * unit_price)' AS formula
    UNION ALL
    SELECT 'R02', 'Total Transactions', 'COUNT(DISTINCT transaction_id)'
    UNION ALL
    SELECT 'R03', 'Total Items Sold', 'SUM(quantity)'
""")

print("Metric Layer Complete!")

con.close()