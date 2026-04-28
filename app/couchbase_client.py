"""Couchbase connection and query helpers – optimised for sub-second responses."""

from __future__ import annotations
from datetime import timedelta

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, ClusterTimeoutOptions
from couchbase.exceptions import CouchbaseException, DocumentNotFoundException

from config import CB_CONN_STR, CB_USERNAME, CB_PASSWORD, CB_BUCKET, SCOPE_RAW, SCOPE_PROCESSED, VECTOR_INDEX_THRESHOLD


def get_cluster() -> Cluster:
    auth = PasswordAuthenticator(CB_USERNAME, CB_PASSWORD)
    cluster = Cluster(
        CB_CONN_STR,
        ClusterOptions(auth, timeout_options=ClusterTimeoutOptions(
            kv_timeout=timedelta(seconds=10),
            query_timeout=timedelta(seconds=30),
        )),
    )
    cluster.wait_until_ready(timedelta(seconds=15))
    return cluster


def _bucket(cluster: Cluster):
    return cluster.bucket(CB_BUCKET)


# ── Collection counts ──────────────────────────────────────────
def get_counts(cluster: Cluster) -> dict:
    """Return document counts for raw and processed scopes.

    Simple COUNT(*) without WHERE is fast — Couchbase serves it from index metadata.
    """
    counts = {}
    for scope, cols in [(SCOPE_RAW, ["homes", "events", "deliveries", "alerts"]),
                        (SCOPE_PROCESSED, ["deliveries"])]:
        for col in cols:
            key = f"{scope}.{col}"
            try:
                rows = list(cluster.query(
                    f"SELECT COUNT(*) AS cnt FROM `{CB_BUCKET}`.`{scope}`.`{col}`"
                ))
                counts[key] = rows[0]["cnt"] if rows else 0
            except CouchbaseException:
                counts[key] = 0
    return counts


# ── Delivery queries ───────────────────────────────────────────
def get_raw_deliveries(cluster: Cluster, limit: int = 20) -> list[dict]:
    """Uses idx_raw_deliveries_created(created_at DESC) — fast ordered scan at any data size."""
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.*
            FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`deliveries` d
                USE INDEX (idx_raw_deliveries_created)
            WHERE d.created_at IS NOT MISSING
            ORDER BY d.created_at DESC
            LIMIT $limit""",
        limit=limit,
    ))
    return rows


def get_raw_delivery_by_scenario(cluster: Cluster, scenario: str) -> dict | None:
    """Fetch any raw delivery matching a scenario_type. LIMIT 1, no sort — sub-second."""
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.*
            FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`deliveries` d
            WHERE d.scenario_type = $scenario
            LIMIT 1""",
        scenario=scenario,
    ))
    return rows[0] if rows else None


def get_delivery_by_id(cluster: Cluster, scope: str, doc_id: str) -> dict | None:
    """KV get – instant point lookup, no N1QL overhead."""
    try:
        col = _bucket(cluster).scope(scope).collection("deliveries")
        result = col.get(doc_id)
        doc = result.content_as[dict]
        doc["doc_id"] = doc_id
        return doc
    except (DocumentNotFoundException, CouchbaseException):
        return None


def get_ai_ready_count(cluster: Cluster) -> int:
    """Uses idx_proc_deliveries_aiready(is_ai_ready, status)."""
    try:
        rows = list(cluster.query(
            f"""SELECT COUNT(*) AS cnt
                FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
                    USE INDEX (idx_proc_deliveries_aiready)
                WHERE d.is_ai_ready = true"""
        ))
        return rows[0]["cnt"] if rows else 0
    except CouchbaseException:
        return 0


# ── Vector index auto-management ───────────────────────────────


def ensure_vector_index(cluster: Cluster) -> tuple[bool, str]:
    """Check vector index status; auto-create when enough embeddings exist.

    Returns (ready, message):
      - ready=True  → index is online, vector search is available
      - ready=False → message explains what's happening
    """
    # 1. Check if index already exists
    try:
        rows = list(cluster.query(
            "SELECT state FROM system:indexes WHERE name = 'idx_delivery_vectors'"
        ))
        if rows:
            state = rows[0].get("state", "")
            if state == "online":
                return True, ""
            if state in ("building", "deferred", "scheduled", "pending"):
                return False, "Vector index is building... Search will be available shortly."
            # Index in "error" or unknown state → drop and attempt recreation
            try:
                list(cluster.query(
                    f"DROP INDEX `idx_delivery_vectors` ON "
                    f"`{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries`"
                ))
            except CouchbaseException:
                pass
    except CouchbaseException:
        pass

    # 2. Check embedding data volume
    ai_ready = get_ai_ready_count(cluster)
    if ai_ready < VECTOR_INDEX_THRESHOLD:
        return False, (
            "Waiting for embeddings — AI-ready docs. "
            "The VectorEmbeddingPipeline will generate them automatically."
        )

    # 3. Enough data — create the IVF,SQ8 index (async build on server side)
    try:
        list(cluster.query(f"""
            CREATE VECTOR INDEX `idx_delivery_vectors`
            ON `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries`(embedding VECTOR)
            WITH {{"dimension": 1536, "similarity": "COSINE", "description": "IVF,SQ8"}}
        """))
        return False, (
            f"Vector index created ({ai_ready} docs). "
            f"Building in progress — search available in ~1-2 minutes."
        )
    except CouchbaseException as e:
        if "already exists" in str(e).lower():
            return False, "Vector index is building..."
        return False, f"Vector index creation pending: {e}"


# ── Recent processed deliveries (for homeowner view) ──────────
def get_recent_processed_deliveries(cluster: Cluster, limit: int = 20) -> list[dict]:
    """Uses idx_proc_deliveries_status(status, created_at DESC)."""
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.id, d.owner_name, d.address,
                   d.status, d.scenario_type, d.carrier, d.risk_score,
                   d.knowledge_summary, d.risk_assessment,
                   d.delivery_location, d.is_ai_ready,
                   d.created_at, d.processing_status
            FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
                USE INDEX (idx_proc_deliveries_status)
            WHERE d.status IS NOT MISSING
            ORDER BY d.created_at DESC
            LIMIT $limit""",
        limit=limit,
    ))
    return rows


# ── Recent alerts ─────────────────────────────────────────────
def get_recent_alerts(cluster: Cluster, severity: str = "", limit: int = 20) -> list[dict]:
    """Uses idx_raw_alerts_severity(severity, triggered_at DESC).

    When no severity filter is set, fetches a balanced mix across all severity
    levels so the feed shows a realistic operational picture.
    """
    if severity:
        # Single severity filter — straightforward
        rows = list(cluster.query(
            f"""SELECT META(d).id AS doc_id, d.*
                FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`alerts` d
                    USE INDEX (idx_raw_alerts_severity)
                WHERE d.severity = '{severity}'
                ORDER BY d.triggered_at DESC
                LIMIT {limit}"""
        ))
        return rows

    # No filter — fetch a balanced mix from each severity
    per_sev = max(limit // 4, 3)
    combined = []
    for sev in ("critical", "high", "medium", "low"):
        try:
            rows = list(cluster.query(
                f"""SELECT META(d).id AS doc_id, d.*
                    FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`alerts` d
                        USE INDEX (idx_raw_alerts_severity)
                    WHERE d.severity = '{sev}'
                    ORDER BY d.triggered_at DESC
                    LIMIT {per_sev}"""
            ))
            combined.extend(rows)
        except CouchbaseException:
            pass
    # Sort the combined set by triggered_at descending
    combined.sort(key=lambda x: x.get("triggered_at", ""), reverse=True)
    return combined[:limit]


# ── Vector search with filters (for search tab) ────────────────
def vector_search_with_filters(cluster: Cluster, query_embedding: list[float],
                               carrier: str = "", scenario: str = "",
                               status: str = "", risk_level: str = "",
                               limit: int = 10) -> tuple[list[dict], str]:
    """Vector search with scalar filters.
    Returns (results, display_query) tuple."""
    conditions = ["d.is_ai_ready = true"]
    if carrier:
        conditions.append(f"d.carrier = '{carrier}'")
    if scenario:
        conditions.append(f"d.scenario_type = '{scenario}'")
    if status:
        conditions.append(f"d.status = '{status}'")
    if risk_level == "critical":
        conditions.append("d.risk_score >= 0.75")
    elif risk_level == "high":
        conditions.append("d.risk_score >= 0.45 AND d.risk_score < 0.75")
    elif risk_level == "medium":
        conditions.append("d.risk_score >= 0.20 AND d.risk_score < 0.45")
    elif risk_level == "low":
        conditions.append("d.risk_score < 0.20")

    where_clause = " AND ".join(conditions)

    # Build display-friendly query
    display_query = f"""SELECT META(d).id, d.id, d.owner_name, d.address,
       d.status, d.scenario_type, d.knowledge_summary, d.risk_assessment,
       d.carrier, d.risk_score, d.delivery_location,
       d.event_timeline, d.risk_factors,
       APPROX_VECTOR_DISTANCE(d.embedding, $query_vec, "COSINE") AS score
FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
WHERE {where_clause}
ORDER BY APPROX_VECTOR_DISTANCE(d.embedding, $query_vec, "COSINE")
LIMIT {limit};

-- $query_vec = OpenAI text-embedding-3-small (1536 dims)
-- Index: Hyperscale Vector Index with COSINE similarity"""

    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.id, d.owner_name, d.address,
                   d.status, d.scenario_type, d.knowledge_summary, d.risk_assessment,
                   d.carrier, d.risk_score, d.delivery_location,
                   d.event_timeline, d.risk_factors,
                   APPROX_VECTOR_DISTANCE(d.embedding, $vec, "COSINE") AS distance
            FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
            WHERE {where_clause}
            ORDER BY APPROX_VECTOR_DISTANCE(d.embedding, $vec, "COSINE")
            LIMIT $lim""",
        vec=query_embedding,
        lim=limit,
    ))
    for row in rows:
        row["score"] = round(1.0 - row.get("distance", 0), 6)
        row["similarity"] = row["score"]
    return rows, display_query


# ── Get a raw delivery for PII comparison ──────────────────────
def get_raw_delivery_by_id(cluster: Cluster, doc_id: str) -> dict | None:
    """KV get – instant point lookup."""
    try:
        col = _bucket(cluster).scope(SCOPE_RAW).collection("deliveries")
        result = col.get(doc_id)
        doc = result.content_as[dict]
        doc["doc_id"] = doc_id
        return doc
    except (DocumentNotFoundException, CouchbaseException):
        return None


# ── Pipeline performance metrics ───────────────────────────────
def get_pipeline_metrics(cluster: Cluster) -> dict | None:
    """KV get – instant point lookup instead of N1QL scan."""
    try:
        col = _bucket(cluster).scope(SCOPE_RAW).collection("events")
        result = col.get("pipeline_metrics")
        return result.content_as[dict]
    except (DocumentNotFoundException, CouchbaseException):
        return None


def get_processing_stats(cluster: Cluster) -> dict:
    """Compare raw vs processed counts to show Eventing processing rate."""
    raw_count = 0
    proc_count = 0
    try:
        rows = list(cluster.query(
            f"""SELECT COUNT(*) AS cnt FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`deliveries` d
                USE INDEX (idx_raw_deliveries_status)
                WHERE d.status IS NOT MISSING"""
        ))
        raw_count = rows[0]["cnt"] if rows else 0
    except CouchbaseException:
        pass
    try:
        rows = list(cluster.query(
            f"""SELECT COUNT(*) AS cnt FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
                USE INDEX (idx_proc_deliveries_status)
                WHERE d.status IS NOT MISSING"""
        ))
        proc_count = rows[0]["cnt"] if rows else 0
    except CouchbaseException:
        pass
    return {"raw_count": raw_count, "processed_count": proc_count}
