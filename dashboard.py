
"""Bitcoin Market Monitor | BTC/MYR analytics dashboard."""

import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

# --------------------------------------------------
# 1. Configuration and database connection
# --------------------------------------------------

load_dotenv()


def get_database_url():
    try:
        url = st.secrets.get("DATABASE_URL")
        if url:
            return url
    except Exception:
        pass

    return os.getenv("DATABASE_URL")


DATABASE_URL = get_database_url()

st.set_page_config(
    page_title="Bitcoin Market Monitor",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --------------------------------------------------
# 2. Visual design
# --------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&display=swap');

    :root {
        --bg: #0c111b;
        --panel: #141c29;
        --border: #293447;
        --muted: #98a6bb;
        --text: #edf2fa;
        --amber: #f5ad36;
        --green: #55d6a0;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
        font-family: 'DM Sans', sans-serif;
    }

    .block-container {
        max-width: 1440px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    .eyebrow {
        color: var(--amber);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        margin-bottom: 0.45rem;
    }

    .page-title {
        color: var(--text);
        font-size: clamp(1.8rem, 3vw, 2.65rem);
        line-height: 1.15;
        font-weight: 700;
        letter-spacing: -0.045em;
        margin: 0;
    }

    .subtitle {
        color: var(--muted);
        font-size: 0.94rem;
        margin-top: 0.55rem;
    }

    .section-title {
        color: var(--text);
        font-size: 1.15rem;
        font-weight: 650;
        letter-spacing: -0.02em;
        margin-bottom: 0.2rem;
    }

    .section-subtitle {
        color: var(--muted);
        font-size: 0.84rem;
        margin-bottom: 1rem;
    }

    .metric-card {
        background: linear-gradient(145deg, #172131, #121a27);
        border: 1px solid var(--border);
        border-radius: 15px;
        padding: 1.15rem 1.25rem;
        min-height: 142px;
    }

    .metric-label {
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 500;
        margin-bottom: 0.9rem;
    }

    .metric-value {
        color: var(--text);
        font-family: 'DM Mono', monospace;
        font-size: clamp(1.25rem, 2vw, 1.8rem);
        font-weight: 500;
        letter-spacing: -0.05em;
        overflow-wrap: anywhere;
    }

    .metric-note {
        color: var(--muted);
        font-size: 0.77rem;
        margin-top: 0.55rem;
    }

    .accent {
        color: var(--amber);
    }

    .positive {
        color: var(--green);
    }

    .negative {
        color: #ff8f8f;
    }

    .status-dot {
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--green);
        margin-right: 7px;
        vertical-align: middle;
    }

    .status-line {
        color: var(--muted);
        font-size: 0.8rem;
        margin-top: 1rem;
    }

    .panel {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 15px;
        padding: 1.25rem 1.35rem;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
    }

    div.stButton > button {
        border: 1px solid #3b475b;
        background: #1a2535;
        color: var(--text);
        border-radius: 9px;
        font-weight: 600;
        padding: 0.45rem 1rem;
    }

    div.stButton > button:hover {
        border-color: var(--amber);
        color: var(--amber);
    }

    div[data-testid="stAlert"] {
        border-radius: 12px;
    }

    hr {
        border-color: var(--border);
        margin-top: 1.5rem;
        margin-bottom: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# 3. Header
# --------------------------------------------------

header_left, header_right = st.columns([4, 1])

with header_left:
    st.markdown('<div class="eyebrow">Market intelligence / Digital assets</div>',
                unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">Bitcoin Market Monitor</h1>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">BTC / MYR · Historical price analytics</div>',
        unsafe_allow_html=True,
    )

with header_right:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("↻  Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown(
    "<div class='status-line'>"
    "<span class='status-dot'></span>"
    "Database connection configured · Prices stored in PostgreSQL"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown("---")

# --------------------------------------------------
# 4. Validate database configuration
# --------------------------------------------------

if not DATABASE_URL:
    st.error(
        "Database connection is not configured. Add DATABASE_URL "
        "to Streamlit Cloud → Settings → Secrets, or your local .env."
    )
    st.stop()


# --------------------------------------------------
# 5. Load price history
# --------------------------------------------------

@st.cache_data(ttl=30)
def load_prices():
    query = """
        SELECT
            coin_id,
            price_myr,
            source_timestamp,
            received_at
        FROM public.crypto_prices
        WHERE coin_id = 'bitcoin'
        ORDER BY received_at DESC
        LIMIT 20000;
    """

    with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            columns = [col.name for col in cur.description]

    df = pd.DataFrame(rows, columns=columns)

    if not df.empty:
        df["price_myr"] = pd.to_numeric(df["price_myr"])
        df["received_at"] = pd.to_datetime(df["received_at"], utc=True)
        df["source_timestamp"] = pd.to_datetime(
            df["source_timestamp"], utc=True, errors="coerce"
        )
        df = df.sort_values("received_at").reset_index(drop=True)

    return df


try:
    df = load_prices()
except Exception:
    st.error("Unable to load data from Neon PostgreSQL.")
    st.info(
        "Check that DATABASE_URL is the full Neon connection string "
        "and that public.crypto_prices exists in the selected database."
    )
    st.stop()

if df.empty:
    st.warning(
        "Your database is connected, but there are no Bitcoin records yet. "
        "Run the ingestion script and check that it writes to this Neon database."
    )
    st.stop()

# --------------------------------------------------
# 6. Derive metrics
# --------------------------------------------------

latest = df.iloc[-1]
latest_price = float(latest["price_myr"])
record_count = len(df)
last_update = latest["received_at"]

now = datetime.now(timezone.utc)
baseline = df[df["received_at"] <= now - timedelta(hours=24)]

change_pct = None
if not baseline.empty:
    old_price = float(baseline.iloc[-1]["price_myr"])
    if old_price:
        change_pct = ((latest_price - old_price) / old_price) * 100

first_record = df["received_at"].min()
history_hours = max(
    0, (last_update - first_record).total_seconds() / 3600
)

# --------------------------------------------------
# 7. Metric cards
# --------------------------------------------------

st.markdown('<div class="eyebrow">Market snapshot</div>',
            unsafe_allow_html=True)

m1, m2, m3 = st.columns(3)

with m1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Latest Bitcoin price</div>
            <div class="metric-value accent">RM {latest_price:,.2f}</div>
            <div class="metric-note">Malaysian ringgit · MYR</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m2:
    if change_pct is None:
        change_display = "Building history"
        change_class = ""
        change_note = "24-hour comparison not available yet"
    else:
        change_display = f"{change_pct:+.2f}%"
        change_class = "positive" if change_pct >= 0 else "negative"
        change_note = "Compared with the latest record at or before 24h ago"

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">24-hour price change</div>
            <div class="metric-value {change_class}">{change_display}</div>
            <div class="metric-note">{change_note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Records collected</div>
            <div class="metric-value">{record_count:,}</div>
            <div class="metric-note">History spans approximately {history_hours:.1f} hours</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# --------------------------------------------------
# 8. Price history chart
# --------------------------------------------------

chart_col, info_col = st.columns([3.2, 1])

with chart_col:
    st.markdown('<div class="section-title">Price history</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">'
        'Recorded BTC prices over time · Values shown in MYR'
        '</div>',
        unsafe_allow_html=True,
    )

    chart_df = df.set_index("received_at")[["price_myr"]]
    st.line_chart(
        chart_df,
        y="price_myr",
        color="#F5AD36",
        height=350,
    )

with info_col:
    st.markdown('<div class="section-title">Data status</div>',
                unsafe_allow_html=True)
    st.markdown("<div style='height:0.5rem'></div>",
                unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="panel">
            <div class="metric-label">Latest database write</div>
            <div style="font-size:1.02rem;font-weight:600;">
                {last_update.strftime("%d %b %Y")}
            </div>
            <div class="metric-note">
                {last_update.strftime("%H:%M:%S UTC")}
            </div>
            <hr>
            <div class="metric-label">Earliest record loaded</div>
            <div style="font-size:0.95rem;font-weight:600;">
                {first_record.strftime("%d %b %Y")}
            </div>
            <div class="metric-note">
                {first_record.strftime("%H:%M:%S UTC")}
            </div>
            <hr>
            <div class="metric-label">Collection interval</div>
            <div style="font-size:1.02rem;font-weight:600;">60 seconds</div>
            <div class="metric-note">
                Configured ingestion target; actual timing depends on the running worker.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --------------------------------------------------
# 9. Recent records
# --------------------------------------------------

st.markdown("---")
st.markdown('<div class="section-title">Recent price records</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">'
    'The latest entries stored in PostgreSQL'
    '</div>',
    unsafe_allow_html=True,
)

recent = df.sort_values("received_at", ascending=False).head(100).copy()
recent = recent.rename(
    columns={
        "coin_id": "Asset",
        "price_myr": "Price (MYR)",
        "source_timestamp": "Source timestamp",
        "received_at": "Database received at (UTC)",
    }
)

recent["Price (MYR)"] = recent["Price (MYR)"].map(
    lambda value: f"RM {value:,.2f}"
)

st.dataframe(
    recent[
        [
            "Asset",
            "Price (MYR)",
            "Source timestamp",
            "Database received at (UTC)",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.markdown("---")
st.markdown(
    """
    <div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;
                color:#98a6bb;font-size:0.76rem;">
        <span>BITCOIN MARKET MONITOR · BTC/MYR</span>
        <span>Source: CoinGecko REST API · Storage: PostgreSQL</span>
    </div>
    """,
    unsafe_allow_html=True,
)
