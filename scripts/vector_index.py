#!/usr/bin/env python3
"""
vector_index.py — Create the vector index for Vector Search & AI Copilot.

Usage: python scripts/vector_index.py

Checks that enough AI-ready docs exist, creates the vector index,
and waits for it to come online.
"""

import os
import sys
import time
import logging
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, ClusterTimeoutOptions
from couchbase.exceptions import CouchbaseException

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("vector-index")

BUCKET = os.getenv("CB_BUCKET", "smartdelivery")
INDEX_NAME = "idx_delivery_vectors"


def main():
    auth = PasswordAuthenticator(os.getenv("CB_USERNAME"), os.getenv("CB_PASSWORD"))
    cluster = Cluster(
        os.getenv("CB_CONN_STR"),
        ClusterOptions(auth, timeout_options=ClusterTimeoutOptions(
            query_timeout=timedelta(seconds=120),
        )),
    )
    cluster.wait_until_ready(timedelta(seconds=15))
    log.info("Connected to Couchbase.")

    # 1. Check if index already exists and is online
    rows = list(cluster.query(
        f"SELECT state FROM system:indexes WHERE name = '{INDEX_NAME}'"
    ))
    if rows:
        state = rows[0].get("state")
        if state == "online":
            log.info("Vector index '%s' is already online. Nothing to do.", INDEX_NAME)
            return
        log.info("Vector index '%s' exists (state: %s). Waiting for it...", INDEX_NAME, state)
    else:
        # 2. Check AI-ready doc count
        rows = list(cluster.query(
            f"SELECT COUNT(*) AS cnt FROM `{BUCKET}`.`processeddata`.`deliveries` d "
            f"WHERE d.is_ai_ready = true"
        ))
        ai_ready = rows[0]["cnt"] if rows else 0
        log.info("AI-ready docs: %d", ai_ready)

        if ai_ready < 200:
            log.error("Need at least 200 AI-ready docs. Run the event generator first.")
            sys.exit(1)

        # 3. Create the index
        log.info("Creating vector index '%s'...", INDEX_NAME)
        try:
            list(cluster.query(f"""
                CREATE VECTOR INDEX `{INDEX_NAME}`
                ON `{BUCKET}`.`processeddata`.`deliveries`(embedding VECTOR)
                WITH {{"dimension": 1536, "similarity": "COSINE"}}
            """))
            log.info("Created. Building in background...")
        except CouchbaseException as e:
            if "already exists" in str(e).lower():
                log.info("Index already exists. Waiting for it...")
            else:
                log.error("Failed: %s", e)
                sys.exit(1)

    # 4. Wait for online (up to 5 minutes)
    for i in range(60):
        time.sleep(5)
        rows = list(cluster.query(
            f"SELECT state FROM system:indexes WHERE name = '{INDEX_NAME}'"
        ))
        if rows and rows[0].get("state") == "online":
            log.info("Vector index is ONLINE. Vector Search is ready!")
            return
        state = rows[0].get("state", "?") if rows else "not visible yet"
        log.info("  [%ds] state: %s", (i + 1) * 5, state)

    log.warning("Index still building after 5 minutes. It will come online eventually.")


if __name__ == "__main__":
    main()
