"""
Couchbase Capella Setup - SmartDelivery
Creates bucket, 2 scopes (rawdata + processeddata), 7 collections, GSI indexes, vector index.
Usage: python scripts/setup_couchbase.py
"""

import os
import sys
import time
import logging
from datetime import timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, ClusterTimeoutOptions
from couchbase.exceptions import ScopeAlreadyExistsException, CollectionAlreadyExistsException

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

BUCKET = os.getenv("CB_BUCKET", "chamberlain")
SCOPES = {
    "rawdata": ["homes", "events", "deliveries", "alerts"],
    "processeddata": ["events", "deliveries", "alerts"],
}


class CapellaAPI:
    def __init__(self):
        self.base = os.getenv("CAPELLA_API_BASE", "https://cloudapi.cloud.couchbase.com")
        self.headers = {
            "Authorization": f"Bearer {os.getenv('CAPELLA_API_SECRET')}",
            "Content-Type": "application/json",
        }
        self.org_id = self.project_id = self.cluster_id = None

    def _get(self, path):
        r = requests.get(f"{self.base}{path}", headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path, data):
        return requests.post(f"{self.base}{path}", headers=self.headers, json=data, timeout=30)

    def discover(self):
        log.info("Discovering Capella org/project/cluster...")
        orgs = self._get("/v4/organizations")
        self.org_id = orgs["data"][0]["id"]
        log.info("  Org: %s", orgs["data"][0].get("name"))

        projects = self._get(f"/v4/organizations/{self.org_id}/projects")
        self.project_id = projects["data"][0]["id"]
        log.info("  Project: %s", projects["data"][0].get("name"))

        clusters = self._get(f"/v4/organizations/{self.org_id}/projects/{self.project_id}/clusters")
        conn_host = os.getenv("CB_CONN_STR", "").replace("couchbases://", "")
        matched = None
        for c in clusters["data"]:
            if conn_host in c.get("connectionString", ""):
                matched = c
                break
        if not matched:
            matched = clusters["data"][0]
        self.cluster_id = matched["id"]
        log.info("  Cluster: %s", matched.get("name"))

    def _bp(self):
        return f"/v4/organizations/{self.org_id}/projects/{self.project_id}/clusters/{self.cluster_id}"

    def _bucket_id(self, name):
        try:
            for b in self._get(f"{self._bp()}/buckets").get("data", []):
                if b.get("name") == name:
                    return b.get("id", name)
        except Exception:
            pass
        return name

    def ensure_bucket(self, name, ram_mb=256):
        try:
            for b in self._get(f"{self._bp()}/buckets").get("data", []):
                if b.get("name") == name:
                    log.info("  Bucket '%s' exists.", name)
                    return False
        except Exception:
            pass
        r = self._post(f"{self._bp()}/buckets", {
            "name": name, "type": "couchbase", "storageBackend": "couchstore",
            "memoryAllocationInMb": ram_mb, "bucketConflictResolution": "seqno",
            "durabilityLevel": "none", "replicas": 1, "flush": True, "timeToLiveInSeconds": 0,
        })
        if r.status_code in (200, 201, 202):
            log.info("  Bucket '%s' created.", name)
            return True
        if "already exists" in r.text.lower():
            log.info("  Bucket '%s' exists.", name)
            return False
        r.raise_for_status()

    def ensure_scope(self, bucket, scope):
        bid = self._bucket_id(bucket)
        r = self._post(f"{self._bp()}/buckets/{bid}/scopes", {"name": scope})
        if r.status_code in (200, 201, 202):
            log.info("  Scope '%s' created.", scope)
        elif "already exists" in r.text.lower():
            log.info("  Scope '%s' exists.", scope)
        else:
            log.warning("  Scope '%s': %s %s", scope, r.status_code, r.text)

    def ensure_collection(self, bucket, scope, collection):
        bid = self._bucket_id(bucket)
        r = self._post(f"{self._bp()}/buckets/{bid}/scopes/{scope}/collections", {"name": collection})
        if r.status_code in (200, 201, 202):
            log.info("  Collection '%s.%s' created.", scope, collection)
        elif "already exists" in r.text.lower():
            log.info("  Collection '%s.%s' exists.", scope, collection)
        else:
            log.warning("  Collection '%s.%s': %s %s", scope, collection, r.status_code, r.text)


def main():
    for var in ("CAPELLA_API_SECRET", "CB_CONN_STR", "CB_USERNAME", "CB_PASSWORD"):
        if not os.getenv(var):
            log.error("%s not set in .env", var)
            sys.exit(1)

    # Phase 1: Capella Management API
    log.info("=" * 60)
    log.info("Phase 1: Capella Management API")
    log.info("=" * 60)
    api = CapellaAPI()
    api.discover()

    created = api.ensure_bucket(BUCKET)
    if created:
        log.info("Waiting 15s for bucket...")
        time.sleep(15)

    for scope_name, collections in SCOPES.items():
        api.ensure_scope(BUCKET, scope_name)
        time.sleep(2)
        for col in collections:
            api.ensure_collection(BUCKET, scope_name, col)
    time.sleep(5)

    # Phase 2: SDK indexes
    log.info("")
    log.info("=" * 60)
    log.info("Phase 2: SDK - GSI Indexes")
    log.info("=" * 60)
    auth = PasswordAuthenticator(os.getenv("CB_USERNAME"), os.getenv("CB_PASSWORD"))
    cluster = Cluster(
        os.getenv("CB_CONN_STR"),
        ClusterOptions(auth, timeout_options=ClusterTimeoutOptions(
            kv_timeout=timedelta(seconds=10),
            query_timeout=timedelta(seconds=60),
            management_timeout=timedelta(seconds=30),
        )),
    )
    cluster.wait_until_ready(timedelta(seconds=15))
    log.info("SDK connected.")

    def create_index(stmt, name):
        try:
            list(cluster.query(stmt))
            log.info("  Created: %s", name)
        except Exception as e:
            if "already exists" in str(e).lower():
                log.info("  Exists: %s", name)
            else:
                log.warning("  %s: %s", name, e)

    # Primary indexes on all collections
    for scope_name, collections in SCOPES.items():
        for col in collections:
            idx = f"primary_{scope_name}_{col}"
            create_index(
                f"CREATE PRIMARY INDEX `{idx}` ON `{BUCKET}`.`{scope_name}`.`{col}`",
                idx,
            )
    time.sleep(10)

    # Secondary indexes
    secondaries = [
        ("idx_raw_deliveries_status", "rawdata", "deliveries", "status, created_at DESC", None),
        ("idx_raw_deliveries_home", "rawdata", "deliveries", "home_id, status", None),
        ("idx_raw_events_home", "rawdata", "events", "home_id, `timestamp` DESC", None),
        ("idx_proc_deliveries_status", "processeddata", "deliveries", "status, created_at DESC", None),
        ("idx_proc_deliveries_scenario", "processeddata", "deliveries", "scenario_type, status", None),
        ("idx_proc_deliveries_aiready", "processeddata", "deliveries", "is_ai_ready, status", None),
        ("idx_proc_alerts_severity", "processeddata", "alerts", "severity, triggered_at DESC", None),
    ]
    for idx_name, scope, col, fields, where in secondaries:
        w = f" WHERE {where}" if where else ""
        create_index(
            f"CREATE INDEX `{idx_name}` ON `{BUCKET}`.`{scope}`.`{col}`({fields}){w}",
            idx_name,
        )
    time.sleep(10)

    # Phase 3: Hyperscale Vector Index for APPROX_VECTOR_DISTANCE
    log.info("")
    log.info("=" * 60)
    log.info("Phase 3: Hyperscale Vector Search Index")
    log.info("=" * 60)
    vec_idx = "idx_delivery_embedding"
    log.info("  Note: Vector index requires training data (embeddings).")
    log.info("  Run event generator + eventing first, then create this index.")
    create_index(
        f"""CREATE VECTOR INDEX `{vec_idx}`
            ON `{BUCKET}`.`processeddata`.`deliveries`(embedding VECTOR)
            WITH {{"dimension": 1536, "similarity": "COSINE", "description": "IVF,SQ8"}}""",
        vec_idx,
    )

    log.info("")
    log.info("=" * 60)
    log.info("Setup complete!")
    log.info("=" * 60)
    log.info("Next steps:")
    log.info("  1. cd event-generator && go run main.go --homes 100 --scenarios 200")
    log.info("  2. Deploy eventing functions in Capella UI")
    log.info("  3. streamlit run app/main.py")


if __name__ == "__main__":
    main()
