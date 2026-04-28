"""
Couchbase Capella Setup - SmartDelivery
Creates bucket, 2 scopes (rawdata + processeddata), 5 collections, GSI indexes,
deploys eventing functions (enrichment + embedding pipelines), and vector index.
Usage: python scripts/setup_couchbase.py
"""

import os
import sys
import time
import logging
import tomllib
from datetime import timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, ClusterTimeoutOptions
from couchbase.exceptions import ScopeAlreadyExistsException, CollectionAlreadyExistsException
from couchbase.management.eventing import (
    EventingFunctionManager,
    EventingFunction,
    EventingFunctionKeyspace,
    EventingFunctionBucketBinding,
    EventingFunctionBucketAccess,
    EventingFunctionUrlBinding,
    EventingFunctionUrlAuthBearer,
    EventingFunctionSettings,
    EventingFunctionDcpBoundary,
    EventingFunctionState,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_project_root = Path(__file__).resolve().parent.parent
with open(_project_root / "settings.toml", "rb") as _f:
    _cfg = tomllib.load(_f)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

BUCKET = os.getenv("CB_BUCKET") or _cfg["database"]["bucket"]
SCOPES = {
    "rawdata": ["homes", "events", "deliveries", "alerts"],
    "processeddata": ["deliveries"],
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


def deploy_eventing_functions(cluster, bucket):
    """Deploy eventing functions using Couchbase SDK EventingFunctionManager."""
    eventing_mgr = cluster.eventing_functions()
    eventing_dir = Path(__file__).resolve().parent.parent / "eventing"
    openai_key = os.getenv("OPENAI_API_KEY", "")

    # ── Function 1: DeliveryKnowledgePipeline ──
    log.info("Deploying DeliveryKnowledgePipeline...")
    code1 = (eventing_dir / "delivery_knowledge_pipeline.js").read_text()

    func1 = EventingFunction(
        name="DeliveryKnowledgePipeline",
        code=code1,
        source_keyspace=EventingFunctionKeyspace(
            bucket=bucket, scope="rawdata", collection="deliveries"
        ),
        metadata_keyspace=EventingFunctionKeyspace(bucket=bucket),
        bucket_bindings=[
            EventingFunctionBucketBinding(
                alias="dst",
                name=EventingFunctionKeyspace(
                    bucket=bucket, scope="processeddata", collection="deliveries"
                ),
                access=EventingFunctionBucketAccess.ReadWrite,
            ),
            EventingFunctionBucketBinding(
                alias="src_events",
                name=EventingFunctionKeyspace(
                    bucket=bucket, scope="rawdata", collection="events"
                ),
                access=EventingFunctionBucketAccess.ReadOnly,
            ),
        ],
        settings=EventingFunctionSettings(
            description="Enriches raw deliveries with knowledge narratives, "
                        "risk assessments, and PII redaction. "
                        "Writes to processeddata.deliveries.",
            dcp_stream_boundary=EventingFunctionDcpBoundary.Everything,
        ),
    )
    try:
        eventing_mgr.upsert_function(func1)
        log.info("  Upserted: DeliveryKnowledgePipeline")
    except Exception as e:
        log.warning("  Upsert DeliveryKnowledgePipeline: %s", e)

    # ── Function 2: VectorEmbeddingPipeline ──
    log.info("Deploying VectorEmbeddingPipeline...")
    code2 = (eventing_dir / "vector_embedding_pipeline.js").read_text()

    func2 = EventingFunction(
        name="VectorEmbeddingPipeline",
        code=code2,
        source_keyspace=EventingFunctionKeyspace(
            bucket=bucket, scope="processeddata", collection="deliveries"
        ),
        metadata_keyspace=EventingFunctionKeyspace(bucket=bucket),
        bucket_bindings=[
            EventingFunctionBucketBinding(
                alias="dst",
                name=EventingFunctionKeyspace(
                    bucket=bucket, scope="processeddata", collection="deliveries"
                ),
                access=EventingFunctionBucketAccess.ReadWrite,
            ),
        ],
        url_bindings=[
            EventingFunctionUrlBinding(
                hostname="https://api.openai.com",
                alias="openai",
                allow_cookies=False,
                validate_ssl_certificate=True,
                auth=EventingFunctionUrlAuthBearer(key=openai_key),
            ),
        ],
        settings=EventingFunctionSettings(
            description="Generates OpenAI text-embedding-3-small vectors "
                        "for enriched deliveries. Marks docs as AI-ready.",
            dcp_stream_boundary=EventingFunctionDcpBoundary.Everything,
        ),
    )
    try:
        eventing_mgr.upsert_function(func2)
        log.info("  Upserted: VectorEmbeddingPipeline")
    except Exception as e:
        log.warning("  Upsert VectorEmbeddingPipeline: %s", e)

    # ── Deploy both functions ──
    time.sleep(5)
    for fn_name in ("DeliveryKnowledgePipeline", "VectorEmbeddingPipeline"):
        try:
            eventing_mgr.deploy_function(fn_name)
            log.info("  Deployed: %s", fn_name)
        except Exception as e:
            if "already deployed" in str(e).lower():
                log.info("  Already deployed: %s", fn_name)
            else:
                log.warning("  Deploy %s: %s", fn_name, e)

    # ── Wait for deployment ──
    log.info("  Waiting for eventing functions to finish deploying...")
    for attempt in range(30):
        time.sleep(5)
        try:
            statuses = eventing_mgr.functions_status()
            all_deployed = True
            if statuses.functions:
                for fn in statuses.functions:
                    state = fn.state
                    log.info("    %s: %s", fn.name, state)
                    if state != EventingFunctionState.Deployed:
                        all_deployed = False
            if all_deployed and statuses.functions:
                log.info("  All eventing functions deployed!")
                break
        except Exception as e:
            log.warning("  Status check: %s", e)
    else:
        log.warning("  Timeout waiting for eventing deployment. Check Capella UI.")


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
        # rawdata.deliveries
        ("idx_raw_deliveries_status", "rawdata", "deliveries", "status, created_at DESC", None),
        ("idx_raw_deliveries_created", "rawdata", "deliveries", "created_at DESC", None),
        ("idx_raw_deliveries_home", "rawdata", "deliveries", "home_id, status", None),
        # rawdata.events
        ("idx_raw_events_home", "rawdata", "events", "home_id, `timestamp` DESC", None),
        # rawdata.alerts
        ("idx_raw_alerts_triggered", "rawdata", "alerts", "triggered_at DESC", None),
        ("idx_raw_alerts_severity", "rawdata", "alerts", "severity, triggered_at DESC", None),
        # processeddata.deliveries
        ("idx_proc_deliveries_status", "processeddata", "deliveries", "status, created_at DESC", None),
        ("idx_proc_deliveries_scenario", "processeddata", "deliveries", "scenario_type, status", None),
        ("idx_proc_deliveries_scenario_status", "processeddata", "deliveries", "scenario_type, status, created_at DESC", None),
        ("idx_proc_deliveries_aiready", "processeddata", "deliveries", "is_ai_ready, status", None),
        ("idx_proc_deliveries_carrier", "processeddata", "deliveries", "carrier, created_at DESC", None),
        ("idx_proc_deliveries_risk", "processeddata", "deliveries", "risk_score, created_at DESC", None),
    ]
    for idx_name, scope, col, fields, where in secondaries:
        w = f" WHERE {where}" if where else ""
        create_index(
            f"CREATE INDEX `{idx_name}` ON `{BUCKET}`.`{scope}`.`{col}`({fields}){w}",
            idx_name,
        )
    time.sleep(10)

    # Phase 3: Hyperscale Vector Index note
    log.info("")
    log.info("=" * 60)
    log.info("Phase 3: Hyperscale Vector Search Index")
    log.info("=" * 60)
    log.info("  Skipped: IVF vector index requires 200+ embedded docs to build.")
    log.info("  The app will auto-create the index once enough embeddings exist.")
    log.info("  (Or manually: python scripts/create_vector_index.py)")

    # Phase 4: Deploy Eventing Functions via SDK
    log.info("")
    log.info("=" * 60)
    log.info("Phase 4: Eventing Functions (SDK EventingFunctionManager)")
    log.info("=" * 60)
    deploy_eventing_functions(cluster, BUCKET)

    log.info("")
    log.info("=" * 60)
    log.info("Setup complete!")
    log.info("=" * 60)
    log.info("Next steps:")
    log.info("  1. cd event-generator && go run main.go --homes 100 --scenarios 200")
    log.info("  2. streamlit run app/main.py")


if __name__ == "__main__":
    main()
