"""
Create the Hyperscale Vector Index on processeddata.deliveries.
Run AFTER the event generator + eventing pipeline have produced embedding data.

Usage: python scripts/create_vector_index.py
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

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

BUCKET = os.getenv("CB_BUCKET", "smartdelivery")


def main():
    auth = PasswordAuthenticator(os.getenv("CB_USERNAME"), os.getenv("CB_PASSWORD"))
    cluster = Cluster(
        os.getenv("CB_CONN_STR"),
        ClusterOptions(auth, timeout_options=ClusterTimeoutOptions(
            query_timeout=timedelta(seconds=120),
        )),
    )
    cluster.wait_until_ready(timedelta(seconds=15))

    # Check that embedding data exists
    rows = list(cluster.query(
        f"SELECT COUNT(*) AS cnt FROM `{BUCKET}`.`processeddata`.`deliveries` d "
        f"WHERE d.is_ai_ready = true"
    ))
    ai_ready = rows[0]["cnt"] if rows else 0
    log.info("AI-ready docs with embeddings: %d", ai_ready)

    if ai_ready == 0:
        log.error("No embedding data found. Run the event generator and wait for "
                  "the VectorEmbeddingPipeline to process documents first.")
        sys.exit(1)

    # Drop existing index if present
    try:
        list(cluster.query(
            f"DROP INDEX `idx_delivery_embedding` ON `{BUCKET}`.`processeddata`.`deliveries`"
        ))
        log.info("Dropped existing vector index.")
        time.sleep(3)
    except Exception as e:
        if "not found" in str(e).lower() or "does not exist" in str(e).lower():
            log.info("No existing vector index to drop.")
        else:
            log.warning("Drop attempt: %s", e)

    # Create the vector index
    log.info("Creating Hyperscale Vector Index (IVF,SQ8)...")
    try:
        list(cluster.query(f"""
            CREATE VECTOR INDEX `idx_delivery_embedding`
            ON `{BUCKET}`.`processeddata`.`deliveries`(embedding VECTOR)
            WITH {{"dimension": 1536, "similarity": "COSINE", "description": "IVF,SQ8"}}
        """))
        log.info("Vector index created successfully!")
    except Exception as e:
        log.error("Failed to create vector index: %s", e)
        sys.exit(1)

    # Wait for index to build
    log.info("Waiting for index to become online...")
    for attempt in range(30):
        time.sleep(5)
        try:
            rows = list(cluster.query(
                "SELECT state FROM system:indexes WHERE name = 'idx_delivery_embedding'"
            ))
            if rows and rows[0].get("state") == "online":
                log.info("Vector index is online and ready!")
                return
            state = rows[0].get("state", "unknown") if rows else "not found"
            log.info("  Index state: %s", state)
        except Exception as e:
            log.warning("  Status check: %s", e)

    log.warning("Index may still be building. Check Capella UI.")


if __name__ == "__main__":
    main()
