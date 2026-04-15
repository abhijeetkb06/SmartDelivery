"""Couchbase connection and query helpers."""

from __future__ import annotations
from datetime import timedelta
from typing import Any

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, ClusterTimeoutOptions
from couchbase.exceptions import CouchbaseException

from config import CB_CONN_STR, CB_USERNAME, CB_PASSWORD, CB_BUCKET, SCOPE_RAW, SCOPE_PROCESSED


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


# ── Collection counts ──────────────────────────────────────────
def get_counts(cluster: Cluster) -> dict:
    """Return document counts for raw and processed scopes."""
    counts = {}
    for scope, cols in [(SCOPE_RAW, ["homes", "events", "deliveries", "alerts"]),
                        (SCOPE_PROCESSED, ["deliveries", "alerts", "events"])]:
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
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.*
            FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`deliveries` d
            ORDER BY d.created_at DESC
            LIMIT $limit""",
        limit=limit,
    ))
    return rows


def get_processed_deliveries(cluster: Cluster, limit: int = 20) -> list[dict]:
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.*
            FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
            ORDER BY d.created_at DESC
            LIMIT $limit""",
        limit=limit,
    ))
    return rows


def get_delivery_by_id(cluster: Cluster, scope: str, doc_id: str) -> dict | None:
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.*
            FROM `{CB_BUCKET}`.`{scope}`.`deliveries` d
            WHERE META(d).id = $doc_id""",
        doc_id=doc_id,
    ))
    return rows[0] if rows else None


def get_delivery_stats(cluster: Cluster, scope: str) -> dict:
    rows = list(cluster.query(
        f"""SELECT
                COUNT(*) AS total,
                COUNT(CASE WHEN d.status = 'completed_success' THEN 1 END) AS success,
                COUNT(CASE WHEN d.status = 'completed_risk' THEN 1 END) AS risk,
                COUNT(CASE WHEN d.status = 'failed' THEN 1 END) AS failed,
                COUNT(CASE WHEN d.status = 'suspicious' THEN 1 END) AS suspicious
            FROM `{CB_BUCKET}`.`{scope}`.`deliveries` d"""
    ))
    return rows[0] if rows else {}


def get_ai_ready_count(cluster: Cluster) -> int:
    try:
        rows = list(cluster.query(
            f"""SELECT COUNT(*) AS cnt
                FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
                WHERE d.is_ai_ready = true"""
        ))
        return rows[0]["cnt"] if rows else 0
    except CouchbaseException:
        return 0


# ── Vector search via SQL++ APPROX_VECTOR_DISTANCE ─────────────
def vector_search(cluster: Cluster, query_embedding: list[float], limit: int = 5) -> list[dict]:
    """Semantic vector search using Couchbase APPROX_VECTOR_DISTANCE with Hyperscale Vector Index."""
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.id, d.owner_name, d.address,
                   d.status, d.scenario_type, d.carrier, d.risk_score,
                   d.knowledge_summary, d.risk_assessment,
                   d.delivery_location, d.is_ai_ready,
                   APPROX_VECTOR_DISTANCE(d.embedding, $vec, "COSINE") AS distance
            FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
            WHERE d.is_ai_ready = true
            ORDER BY APPROX_VECTOR_DISTANCE(d.embedding, $vec, "COSINE")
            LIMIT $lim""",
        vec=query_embedding,
        lim=limit,
    ))
    # Add similarity score (1 - cosine distance) for display
    for row in rows:
        row["similarity"] = round(1.0 - row.get("distance", 0), 6)
    return rows


# ── Aggregate distributions (for charts) ──────────────────────
def get_scenario_distribution(cluster: Cluster, scope: str) -> list[dict]:
    rows = list(cluster.query(
        f"""SELECT d.scenario_type, COUNT(*) AS cnt
            FROM `{CB_BUCKET}`.`{scope}`.`deliveries` d
            GROUP BY d.scenario_type
            ORDER BY cnt DESC"""
    ))
    return rows


def get_carrier_distribution(cluster: Cluster, scope: str) -> list[dict]:
    rows = list(cluster.query(
        f"""SELECT d.carrier, COUNT(*) AS cnt
            FROM `{CB_BUCKET}`.`{scope}`.`deliveries` d
            GROUP BY d.carrier
            ORDER BY cnt DESC"""
    ))
    return rows


# ── Recent processed deliveries (for homeowner view) ──────────
def get_recent_processed_deliveries(cluster: Cluster, limit: int = 20) -> list[dict]:
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.id, d.owner_name, d.address,
                   d.status, d.scenario_type, d.carrier, d.risk_score,
                   d.knowledge_summary, d.risk_assessment,
                   d.delivery_location, d.is_ai_ready,
                   d.created_at, d.processing_status
            FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
            ORDER BY d.created_at DESC
            LIMIT $limit""",
        limit=limit,
    ))
    return rows


# ── Recent alerts ─────────────────────────────────────────────
def get_recent_alerts(cluster: Cluster, severity: str = "", limit: int = 20) -> list[dict]:
    conditions = ["1=1"]
    if severity:
        conditions.append(f"d.severity = '{severity}'")

    where = " AND ".join(conditions)
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.*
            FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`alerts` d
            WHERE {where}
            ORDER BY d.triggered_at DESC
            LIMIT {limit}"""
    ))
    return rows


# ── Filtered search ────────────────────────────────────────────
def search_deliveries(cluster: Cluster, status: str = "", scenario: str = "",
                      risk_level: str = "", limit: int = 20) -> list[dict]:
    conditions = ["1=1"]
    if status:
        conditions.append(f"d.status = '{status}'")
    if scenario:
        conditions.append(f"d.scenario_type = '{scenario}'")
    if risk_level == "critical":
        conditions.append("d.risk_score >= 0.75")
    elif risk_level == "high":
        conditions.append("d.risk_score >= 0.45 AND d.risk_score < 0.75")
    elif risk_level == "medium":
        conditions.append("d.risk_score >= 0.20 AND d.risk_score < 0.45")
    elif risk_level == "low":
        conditions.append("d.risk_score < 0.20")

    where = " AND ".join(conditions)
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.*
            FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d
            WHERE {where}
            ORDER BY d.created_at DESC
            LIMIT {limit}"""
    ))
    return rows


# ── Vector search with filters (for search tab) ────────────────
def vector_search_with_filters(cluster: Cluster, query_embedding: list[float],
                               carrier: str = "", scenario: str = "",
                               status: str = "", risk_level: str = "",
                               limit: int = 10) -> tuple[list[dict], str]:
    """Vector search with scalar filters, matching reference repo pattern.
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
    rows = list(cluster.query(
        f"""SELECT META(d).id AS doc_id, d.id, d.owner_name, d.address
            FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`deliveries` d
            WHERE META(d).id = $doc_id""",
        doc_id=doc_id,
    ))
    return rows[0] if rows else None


# ── Pipeline performance metrics ───────────────────────────────
def get_pipeline_metrics(cluster: Cluster) -> dict | None:
    """Read live pipeline metrics written by the Go event generator.
    Returns metrics dict or None if generator not running."""
    try:
        rows = list(cluster.query(
            f"""SELECT d.* FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`events` d
                WHERE META(d).id = 'pipeline_metrics'"""
        ))
        return rows[0] if rows else None
    except CouchbaseException:
        return None


def get_processing_stats(cluster: Cluster) -> dict:
    """Compare raw vs processed counts to show Eventing processing rate."""
    raw_count = 0
    proc_count = 0
    try:
        rows = list(cluster.query(
            f"""SELECT COUNT(*) AS cnt FROM `{CB_BUCKET}`.`{SCOPE_RAW}`.`deliveries` d"""
        ))
        raw_count = rows[0]["cnt"] if rows else 0
    except CouchbaseException:
        pass
    try:
        rows = list(cluster.query(
            f"""SELECT COUNT(*) AS cnt FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d"""
        ))
        proc_count = rows[0]["cnt"] if rows else 0
    except CouchbaseException:
        pass
    return {"raw_count": raw_count, "processed_count": proc_count}
