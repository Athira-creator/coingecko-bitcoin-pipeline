
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv


# 1. Load database settings from .env
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

# 2. Configure the dashboard
st.set_page_config(
    page_title="BTC/MYR Dashboard",
    page_icon="₿",
    layout="wide",
)

st.title("₿ Bitcoin Price Dashboard")
st.caption("Data source: PostgreSQL | Currency: MYR")

if not DB_CONFIG["dbname"] or not DB_CONFIG["user"]:
    st.error("Check DB_NAME and DB_USER in your .env file.")
    st.stop()


# 3. Retrieve historical prices from PostgreSQL
@st.cache_data(ttl=30)
def load_prices():
    query = """
        SELECT coin_id, price_myr, source_timestamp, received_at
        FROM crypto_prices
        WHERE coin_id = 'bitcoin'
        ORDER BY received_at DESC
        LIMIT 20000;
    """

    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            columns = [col.name for col in cur.description]

    df = pd.DataFrame(rows, columns=columns)

    if not df.empty:
        df["price_myr"] = pd.to_numeric(df["price_myr"])
        df["received_at"] = pd.to_datetime(
            df["received_at"], utc=True
        )
        df = df.sort_values("received_at")

    return df


# 4. Display the data
try:
    df = load_prices()
except Exception as exc:
    st.error("Could not read data from PostgreSQL.")
    st.caption(f"Error details: {exc}")
    st.stop()

if df.empty:
    st.warning(
        "No Bitcoin records found. Run btc.py first "
        "and check the crypto_prices table."
    )
    st.stop()

latest = df.iloc[-1]
latest_price = float(latest["price_myr"])

st.subheader("Key Metrics")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Latest BTC Price",
    f"RM {latest_price:,.2f}",
)

col2.metric(
    "Records Loaded",
    f"{len(df):,}",
)

last_update = latest["received_at"]
col3.metric(
    "Last Database Update",
    last_update.strftime("%d %b %Y, %H:%M:%S UTC"),
)

# 5. Calculate an approximate 24-hour change
now = datetime.now(timezone.utc)
target_time = now - timedelta(hours=24)

baseline = df[df["received_at"] <= target_time]

if not baseline.empty:
    old_price = float(baseline.iloc[-1]["price_myr"])

    if old_price != 0:
        change_pct = (
            (latest_price - old_price) / old_price
        ) * 100

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Change vs. 24h Baseline",
            f"{change_pct:+.2f}%",
        )
    else:
        st.info("Cannot calculate percentage change from zero.")
else:
    st.info(
        "Collect at least 24 hours of history to calculate "
        "the 24-hour change."
    )

# 6. Plot historical prices
st.subheader("Bitcoin Price History")

chart_data = df.set_index("received_at")[["price_myr"]]
st.line_chart(chart_data, y="price_myr")

# 7. Display recent records
st.subheader("Recent Records")

st.dataframe(
    df.sort_values("received_at", ascending=False).head(100),
    use_container_width=True,
    hide_index=True,
)

# 8. Allow manual refresh
if st.button("Refresh Dashboard"):
    st.cache_data.clear()
    st.rerun()

