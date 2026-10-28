
"""Bitcoin price tracker: CoinGecko REST API to PostgreSQL."""

import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import requests
import psycopg
from dotenv import load_dotenv

# Locate .env in the project folder.
script_dir = Path(__file__).resolve().parent
env_path = script_dir / ".env"

if not env_path.exists():
    env_path = script_dir.parent / ".env"

load_dotenv(env_path, override=True)

# FIX: Read the correct environment variable.
API_KEY = os.getenv("CG_API_KEY")

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


def fetch_prices(session):
    response = session.get(
        f"{BASE_URL.rstrip('/')}/simple/price",
        headers={"x-cg-demo-api-key": API_KEY},
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
        raise ValueError("Unexpected API response")

    return data


def save_price(coin_id, price_myr, source_timestamp):
    sql = """
        INSERT INTO crypto_prices (
            coin_id,
            price_myr,
            source_timestamp
        )
        VALUES (%s, %s, %s);
    """

    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "crypto_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=10,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                sql,
                (coin_id, price_myr, source_timestamp),
            )


def process_prices(data):
    saved_count = 0

    for coin_id in COINS:
        values = data.get(coin_id)

        if not isinstance(values, dict):
            logging.warning("No data returned for %s", coin_id)
            continue

        raw_price = values.get(CURRENCY)

        try:
            price = Decimal(str(raw_price))
        except (InvalidOperation, ValueError, TypeError):
            logging.warning("Invalid price for %s", coin_id)
            continue

        if not price.is_finite() or price <= 0:
            logging.warning("Non-positive price for %s", coin_id)
            continue

        raw_timestamp = values.get("last_updated_at")

        if raw_timestamp is not None:
            try:
                source_timestamp = datetime.fromtimestamp(
                    float(raw_timestamp),
                    tz=timezone.utc,
                )
            except (ValueError, TypeError, OverflowError, OSError):
                source_timestamp = None
        else:
            source_timestamp = None

        save_price(coin_id, price, source_timestamp)

        logging.info(
            "%s: RM %s | Saved to PostgreSQL",
            coin_id.upper(),
            f"{price:,.2f}",
        )
        saved_count += 1

    if saved_count == 0:
        logging.warning("No records saved in this cycle")


def main():
    if not API_KEY:
        raise RuntimeError(
            f"CG_API_KEY is missing. Check this file: {env_path}"
        )

    logging.info("Starting Bitcoin price tracker")

    with requests.Session() as session:
        while True:
            cycle_start = time.monotonic()

            try:
                data = fetch_prices(session)
                process_prices(data)

            except requests.RequestException as exc:
                logging.error("CoinGecko request failed: %s", exc)

            except Exception:
                logging.exception("Pipeline cycle failed")

            elapsed = time.monotonic() - cycle_start
            time.sleep(max(0, INTERVAL_SECONDS - elapsed))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Tracker stopped")
