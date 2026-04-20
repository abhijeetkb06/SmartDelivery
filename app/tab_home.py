"""Tab 1 - My myQ: Homeowner view with smart delivery intelligence."""

from __future__ import annotations
import streamlit as st
from couchbase.cluster import Cluster
import couchbase_client as cb
import charts
from styles import status_badge, risk_badge, risk_bar_html, scenario_icon, scenario_friendly_name, icon


def render(cluster: Cluster):
    # Homeowner view: query RAWDATA so they see their full name & address
    try:
        deliveries = cb.get_raw_deliveries(cluster, limit=100)
    except Exception:
        st.warning("Delivery data is still loading. Please wait a moment and refresh.")
        return

    # Build diverse subsets — variety of scenarios so the demo looks realistic
    alert_pool = [d for d in deliveries if d.get("risk_score", 0) >= 0.45]
    alert_deliveries = _diverse_pick(alert_pool, total=5)
    recent_deliveries = _diverse_pick(deliveries, total=6)

    # ── Section 1: myQ Device Card ──────────────────────────────
    latest = deliveries[0] if deliveries else None
    door_closed = True
    if latest and latest.get("scenario_type") == "door_stuck_open":
        door_closed = False
    door_status = "Closed" if door_closed else "Stuck Open"
    door_icon = icon("lock", size=24, color="#22c55e") if door_closed else icon("alert-triangle", size=24, color="#f59e0b")
    dot_cls = "" if door_closed else "open"

    st.markdown(f"""<div class="myq-device-card">
        <div class="myq-device-header">
            <div>
                <div class="myq-device-name">My Devices</div>
                <div class="myq-device-location">Home Garage Door</div>
            </div>
            <div class="myq-door-icon">{door_icon}</div>
        </div>
        <div class="myq-door-status">
            <div class="myq-door-status-dot {dot_cls}"></div>
            <div class="myq-door-status-text">{door_status}</div>
        </div>
        <div class="myq-delivery-banner">
            <div class="myq-delivery-banner-title">{icon("package", size=14, color="rgba(255,255,255,0.8)")} Delivery Intelligence</div>
            <div class="myq-delivery-banner-text">
                {_latest_delivery_text(latest)}
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── Section 2: Before vs After (THE SELL) ───────────────────
    st.markdown('<div class="section-title">What if myQ could understand your deliveries?</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Today, myQ tells you "garage door opened." '
        'With Couchbase, it tells you what happened and whether you need to act.</div>',
        unsafe_allow_html=True)

    st.markdown(charts.create_notification_comparison_html(latest), unsafe_allow_html=True)

    # ── Code Spotlight: How Couchbase Intelligence Works ──────────
    with st.expander("View Couchbase Eventing Pipeline", expanded=False):
        if latest:
            doc_id = latest.get("doc_id", latest.get("id", ""))
            carrier = latest.get("carrier", "Unknown")
            scenario = latest.get("scenario_type", "")
            owner = latest.get("owner_name", "")
            address = latest.get("address", "")
            risk = latest.get("risk_score", 0)
            location = latest.get("delivery_location", "").replace("_", " ")
            factors = latest.get("risk_factors", [])
            timeline = latest.get("event_timeline", [])

            # Fetch the processed (enriched) counterpart to show real intelligence
            proc = cb.get_delivery_by_id(cluster, "processeddata", doc_id)
            knowledge = proc.get("knowledge_summary", "") if proc else ""
            proc_name = proc.get("owner_name", "") if proc else ""
            risk_assessment = proc.get("risk_assessment", {}) if proc else {}

            # Redacted name preview
            parts = owner.split() if owner else []
            redacted = proc_name if proc_name else (
                " ".join(p[0].upper() + "***" for p in parts if p) if parts else "R*******"
            )

            # ── Step 1: Eventing (what fires first in the data flow) ──
            st.markdown("#### Step 1: Couchbase Eventing (Server-Side, Automatic)")
            st.markdown(
                f"When this `{carrier}` delivery landed in `rawdata.deliveries`, "
                f"the **DeliveryKnowledgePipeline** eventing function fired automatically "
                f"on the server — no application code involved:")
            st.code(f"""// Fires on every mutation in rawdata.deliveries
function OnUpdate(doc, meta) {{
    // 1. Redact PII (owner name only — address kept for ops)
    var redactedName = redactName(doc.owner_name);
    //    "{owner}" → "{redacted}"

    // 2. Correlate sensor events into a knowledge narrative
    var narrative = buildNarrative(doc, redactedName);
    //    Walks through {len(timeline)} events: {', '.join(e.get('event_type','') for e in timeline[:4])}...
    //    Builds: "Delivery {doc_id} ... Event sequence: 1. {timeline[0].get('summary','') if timeline else '...'} ..."

    // 3. Assess risk from detected risk_factors
    var riskAssessment = buildRiskAssessment(doc);
    //    Input factors: [{', '.join(factors) if factors else 'none'}]
    //    Output: {{ level: "{risk_assessment.get('level','')}", score: {risk}, recommendations: [...] }}

    // 4. Write enriched doc to processeddata.deliveries
    enriched.owner_name = redactedName;          // PII redacted
    enriched.knowledge_summary = narrative;       // structured intelligence
    enriched.risk_assessment = riskAssessment;    // actionable risk data
    enriched.embedding_text = buildEmbeddingText(enriched);
    dst[meta.id] = enriched;
}}""", language="javascript")

            # ── Step 2: What eventing produced ──
            st.markdown("---")
            st.markdown("#### Step 2: Eventing Output (knowledge_summary)")
            st.markdown(
                f"The `buildNarrative()` function correlated **{len(timeline)} raw sensor events** "
                f"into this structured knowledge narrative stored in `processeddata.deliveries`:")

            if timeline:
                st.markdown("**Input: Raw sensor events**")
                for i, evt in enumerate(timeline, 1):
                    evt_type = evt.get("event_type", "")
                    summary = evt.get("summary", "")
                    evt_loc = evt.get("location", "")
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:0.5rem;padding:0.3rem 0;'
                        f'border-bottom:1px solid rgba(100,116,139,0.1);">'
                        f'<span style="color:#6366f1;font-weight:600;min-width:1.5rem;">{i}.</span>'
                        f'<code style="font-size:0.75rem;color:#fbbf24;min-width:10rem;">{evt_type}</code>'
                        f'<span style="font-size:0.82rem;color:#cbd5e1;">{summary}</span>'
                        f'<span style="font-size:0.72rem;color:#64748b;margin-left:auto;">{evt_loc}</span>'
                        f'</div>', unsafe_allow_html=True)

            if factors:
                st.markdown("")
                st.markdown(f"**Risk factors detected:** `{'`, `'.join(factors)}`")

            if knowledge:
                st.markdown("")
                st.markdown(
                    f'<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);'
                    f'border-radius:8px;padding:0.75rem 1rem;margin:0.5rem 0;">'
                    f'<div style="font-size:0.72rem;color:#818cf8;font-weight:600;margin-bottom:0.25rem;">'
                    f'OUTPUT: knowledge_summary (stored in Couchbase)</div>'
                    f'<div style="font-size:0.82rem;color:#cbd5e1;line-height:1.5;">{knowledge}</div>'
                    f'</div>', unsafe_allow_html=True)

            # ── Step 3: Query that powers the intelligence panel ──
            st.markdown("---")
            st.markdown("#### Step 3: Read Enriched Data (Sub-Millisecond)")
            st.markdown(
                "The app reads the enriched document from `processeddata.deliveries` using a "
                "KV GET and transforms the structured data into the user-friendly alert:")
            st.markdown(f"""<div class="query-box">-- KV GET: instant point lookup by document ID
GET `smartdelivery`.`processeddata`.`deliveries`.`{doc_id}`

-- Returns enriched fields written by Eventing:
--   knowledge_summary: "{knowledge[:100]}{"..." if len(knowledge) > 100 else ""}"
--   owner_name: "{redacted}" (PII redacted)
--   risk_assessment: {{ level: "{risk_assessment.get('level','')}", score: {risk} }}
--   scenario_type: "{scenario}"
--   carrier: "{carrier}"
--   is_ai_ready: true (embedding generated)
-- Latency: &lt;1ms (KV SDK direct lookup)</div>""", unsafe_allow_html=True)

            st.markdown("")
            smart_msg = _smart_summary(latest)
            st.markdown(
                f'<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.25);'
                f'border-radius:8px;padding:0.75rem 1rem;margin:0.5rem 0;">'
                f'<div style="font-size:0.72rem;color:#4ade80;font-weight:600;margin-bottom:0.25rem;">'
                f'SMART DELIVERY ALERT (displayed to homeowner)</div>'
                f'<div style="font-size:0.88rem;color:#e2e8f0;line-height:1.5;">{smart_msg}</div>'
                f'</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### Eventing Pipeline Flow")
        st.markdown("""
        ```
        1. RAW DELIVERY MUTATION
           rawdata.deliveries ← Go Event Generator (5,000 ops/sec)
                    │
                    ▼
        2. DeliveryKnowledgePipeline (Eventing Function #1)
           • PII redaction: owner_name → masked
           • Narrative generation from event_timeline
           • Risk assessment from risk_factors
           • Write → processeddata.deliveries
                    │
                    ▼
        3. VectorEmbeddingPipeline (Eventing Function #2)
           • Builds embedding_text from narrative + metadata
           • Calls OpenAI text-embedding-3-small → 1,536-dim vector
           • Marks document as AI-ready
                    │
                    ▼
        4. INTELLIGENCE READY
           • Smart notifications (this screen)
           • Vector Search & AI Copilot (RAG)
           • All automated — zero application code
        ```
        """)

    st.markdown(
        '<div style="text-align:center;font-size:0.72rem;color:#475569;margin-bottom:1.5rem;">'
        'The smart insight on the right is generated <b style="color:#4ade80;">automatically</b> '
        'by Couchbase Eventing &mdash; turning raw events into intelligence, no application code needed</div>',
        unsafe_allow_html=True)

    # ── Section 3: Active Alerts ────────────────────────────────
    if alert_deliveries:
        st.markdown(f'<div class="section-title">{icon("shield-alert", size=18, color="#ef4444")} Active Alerts</div>',
                    unsafe_allow_html=True)
        for d in alert_deliveries:
            scenario = scenario_friendly_name(d.get("scenario_type", ""))
            s_icon = scenario_icon(d.get("scenario_type", ""))
            # Raw data may not have risk_assessment; generate recommendation from risk_factors
            ra = d.get("risk_assessment") or {}
            rec = ra.get("recommendations") if ra else None
            if not rec:
                rec = _recommendations_from_factors(d.get("risk_factors", []))
            rec_text = rec[0] if rec else "Check your security camera."
            is_suspicious = d.get("status") == "suspicious"
            banner_cls = "alert-banner-critical" if is_suspicious else "alert-banner-warning"

            st.markdown(f"""<div class="alert-banner {banner_cls}">
                <div class="alert-banner-icon">{s_icon}</div>
                <div class="alert-banner-content">
                    <div class="alert-banner-title">{scenario} &mdash; {d.get('address','')}</div>
                    <div class="alert-banner-desc">{rec_text}</div>
                </div>
                <div style="flex-shrink:0;text-align:right;">
                    <div style="font-size:0.75rem;font-weight:600;color:#ef4444;">{d.get('risk_score',0):.0%} RISK</div>
                    <div style="font-size:0.68rem;color:#64748b;">{d.get('carrier','')}</div>
                </div>
            </div>""", unsafe_allow_html=True)

    # ── Section 4: Recent Delivery Activity ─────────────────────
    st.markdown(f'<div class="section-title">{icon("package", size=18, color="#818cf8")} Recent Delivery Activity</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Smart notifications powered by AI-generated delivery narratives. '
        'Each summary is created automatically by Couchbase Eventing.</div>',
        unsafe_allow_html=True)

    if not deliveries:
        st.info("No deliveries found. Make sure the event generator has produced data.")
        return

    for d in recent_deliveries:
        _render_notification_card(d)


def _latest_delivery_text(latest: dict | None) -> str:
    if not latest:
        return "No recent delivery activity."
    carrier = latest.get("carrier", "Unknown")
    address = latest.get("address", "")
    return f"Latest: {carrier} delivery at {address} &mdash; {_smart_summary(latest)}"


def _smart_summary(d: dict) -> str:
    """Generate a scenario-aware insight from delivery data."""
    carrier = d.get("carrier", "Carrier")
    scenario = d.get("scenario_type", "")
    location = d.get("delivery_location", "").replace("_", " ")
    risk = d.get("risk_score", 0)
    factors = d.get("risk_factors", [])

    if scenario == "happy_path":
        return (
            f"{carrier} package safely delivered inside your garage. "
            f"Door confirmed closed and secured — no action needed."
        )
    if scenario == "front_door_misdelivery":
        return (
            f"{carrier} left your package at the front door instead of the garage — "
            f"exposed to weather and theft. Retrieve it soon."
        )
    if scenario == "package_behind_car":
        return (
            f"{carrier} placed your package behind your car in the garage — "
            f"it could be crushed when you back out. Move it before driving."
        )
    if scenario == "door_stuck_open":
        return (
            f"Garage door stuck open after {carrier} delivery — "
            f"package is inside but garage is unsecured. Immediate action required."
        )
    if scenario == "no_package_placed":
        return (
            f"Garage door opened for {carrier} but no package detected inside — "
            f"possible missed delivery or wrong drop-off."
        )
    if scenario == "delivery_timeout":
        return (
            f"Expected {carrier} delivery never arrived — "
            f"delivery window expired with no carrier activity."
        )
    if scenario == "theft_suspicious":
        return (
            f"Unknown person detected near your {carrier} package at the front door "
            f"shortly after delivery. Check your camera immediately."
        )
    # Fallback
    return f"{carrier} delivery at {location}. Risk: {risk:.0%}."


def _render_notification_card(d: dict):
    risk_score = d.get("risk_score", 0)
    scenario = scenario_friendly_name(d.get("scenario_type", ""))
    s_icon = scenario_icon(d.get("scenario_type", ""))
    # Homeowner sees full details — it's their own view
    owner_name = d.get("owner_name", "")
    address = d.get("address", "")

    if risk_score >= 0.75:
        card_cls = "notification-card-critical"
        risk_label = f'<span style="color:#f87171;font-weight:600;">{risk_score:.0%} CRITICAL</span>'
        header_icon = icon("shield-alert", size=18, color="#f87171")
    elif risk_score >= 0.45:
        card_cls = "notification-card-risk"
        risk_label = f'<span style="color:#fbbf24;font-weight:600;">{risk_score:.0%} RISK</span>'
        header_icon = icon("alert-triangle", size=18, color="#fbbf24")
    else:
        card_cls = "notification-card-safe"
        risk_label = f'<span style="color:#4ade80;">{risk_score:.0%} Safe</span>'
        header_icon = icon("check-circle", size=18, color="#4ade80")

    created = d.get("created_at", "")
    time_str = created[11:16] if len(created) >= 16 else created

    # Build a homeowner-friendly smart insight
    summary = _smart_summary(d)

    st.markdown(f"""<div class="notification-card {card_cls}">
        <div class="notif-header">
            <div>
                <span class="notif-icon">{header_icon}</span>
                <span class="notif-id">{d.get('id','')}</span>
                {status_badge(d.get('status',''))}
            </div>
            <div class="notif-time">{time_str}</div>
        </div>
        <div class="notif-body">{summary}</div>
        <div class="notif-tags">
            <span class="notif-tag">{s_icon} {scenario}</span>
            <span class="notif-tag">{icon("home", size=13, color="#94a3b8")} {d.get('delivery_location','').replace('_',' ').title()}</span>
            <span class="notif-tag">{icon("truck", size=13, color="#94a3b8")} {d.get('carrier','')}</span>
            <span class="notif-tag">{icon("zap", size=13, color="#94a3b8")} {risk_label} {risk_bar_html(risk_score)}</span>
        </div>
    </div>""", unsafe_allow_html=True)


_FACTOR_RECS = {
    "door_stuck_open": "Dispatch technician to check garage door mechanism",
    "garage_accessible": "Dispatch technician to check garage door mechanism",
    "package_wrong_location": "Notify homeowner of misdelivered package location",
    "not_in_garage": "Notify homeowner of misdelivered package location",
    "package_behind_vehicle": "Send urgent alert to move package before driving",
    "crush_risk": "Send urgent alert to move package before driving",
    "package_theft_risk": "Alert homeowner and review security camera footage",
    "suspicious_activity_after_delivery": "Alert homeowner and review security camera footage",
    "delivery_not_received": "Contact carrier for delivery status update",
    "window_expired": "Contact carrier for delivery status update",
}


def _recommendations_from_factors(factors: list) -> list:
    """Generate recommendations from risk_factors when risk_assessment is absent (raw data)."""
    recs = []
    for f in factors:
        if f in _FACTOR_RECS and _FACTOR_RECS[f] not in recs:
            recs.append(_FACTOR_RECS[f])
    return recs if recs else ["Check your security camera."]


def _diverse_pick(items: list[dict], total: int = 6) -> list[dict]:
    """Pick a diverse mix of deliveries that looks realistic in a demo.

    Pass 1: grab the first occurrence of each unique scenario_type.
    Pass 2: if we still haven't reached *total*, backfill with remaining
             items (different addresses) so the feed never looks sparse.
    """
    if not items:
        return []

    picked_ids: set[str] = set()
    result: list[dict] = []

    # Pass 1 — one per scenario (diversity)
    seen_scenarios: set[str] = set()
    for d in items:
        s = d.get("scenario_type", "")
        if s not in seen_scenarios:
            result.append(d)
            picked_ids.add(id(d))
            seen_scenarios.add(s)
        if len(result) >= total:
            return result

    # Pass 2 — backfill with remaining items (prefer different addresses)
    seen_addresses: set[str] = {d.get("address", "") for d in result}
    for d in items:
        if id(d) in picked_ids:
            continue
        addr = d.get("address", "")
        if addr not in seen_addresses:
            result.append(d)
            picked_ids.add(id(d))
            seen_addresses.add(addr)
            if len(result) >= total:
                return result

    # Pass 3 — still short, just fill with whatever is left
    for d in items:
        if id(d) not in picked_ids:
            result.append(d)
            if len(result) >= total:
                break

    return result
