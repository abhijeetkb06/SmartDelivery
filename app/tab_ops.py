"""Tab 2 - myQ Command Center: Fleet-wide intelligence with PII-safe data."""

from __future__ import annotations
from datetime import timedelta
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from couchbase.cluster import Cluster
import couchbase_client as cb
import charts
from styles import status_badge, risk_badge, risk_bar_html, scenario_icon, scenario_friendly_name

_SEVERITY_COLORS = {"critical": "#ef4444", "high": "#f97316", "medium": "#fbbf24", "low": "#6366f1"}


def render(cluster: Cluster):
    # ── Check if generator is running for auto-refresh ──────────
    metrics = cb.get_pipeline_metrics(cluster)
    is_live = metrics is not None and metrics.get("running", False)

    # Auto-refresh every 3 seconds when generator is running
    if is_live:
        st_autorefresh(interval=3000, key="ops_autorefresh")

    # ── Section 1: Fleet Overview Stats ─────────────────────────
    # When generator is running, use its live metrics (fast) instead of slow COUNT(*) queries
    if is_live:
        total_deliveries = metrics.get("total_deliveries", 0)
        total_alerts = metrics.get("total_alerts", 0)
        proc_stats = cb.get_processing_stats(cluster)
        ai_ready = proc_stats.get("processed_count", 0)
        homes_count = 200  # Homes are pre-generated, no need to query
    else:
        counts = cb.get_counts(cluster)
        ai_ready = cb.get_ai_ready_count(cluster)
        total_deliveries = counts.get('rawdata.deliveries', 0)
        total_alerts = counts.get('rawdata.alerts', 0)
        homes_count = counts.get('rawdata.homes', 0)

    st.markdown('<div class="section-title">myQ Command Center</div>', unsafe_allow_html=True)

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
            'Chamberlain-equipped homes. Homeowner names are automatically redacted by Couchbase Eventing.</div>',
            unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-icon">&#127968;</div>
            <div class="stat-value">{homes_count:,}</div>
            <div class="stat-label">Homes Monitored</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-icon">&#128230;</div>
            <div class="stat-value">{total_deliveries:,}</div>
            <div class="stat-label">Total Deliveries</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-icon">&#128680;</div>
            <div class="stat-value">{total_alerts:,}</div>
            <div class="stat-label">Alerts Triggered</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-icon">&#129302;</div>
            <div class="stat-value">{ai_ready:,}</div>
            <div class="stat-label">AI-Ready Records</div>
        </div>""", unsafe_allow_html=True)

    # ── Section 2: Live Pipeline Performance ────────────────────
    if not is_live:
        proc_stats = cb.get_processing_stats(cluster)

    st.markdown('<div class="section-title">&#9889; Live Pipeline Performance</div>',
                unsafe_allow_html=True)

    if is_live:
        # Generator is running — show live metrics
        rate = metrics.get("actual_rate", 0)
        total_events = metrics.get("total_events_ingested", 0)
        total_deliveries = metrics.get("total_deliveries", 0)
        total_alerts = metrics.get("total_alerts", 0)
        elapsed = metrics.get("elapsed_seconds", 0)
        raw_cnt = proc_stats.get("raw_count", 0)
        proc_cnt = proc_stats.get("processed_count", 0)
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
                <div style="font-size:1.5rem;color:#6366f1;">&#10132;</div>
                <div style="text-align:center;padding:0.5rem 1rem;background:rgba(99,102,241,0.1);border-radius:8px;border:1px solid rgba(99,102,241,0.3);">
                    <div style="font-size:0.72rem;color:#6366f1;font-weight:600;">EVENTING</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;">{proc_cnt:,} enriched</div>
                    <div style="font-size:0.68rem;color:#64748b;">PII Redact + Enrich + Embed</div>
                </div>
                <div style="font-size:1.5rem;color:#6366f1;">&#10132;</div>
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
                <div style="font-size:1.5rem;color:#6366f1;">&#10132;</div>
                <div style="text-align:center;padding:0.5rem 1rem;background:rgba(99,102,241,0.1);border-radius:8px;border:1px solid rgba(99,102,241,0.3);">
                    <div style="font-size:0.72rem;color:#6366f1;font-weight:600;">EVENTING</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;">{proc_cnt:,} enriched</div>
                    <div style="font-size:0.68rem;color:#64748b;">PII Redact + Enrich + Embed</div>
                </div>
                <div style="font-size:1.5rem;color:#6366f1;">&#10132;</div>
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
    st.markdown('<div class="section-title">&#128274; Automatic Name Redaction by Couchbase Eventing</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Homeowner names are redacted so the command center '
        'never sees PII. Addresses stay intact so ops can act on incidents.</div>',
        unsafe_allow_html=True)

    # Get one raw delivery and its processed counterpart to show the redaction
    raw_deliveries = cb.get_raw_deliveries(cluster, limit=1)
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
                <div class="pii-label pii-label-raw">&#128274; Raw Data (rawdata scope)</div>
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
                    &#9888;&#65039; Contains homeowner PII &mdash; ops shouldn&#39;t see names
                </div>
            </div>
            <div class="pii-arrow">&#10132;</div>
            <div class="pii-safe-card">
                <div class="pii-label pii-label-safe">&#9989; AI-Ready Data (processeddata scope)</div>
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
                    &#9989; Name redacted + address kept for ops + AI narrative + vector embedding
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(
            '<div style="text-align:center;font-size:0.72rem;color:#475569;margin-bottom:1.5rem;">'
            'Name redaction happens <b style="color:#4ade80;">automatically</b> via Couchbase Eventing &mdash; '
            'no application code, no ETL pipeline, no middleware. '
            'Addresses are preserved so the ops team can <b>act</b> on incidents.</div>',
            unsafe_allow_html=True)

    # ── Section 4: Fleet Charts ─────────────────────────────────
    ch1, ch2, ch3 = st.columns(3)
    with ch1:
        st.markdown('<div style="font-size:0.82rem;font-weight:600;color:#94a3b8;text-align:center;'
                    'margin-bottom:0.3rem;">Delivery Scenarios</div>', unsafe_allow_html=True)
        scenario_data = cb.get_scenario_distribution(cluster, "rawdata")
        if scenario_data:
            fig = charts.create_scenario_donut(scenario_data)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with ch2:
        st.markdown('<div style="font-size:0.82rem;font-weight:600;color:#94a3b8;text-align:center;'
                    'margin-bottom:0.3rem;">Delivery Outcomes</div>', unsafe_allow_html=True)
        stats = cb.get_delivery_stats(cluster, "rawdata")
        if stats:
            fig = charts.create_status_bar(stats)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with ch3:
        st.markdown('<div style="font-size:0.82rem;font-weight:600;color:#94a3b8;text-align:center;'
                    'margin-bottom:0.3rem;">Carrier Breakdown</div>', unsafe_allow_html=True)
        carrier_data = cb.get_carrier_distribution(cluster, "rawdata")
        if carrier_data:
            fig = charts.create_carrier_pie(carrier_data)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Section 5: Alert Feed ───────────────────────────────────
    st.markdown('<div class="section-title">&#128680; Alert Feed</div>', unsafe_allow_html=True)
    fc1, fc2 = st.columns(2)
    with fc1:
        severity_filter = st.selectbox("Severity", ["All", "critical", "high", "medium", "low"],
                                       label_visibility="collapsed")
    with fc2:
        alert_limit = st.selectbox("Show", [10, 20, 50], index=0, label_visibility="collapsed")
    severity = "" if severity_filter == "All" else severity_filter
    alerts = cb.get_recent_alerts(cluster, severity=severity, limit=alert_limit)
    if alerts:
        for alert in alerts:
            _render_alert_card(alert)
    else:
        st.info("No alerts found matching the filter.")

    # ── Section 6: Delivery Grid ────────────────────────────────
    st.markdown('<div class="section-title">&#128230; Recent Deliveries (PII-Safe)</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        status_filter = st.selectbox("Status", ["All", "completed_success", "completed_risk", "failed", "suspicious"])
    with c2:
        scenario_filter = st.selectbox("Scenario", ["All", "happy_path", "front_door_misdelivery",
                                                      "package_behind_car", "door_stuck_open",
                                                      "no_package_placed", "delivery_timeout", "theft_suspicious"])
    with c3:
        risk_filter = st.selectbox("Risk Level", ["All", "critical", "high", "medium", "low"])
    results = cb.search_deliveries(cluster,
        status="" if status_filter == "All" else status_filter,
        scenario="" if scenario_filter == "All" else scenario_filter,
        risk_level="" if risk_filter == "All" else risk_filter, limit=15)
    if results:
        for row in results:
            _render_delivery_row(row)
    else:
        st.info("No deliveries match the selected filters.")


def _render_alert_card(alert: dict):
    severity = alert.get("severity", "medium")
    color = _SEVERITY_COLORS.get(severity, "#6366f1")
    message = alert.get("message", "")
    address = alert.get("address", "")
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


def _render_delivery_row(row: dict):
    scenario = scenario_friendly_name(row.get("scenario_type", ""))
    s_icon = scenario_icon(row.get("scenario_type", ""))
    risk_score = row.get("risk_score", 0)
    # Name comes from processeddata (redacted), address is intact
    st.markdown(f"""<div class="glass-card" style="padding:0.8rem 1rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-weight:600;color:#e2e8f0;">{row.get('id','')}</span>
            {status_badge(row.get('status',''))}</div>
            <div style="display:flex;align-items:center;gap:0.8rem;font-size:0.82rem;color:#94a3b8;">
                <span>{s_icon} {scenario}</span>
                <span>&#128666; {row.get('carrier','')}</span>
                <span>&#9889; {risk_score:.0%} {risk_bar_html(risk_score)}</span>
            </div></div>
        <div style="font-size:0.78rem;color:#64748b;margin-top:0.25rem;">
            {row.get('owner_name','')} &mdash; {row.get('address','')}</div>
    </div>""", unsafe_allow_html=True)
