
"""Bitcoin price tracker: CoinGecko REST API to Neon PostgreSQL."""

import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import requests
import psycopg
from dotenv import load_dotenv

# --------------------------------------------------
# 1. Load environment variables from .env
# --------------------------------------------------

script_dir = Path(__file__).resolve().parent
env_path = script_dir / ".env"

if not env_path.exists():
    env_path = script_dir.parent / ".env"

load_dotenv(env_path, override=True)

API_KEY = os.getenv("CG_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

BASE_URL = os.getenv(
    "CG_BASE_URL",
    "https://api.coingecko.com/api/v3",
)

COINS = ["bitcoin"]
CURRENCY = "myr"
INTERVAL_SECONDS = 60
TIMEOUT_SECONDS = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# --------------------------------------------------
# 2. Fetch prices from CoinGecko
# --------------------------------------------------

def fetch_prices(session):
    headers = {}

    if API_KEY:
        headers["x-cg-demo-api-key"] = API_KEY

    response = session.get(
        f"{BASE_URL.rstrip('/')}/simple/price",
        headers=headers,
        params={
            "ids": ",".join(COINS),
            "vs_currencies": CURRENCY,
            "include_last_updated_at": "true",
        },
        timeout=TIMEOUT_SECONDS,
    )

    response.raise_for_status()
    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("Unexpected CoinGecko API response")

    return data


# --------------------------------------------------
# 3. Save prices to Neon PostgreSQL
# --------------------------------------------------

def save_price(coin_id, price_myr, source_timestamp):
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing. Check your .env file."
        )

    sql = """
        INSERT INTO crypto_prices (
            coin_id,
            price_myr,
            source_timestamp
        )
        VALUES (%s, %s, %s);
    """

    # Neon connection string includes the host, database,
    # username and password. SSL is enabled in the URL.
    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=10,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                sql,
                (coin_id, price_myr, source_timestamp),
            )


# --------------------------------------------------
# 4. Validate and process prices
# --------------------------------------------------

def process_prices(data):
    saved_count = 0

    for coin_id in COINS:
        values = data.get(coin_id)

        if not isinstance(values, dict):
            logging.warning(
                "No data returned for %s",
                coin_id,
            )
            continue

        raw_price = values.get(CURRENCY)

        try:
            price = Decimal(str(raw_price))
        except (InvalidOperation, ValueError, TypeError):
            logging.warning(
                "Invalid price for %s",
                coin_id,
            )
            continue

        if not price.is_finite() or price <= 0:
            logging.warning(
                "Non-positive price for %s",
                coin_id,
            )
            continue

        raw_timestamp = values.get("last_updated_at")
        source_timestamp = None

        if raw_timestamp is not None:
            try:
                source_timestamp = datetime.fromtimestamp(
                    float(raw_timestamp),
                    tz=timezone.utc,
                )
            except (
                ValueError,
                TypeError,
                OverflowError,
                OSError,
            ):
                logging.warning(
                    "Invalid source timestamp for %s",
                    coin_id,
                )

        save_price(
            coin_id,
            price,
            source_timestamp,
        )

        logging.info(
            "%s: RM %s | Saved to Neon PostgreSQL",
            coin_id.upper(),
            f"{price:,.2f}",
        )

        saved_count += 1

    if saved_count == 0:
        logging.warning("No records saved in this cycle")


# --------------------------------------------------
# 5. Run the pipeline every 60 seconds
# --------------------------------------------------

def main():
    if not API_KEY:
        raise RuntimeError(
            f"CG_API_KEY is missing. Check this file: {env_path}"
        )

    if not DATABASE_URL:
        raise RuntimeError(
            f"DATABASE_URL is missing. Check this file: {env_path}"
        )

    logging.info("Starting Bitcoin price tracker")
    logging.info("Database target: Neon PostgreSQL")
    logging.info(
        "Polling interval: %s seconds",
        INTERVAL_SECONDS,
    )

    with requests.Session() as session:
        while True:
            cycle_start = time.monotonic()

            try:
                data = fetch_prices(session)
                process_prices(data)

            except requests.RequestException as exc:
                logging.error(
                    "CoinGecko request failed: %s",
                    exc,
                )

            except Exception:
                logging.exception(
                    "Pipeline cycle failed"
                )

            elapsed = time.monotonic() - cycle_start

            time.sleep(
                max(0, INTERVAL_SECONDS - elapsed)
            )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Tracker stopped")
