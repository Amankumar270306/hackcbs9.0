#!/usr/bin/env python3
"""Database initialization and Alembic migration runner script."""

import logging
import os
import subprocess
import sys
import time
import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration_runner")

HOST = os.getenv("YUGABYTEDB_HOST", "yugabytedb")
PORT = int(os.getenv("YUGABYTEDB_PORT", "5433"))
USER = os.getenv("DATABASE_USER", "yugabyte")
PASSWORD = os.getenv("DATABASE_PASSWORD", "")
TARGET_DB = os.getenv("DATABASE_NAME", "compliance_sentinel")

auth = f"{USER}" + (f":{PASSWORD}" if PASSWORD else "")
DEFAULT_DB_URL = f"postgresql://{auth}@{HOST}:{PORT}/yugabyte"


def wait_and_create_db(max_retries: int = 30, delay_sec: int = 2) -> None:
    """Connect to default database and ensure target database exists."""
    logger.info(f"Connecting to YugabyteDB on {HOST}:{PORT}...")
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg.connect(DEFAULT_DB_URL, autocommit=True)
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TARGET_DB,))
                if not cur.fetchone():
                    logger.info(f"Database '{TARGET_DB}' does not exist. Creating...")
                    cur.execute(f'CREATE DATABASE "{TARGET_DB}";')
                    logger.info(f"Database '{TARGET_DB}' successfully created.")
                else:
                    logger.info(f"Database '{TARGET_DB}' already exists.")
            conn.close()
            return
        except Exception as exc:
            logger.warning(f"Attempt {attempt}/{max_retries}: YugabyteDB not ready ({exc}). Retrying in {delay_sec}s...")
            time.sleep(delay_sec)

    logger.error("Failed to connect to YugabyteDB after maximum retries.")
    sys.exit(1)


def run_alembic_upgrade() -> None:
    """Execute Alembic upgrade head."""
    logger.info("Executing Alembic migrations...")
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Alembic upgrade failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        sys.exit(result.returncode)
    logger.info(f"Alembic migrations completed successfully:\n{result.stdout}")


if __name__ == "__main__":
    wait_and_create_db()
    run_alembic_upgrade()

