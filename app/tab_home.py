"""Tab 1 - My myQ: Homeowner view with smart delivery intelligence."""

from __future__ import annotations
import streamlit as st
from couchbase.cluster import Cluster
import couchbase_client as cb
import charts
from styles import status_badge, risk_badge, risk_bar_html, scenario_icon, scenario_friendly_name


def render(cluster: Cluster):
    # Homeowner view: query RAWDATA so they see their full name & address
    try:
        deliveries = cb.get_raw_deliveries(cluster, limit=30)
    except Exception:
        st.warning("Delivery data is still loading. Please wait a moment and refresh.")
        return
    critical_deliveries = [d for d in deliveries if d.get("risk_score", 0) >= 0.75]

    # ── Section 1: myQ Device Card ──────────────────────────────
    latest = deliveries[0] if deliveries else None
    door_closed = True
    if latest and latest.get("scenario_type") == "door_stuck_open":
        door_closed = False
    door_status = "Closed" if door_closed else "Stuck Open"
    door_icon = "🔒" if door_closed else "⚠️"
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
            <div class="myq-delivery-banner-title">📦 Delivery Intelligence</div>
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

    st.markdown(
        '<div style="text-align:center;font-size:0.72rem;color:#475569;margin-bottom:1.5rem;">'
        'The smart insight on the right is generated <b style="color:#4ade80;">automatically</b> '
        'by Couchbase Eventing &mdash; turning raw events into intelligence, no application code needed</div>',
        unsafe_allow_html=True)

    # ── Section 3: Active Alerts ────────────────────────────────
    if critical_deliveries:
        st.markdown('<div class="section-title">&#128680; Active Alerts</div>',
                    unsafe_allow_html=True)
        for d in critical_deliveries[:5]:
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
    st.markdown('<div class="section-title">&#128230; Recent Delivery Activity</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Smart notifications powered by AI-generated delivery narratives. '
        'Each summary is created automatically by Couchbase Eventing.</div>',
        unsafe_allow_html=True)

    if not deliveries:
        st.info("No deliveries found. Make sure the event generator has produced data.")
        return

    for d in deliveries[:15]:
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
        header_icon = "&#128680;"
    elif risk_score >= 0.45:
        card_cls = "notification-card-risk"
        risk_label = f'<span style="color:#fbbf24;font-weight:600;">{risk_score:.0%} RISK</span>'
        header_icon = "&#9888;&#65039;"
    else:
        card_cls = "notification-card-safe"
        risk_label = f'<span style="color:#4ade80;">{risk_score:.0%} Safe</span>'
        header_icon = "&#9989;"

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
            <span class="notif-tag">&#127968; {d.get('delivery_location','').replace('_',' ').title()}</span>
            <span class="notif-tag">&#128666; {d.get('carrier','')}</span>
            <span class="notif-tag">&#9889; {risk_label} {risk_bar_html(risk_score)}</span>
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
