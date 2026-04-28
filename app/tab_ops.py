"""Tab 2 - myQ Command Center: Fleet-wide intelligence with PII-safe data."""

from __future__ import annotations
from datetime import timedelta
import logging
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time

import streamlit as st
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, ClusterTimeoutOptions
from couchbase.exceptions import CouchbaseException

import couchbase_client as cb
from config import (CB_CONN_STR, CB_USERNAME, CB_PASSWORD, CB_BUCKET, SCOPE_PROCESSED,
                     GENERATOR_RATE, GENERATOR_WORKERS, GENERATOR_BATCH, GENERATOR_COUNT,
                     HOMES_COUNT)
from styles import icon

_SEVERITY_COLORS = {"critical": "#ef4444", "high": "#f97316", "medium": "#fbbf24", "low": "#6366f1"}
_GEN_BIN = Path(__file__).resolve().parent.parent / "event-generator" / "smart-delivery-gen"
_log = logging.getLogger(__name__)

# ── Background Vector Index Watcher ─────────────────────────────
_vector_watcher_running = False  # module-level flag to prevent duplicate threads


def _vector_index_watcher():
    """Background thread: waits for embeddings, then creates the vector index.

    Flow:
      1. Sleep 30s (let eventing pipeline start processing)
      2. Poll AI-ready doc count every 15s
      3. Once >= 200, create IVF,SQ8 vector index
      4. Exit
    """
    global _vector_watcher_running
    try:
        _log.info("[VectorWatcher] Waiting 30s for eventing pipeline to generate embeddings...")
        time.sleep(30)

        # Create an independent cluster connection for this thread
        auth = PasswordAuthenticator(CB_USERNAME, CB_PASSWORD)
        cluster = Cluster(
            CB_CONN_STR,
            ClusterOptions(auth, timeout_options=ClusterTimeoutOptions(
                query_timeout=timedelta(seconds=120),
            )),
        )
        cluster.wait_until_ready(timedelta(seconds=15))

        # Poll until we have enough embeddings (max ~10 minutes)
        threshold = cb.VECTOR_INDEX_THRESHOLD
        for attempt in range(40):  # 40 * 15s = 10 min max
            # Check if index already exists and is online
            try:
                rows = list(cluster.query(
                    "SELECT state FROM system:indexes WHERE name = 'idx_delivery_vectors'"
                ))
                if rows and rows[0].get("state") == "online":
                    _log.info("[VectorWatcher] Vector index already online. Exiting.")
                    return
            except CouchbaseException:
                pass

            # Check AI-ready count
            try:
                rows = list(cluster.query(
                    f"SELECT COUNT(*) AS cnt FROM `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries` d "
                    f"WHERE d.is_ai_ready = true"
                ))
                ai_ready = rows[0]["cnt"] if rows else 0
            except CouchbaseException:
                ai_ready = 0

            _log.info("[VectorWatcher] AI-ready docs: %d/%d", ai_ready, threshold)

            if ai_ready >= threshold:
                # Drop broken index if exists
                try:
                    list(cluster.query(
                        f"DROP INDEX `idx_delivery_vectors` ON "
                        f"`{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries`"
                    ))
                    time.sleep(3)
                except CouchbaseException:
                    pass

                # Create the vector index
                try:
                    list(cluster.query(f"""
                        CREATE VECTOR INDEX `idx_delivery_vectors`
                        ON `{CB_BUCKET}`.`{SCOPE_PROCESSED}`.`deliveries`(embedding VECTOR)
                        WITH {{"dimension": 1536, "similarity": "COSINE", "description": "IVF,SQ8"}}
                    """))
                    _log.info("[VectorWatcher] Vector index created! Will build in background.")
                except CouchbaseException as e:
                    if "already exists" not in str(e).lower():
                        _log.warning("[VectorWatcher] Index creation failed: %s", e)
                return

            time.sleep(15)

        _log.warning("[VectorWatcher] Timed out waiting for enough embeddings.")
    finally:
        _vector_watcher_running = False


def _start_vector_index_watcher():
    """Spawn the vector index watcher thread if not already running."""
    global _vector_watcher_running
    if _vector_watcher_running:
        return
    _vector_watcher_running = True
    t = threading.Thread(target=_vector_index_watcher, daemon=True, name="VectorIndexWatcher")
    t.start()
    _log.info("[VectorWatcher] Background thread started.")


def _start_generator(cluster: Cluster) -> bool:
    """Launch Go event generator as a background process.

    Auto-builds the binary if missing and Go is installed.
    Returns True on successful launch, False on failure.
    """
    # Auto-build if binary is missing
    if not _GEN_BIN.exists():
        if not shutil.which("go"):
            st.session_state["gen_error"] = (
                "Go is not installed and the event generator binary is missing. "
                "Install Go 1.21+ from https://go.dev/dl/ then restart the dashboard, "
                "or build manually: `cd event-generator && go build -o smart-delivery-gen .`"
            )
            return False
        with st.spinner("Compiling event generator (first run only)..."):
            result = subprocess.run(
                ["go", "build", "-o", "smart-delivery-gen", "."],
                cwd=_GEN_BIN.parent,
                capture_output=True, text=True, timeout=120,
            )
        if result.returncode != 0 or not _GEN_BIN.exists():
            st.session_state["gen_error"] = f"Go build failed: {result.stderr.strip()}"
            return False

    st.session_state.pop("gen_error", None)
    try:
        proc = subprocess.Popen(
            [str(_GEN_BIN), "--continuous",
             "--rate", str(GENERATOR_RATE), "--workers", str(GENERATOR_WORKERS),
             "--batch", str(GENERATOR_BATCH), "--count", str(GENERATOR_COUNT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        st.session_state["gen_pid"] = proc.pid
    except Exception as e:
        st.session_state["gen_error"] = f"Failed to start event generator: {e}"
        return False
    # Kick off background vector index creation (waits 30s, then auto-creates when ready)
    _start_vector_index_watcher()
    return True


def _stop_generator(cluster: Cluster):
    """Kill the generator process reliably and clear the running flag in Couchbase.

    Strategy:
      1. Try killing by stored PID (process group SIGTERM, then SIGKILL).
      2. Fallback: pkill by binary name to catch orphaned processes.
      3. Clear the running flag in Couchbase so the UI stops treating it as live.
    """
    pid = st.session_state.get("gen_pid")

    # 1. Kill by stored PID
    if pid:
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
            # Give it a moment to shut down, then force-kill if still alive
            time.sleep(0.5)
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # already dead, good
        except (ProcessLookupError, PermissionError, OSError):
            pass

    # 2. Fallback: kill any remaining instances by binary name
    try:
        subprocess.run(
            ["pkill", "-9", "-f", "smart-delivery-gen"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass

    st.session_state.pop("gen_pid", None)

    # 3. Clear the running flag in Couchbase so the UI stops treating it as live
    try:
        col = cluster.bucket("smartdelivery").scope("rawdata").collection("events")
        col.upsert("pipeline_metrics", {"running": False})
    except Exception:
        pass


def render(cluster: Cluster):
    # ── Check if generator is running for auto-refresh ──────────
    metrics = cb.get_pipeline_metrics(cluster)
    is_live = metrics is not None and metrics.get("running", False)

    # ── Section 1: Fleet Overview Stats ─────────────────────────
    # Cache stats in session_state with a 5-second TTL so Streamlit reruns
    # don't fire 12+ N1QL queries each time.
    now = time.time()
    cache = st.session_state.get("_ops_stats_cache")
    cache_fresh = cache is not None and (now - cache.get("_ts", 0)) < 5

    if is_live:
        total_deliveries = metrics.get("total_deliveries", 0)
        total_alerts = metrics.get("total_alerts", 0)
        if cache_fresh and "proc_stats" in cache:
            proc_stats = cache["proc_stats"]
        else:
            proc_stats = cb.get_processing_stats(cluster)
            st.session_state["_ops_stats_cache"] = {"proc_stats": proc_stats, "_ts": now}
        ai_ready = proc_stats.get("processed_count", 0)
        homes_count = HOMES_COUNT
    else:
        if cache_fresh and "counts" in cache:
            counts = cache["counts"]
            ai_ready = cache["ai_ready"]
            proc_stats = cache["proc_stats"]
        else:
            counts = cb.get_counts(cluster)
            ai_ready = cb.get_ai_ready_count(cluster)
            proc_stats = cb.get_processing_stats(cluster)
            st.session_state["_ops_stats_cache"] = {
                "counts": counts, "ai_ready": ai_ready,
                "proc_stats": proc_stats, "_ts": now,
            }
        total_deliveries = counts.get('rawdata.deliveries', 0)
        total_alerts = counts.get('rawdata.alerts', 0)
        homes_count = HOMES_COUNT

    st.markdown('<div class="section-title">myQ Command Center</div>', unsafe_allow_html=True)

    # ── Generator Start / Stop control ───────────────────────────
    ctrl_col, status_col = st.columns([1, 3])
    with ctrl_col:
        if is_live:
            if st.button("Stop Event Stream", type="secondary", use_container_width=True):
                _stop_generator(cluster)
                st.session_state.pop("gen_starting", None)
                st.session_state.pop("gen_error", None)
                st.rerun()
        else:
            if st.button("Start Event Stream", type="primary", use_container_width=True):
                if _start_generator(cluster):
                    # Flag so auto-refresh kicks in before first metrics doc arrives
                    st.session_state["gen_starting"] = True
                    st.rerun()
    with status_col:
        if is_live:
            rate = metrics.get("actual_rate", 0) or 0
            pid = st.session_state.get("gen_pid", "?")
            st.markdown(
                f'<div style="padding:0.5rem 0;font-size:0.82rem;color:#4ade80;">'
                f'&#9679; LIVE &mdash; Streaming at {rate:,.0f} ops/sec '
                f'(PID {pid})</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="padding:0.5rem 0;font-size:0.82rem;color:#64748b;">'
                f'Click <b>Start Event Stream</b> to begin ingesting delivery events at {GENERATOR_RATE:,}/sec.</div>',
                unsafe_allow_html=True)

    # Show persistent error if generator failed to start
    gen_error = st.session_state.get("gen_error")
    if gen_error:
        st.error(gen_error)

    # Show LIVE indicator when generator is running
    if is_live:
        st.markdown(
            '<div class="section-subtitle">Fleet-wide delivery intelligence &mdash; '
            '<span style="color:#4ade80;">&#9679; LIVE</span> '
            'Event stream active (auto-refreshes every 3s)</div>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="section-subtitle">Fleet-wide delivery intelligence across all '
            'myQ-equipped homes. Homeowner names are automatically redacted by Couchbase Eventing.</div>',
            unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-icon">{icon("home", size=22, color="#818cf8")}</div>
            <div class="stat-value">{homes_count:,}</div>
            <div class="stat-label">Homes Monitored</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-icon">{icon("package", size=22, color="#818cf8")}</div>
            <div class="stat-value">{total_deliveries:,}</div>
            <div class="stat-label">Total Deliveries</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-icon">{icon("shield-alert", size=22, color="#818cf8")}</div>
            <div class="stat-value">{total_alerts:,}</div>
            <div class="stat-label">Alerts Triggered</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-icon">{icon("cpu", size=22, color="#818cf8")}</div>
            <div class="stat-value">{ai_ready:,}</div>
            <div class="stat-label">AI-Ready Records</div>
        </div>""", unsafe_allow_html=True)

    # ── Section 2: Live Pipeline Performance ────────────────────
    # proc_stats already loaded above (cached)

    st.markdown(f'<div class="section-title">{icon("zap", size=18, color="#fbbf24")} Live Pipeline Performance</div>',
                unsafe_allow_html=True)

    if is_live:
        # Generator is running — show live metrics
        rate = metrics.get("actual_rate", 0) or 0
        total_events = metrics.get("total_events_ingested", 0) or 0
        total_deliveries = metrics.get("total_deliveries", 0) or 0
        total_alerts = metrics.get("total_alerts", 0) or 0
        elapsed = metrics.get("elapsed_seconds", 0) or 0
        raw_cnt = proc_stats.get("raw_count", 0) or 0
        proc_cnt = proc_stats.get("processed_count", 0) or 0
        processing_pct = (proc_cnt / raw_cnt * 100) if raw_cnt > 0 else 0

        st.markdown(
            '<div class="section-subtitle">Real-time event ingestion &mdash; '
            '<span style="color:#4ade80;">&#9679; LIVE</span> '
            '(auto-refreshes every 3s)</div>',
            unsafe_allow_html=True)

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.markdown(f"""<div class="stat-card" style="border-left:4px solid #4ade80;">
                <div class="stat-value" style="color:#4ade80;">{rate:.0f}</div>
                <div class="stat-label">Ops/sec</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="stat-card" style="border-left:4px solid #6366f1;">
                <div class="stat-value" style="color:#6366f1;">{total_events:,}</div>
                <div class="stat-label">Total Events</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="stat-card" style="border-left:4px solid #f97316;">
                <div class="stat-value" style="color:#f97316;">{total_deliveries:,}</div>
                <div class="stat-label">Deliveries Generated</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""<div class="stat-card" style="border-left:4px solid #ef4444;">
                <div class="stat-value" style="color:#ef4444;">{total_alerts:,}</div>
                <div class="stat-label">Alerts Triggered</div>
            </div>""", unsafe_allow_html=True)
        with m5:
            st.markdown(f"""<div class="stat-card" style="border-left:4px solid #22c55e;">
                <div class="stat-value" style="color:#22c55e;">{processing_pct:.0f}%</div>
                <div class="stat-label">Eventing Processed</div>
            </div>""", unsafe_allow_html=True)

        # Pipeline flow visualization (live)
        st.markdown(f"""<div class="glass-card" style="padding:1rem;margin-top:0.5rem;">
            <div style="display:flex;align-items:center;justify-content:center;gap:1rem;flex-wrap:wrap;">
                <div style="text-align:center;padding:0.5rem 1rem;background:rgba(249,115,22,0.1);border-radius:8px;border:1px solid rgba(249,115,22,0.3);">
                    <div style="font-size:0.72rem;color:#f97316;font-weight:600;">INGEST</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;">{rate:.0f} ops/s</div>
                    <div style="font-size:0.68rem;color:#64748b;">Go Event Generator</div>
                </div>
                <div style="line-height:1;">{icon("arrow-right", size=24, color="#6366f1")}</div>
                <div style="text-align:center;padding:0.5rem 1rem;background:rgba(99,102,241,0.1);border-radius:8px;border:1px solid rgba(99,102,241,0.3);">
                    <div style="font-size:0.72rem;color:#6366f1;font-weight:600;">EVENTING</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;">{proc_cnt:,} enriched</div>
                    <div style="font-size:0.68rem;color:#64748b;">PII Redact + Enrich + Embed</div>
                </div>
                <div style="line-height:1;">{icon("arrow-right", size=24, color="#6366f1")}</div>
                <div style="text-align:center;padding:0.5rem 1rem;background:rgba(34,197,94,0.1);border-radius:8px;border:1px solid rgba(34,197,94,0.3);">
                    <div style="font-size:0.72rem;color:#22c55e;font-weight:600;">AI-READY</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;">{ai_ready:,} records</div>
                    <div style="font-size:0.68rem;color:#64748b;">Vector Index + RAG</div>
                </div>
            </div>
            <div style="text-align:center;margin-top:0.5rem;font-size:0.68rem;color:#4ade80;">
                Elapsed: {elapsed:.0f}s &mdash; Couchbase Eventing processes events in real-time as they arrive</div>
        </div>""", unsafe_allow_html=True)

    else:
        # Generator not running — show static pipeline stats
        raw_cnt = proc_stats.get("raw_count", 0)
        proc_cnt = proc_stats.get("processed_count", 0)
        processing_pct = (proc_cnt / raw_cnt * 100) if raw_cnt > 0 else 0

        st.markdown(
            '<div class="section-subtitle">Run the event generator with '
            '<code>--continuous --rate 500</code> to stream live events and see real-time throughput.</div>',
            unsafe_allow_html=True)

        st.markdown(f"""<div class="glass-card" style="padding:1rem;">
            <div style="display:flex;align-items:center;justify-content:center;gap:1rem;flex-wrap:wrap;">
                <div style="text-align:center;padding:0.5rem 1rem;background:rgba(249,115,22,0.1);border-radius:8px;border:1px solid rgba(249,115,22,0.3);">
                    <div style="font-size:0.72rem;color:#f97316;font-weight:600;">INGEST</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;">{raw_cnt:,} deliveries</div>
                    <div style="font-size:0.68rem;color:#64748b;">Raw Events (rawdata scope)</div>
                </div>
                <div style="line-height:1;">{icon("arrow-right", size=24, color="#6366f1")}</div>
                <div style="text-align:center;padding:0.5rem 1rem;background:rgba(99,102,241,0.1);border-radius:8px;border:1px solid rgba(99,102,241,0.3);">
                    <div style="font-size:0.72rem;color:#6366f1;font-weight:600;">EVENTING</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;">{proc_cnt:,} enriched</div>
                    <div style="font-size:0.68rem;color:#64748b;">PII Redact + Enrich + Embed</div>
                </div>
                <div style="line-height:1;">{icon("arrow-right", size=24, color="#6366f1")}</div>
                <div style="text-align:center;padding:0.5rem 1rem;background:rgba(34,197,94,0.1);border-radius:8px;border:1px solid rgba(34,197,94,0.3);">
                    <div style="font-size:0.72rem;color:#22c55e;font-weight:600;">AI-READY</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;">{ai_ready:,} records</div>
                    <div style="font-size:0.68rem;color:#64748b;">Vector Index + RAG</div>
                </div>
            </div>
            <div style="text-align:center;margin-top:0.75rem;font-size:0.72rem;color:#64748b;">
                {processing_pct:.0f}% of raw deliveries processed by Eventing &mdash;
                run <code>./smart-delivery-gen --continuous --rate 500 --workers 40</code> to stream live events</div>
        </div>""", unsafe_allow_html=True)

    # ── Section 3: PII Redaction Showcase ───────────────────────
    st.markdown(f'<div class="section-title">{icon("lock", size=18, color="#818cf8")} Automatic Name Redaction by Couchbase Eventing</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Homeowner names are redacted so the command center '
        'never sees PII. Addresses stay intact so ops can act on incidents.</div>',
        unsafe_allow_html=True)

    # Get one raw delivery and its processed counterpart to show the redaction
    try:
        raw_deliveries = cb.get_raw_deliveries(cluster, limit=1)
    except Exception:
        raw_deliveries = []
    if raw_deliveries:
        raw = raw_deliveries[0]
        doc_id = raw.get("doc_id", raw.get("id", ""))
        proc = cb.get_delivery_by_id(cluster, "processeddata", doc_id)

        raw_name = raw.get("owner_name", "N/A")
        raw_address = raw.get("address", "N/A")
        proc_name = proc.get("owner_name", "R*******") if proc else "R*******"
        proc_address = proc.get("address", "N/A") if proc else "N/A"

        st.markdown(f"""<div class="pii-comparison">
            <div class="pii-raw-card">
                <div class="pii-label pii-label-raw">{icon("unlock", size=14, color="#f87171")} Raw Data (rawdata scope)</div>
                <div class="pii-field">
                    <span class="pii-field-name">Homeowner</span>
                    <span class="pii-field-value-raw">{raw_name}</span>
                </div>
                <div class="pii-field">
                    <span class="pii-field-name">Address</span>
                    <span style="font-size:0.85rem;color:#94a3b8;">{raw_address}</span>
                </div>
                <div class="pii-field">
                    <span class="pii-field-name">Delivery ID</span>
                    <span style="font-size:0.85rem;color:#94a3b8;">{raw.get('id','')}</span>
                </div>
                <div class="pii-field">
                    <span class="pii-field-name">Carrier</span>
                    <span style="font-size:0.85rem;color:#94a3b8;">{raw.get('carrier','')}</span>
                </div>
                <div style="margin-top:0.75rem;padding-top:0.5rem;border-top:1px solid rgba(239,68,68,0.15);font-size:0.72rem;color:#f87171;">
                    {icon("alert-triangle", size=13, color="#f87171")} Contains homeowner PII &mdash; ops shouldn&#39;t see names
                </div>
            </div>
            <div class="pii-arrow">{icon("arrow-right", size=24, color="#6366f1")}</div>
            <div class="pii-safe-card">
                <div class="pii-label pii-label-safe">{icon("check-circle", size=14, color="#4ade80")} AI-Ready Data (processeddata scope)</div>
                <div class="pii-field">
                    <span class="pii-field-name">Homeowner</span>
                    <span class="pii-field-value-safe">{proc_name}</span>
                </div>
                <div class="pii-field">
                    <span class="pii-field-name">Address</span>
                    <span style="font-size:0.85rem;color:#94a3b8;">{proc_address}</span>
                </div>
                <div class="pii-field">
                    <span class="pii-field-name">Delivery ID</span>
                    <span style="font-size:0.85rem;color:#94a3b8;">{raw.get('id','')}</span>
                </div>
                <div class="pii-field">
                    <span class="pii-field-name">Carrier</span>
                    <span style="font-size:0.85rem;color:#94a3b8;">{raw.get('carrier','')}</span>
                </div>
                <div style="margin-top:0.75rem;padding-top:0.5rem;border-top:1px solid rgba(34,197,94,0.15);font-size:0.72rem;color:#4ade80;">
                    {icon("check-circle", size=13, color="#4ade80")} Name redacted + address kept for ops + AI narrative + vector embedding
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(
            '<div style="text-align:center;font-size:0.72rem;color:#475569;margin-bottom:1.5rem;">'
            'Name redaction happens <b style="color:#4ade80;">automatically</b> via Couchbase Eventing &mdash; '
            'no application code, no ETL pipeline, no middleware. '
            'Addresses are preserved so the ops team can <b>act</b> on incidents.</div>',
            unsafe_allow_html=True)

    # ── Section 4: Alert Feed ───────────────────────────────────
    st.markdown(f'<div class="section-title">{icon("shield-alert", size=18, color="#ef4444")} Alert Feed</div>', unsafe_allow_html=True)
    fc1, fc2 = st.columns(2)
    with fc1:
        severity_filter = st.selectbox("Severity", ["All", "critical", "high", "medium", "low"],
                                       label_visibility="collapsed")
    with fc2:
        alert_limit = st.selectbox("Show", [10, 20, 50], index=0, label_visibility="collapsed")
    severity = "" if severity_filter == "All" else severity_filter
    alert_cache_key = f"_alerts_{severity}_{alert_limit}"
    alert_cache = st.session_state.get(alert_cache_key)
    if alert_cache and (now - alert_cache.get("_ts", 0)) < 5:
        alerts = alert_cache["data"]
    else:
        alerts = cb.get_recent_alerts(cluster, severity=severity, limit=alert_limit)
        st.session_state[alert_cache_key] = {"data": alerts, "_ts": now}
    if alerts:
        for alert in alerts:
            _render_alert_card(alert)
    else:
        st.info("No alerts found matching the filter.")


def _render_alert_card(alert: dict):
    severity = alert.get("severity", "medium")
    color = _SEVERITY_COLORS.get(severity, "#6366f1")
    message = alert.get("message", "") or ""
    address = alert.get("address", "") or ""
    alert_type = alert.get("alert_type", "").replace("_", " ").title()
    triggered = alert.get("triggered_at", "")
    time_str = triggered[11:16] if len(triggered) >= 16 else triggered
    st.markdown(f"""<div class="ops-alert-card">
        <div class="ops-alert-severity" style="background:{color};box-shadow:0 0 6px {color}40;"></div>
        <div style="flex:1;min-width:0;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div><span style="font-weight:600;color:{color};font-size:0.78rem;text-transform:uppercase;">{severity}</span>
                <span style="color:#e2e8f0;font-weight:500;font-size:0.85rem;margin-left:0.5rem;">{alert_type}</span></div>
                <span style="color:#64748b;font-size:0.72rem;">{time_str}</span>
            </div>
            <div style="color:#94a3b8;font-size:0.78rem;margin-top:0.15rem;">
                {address} &mdash; {message[:80]}{"..." if len(message) > 80 else ""}</div>
        </div></div>""", unsafe_allow_html=True)
