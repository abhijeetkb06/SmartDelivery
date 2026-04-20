"""HTML UI builders for SmartDelivery delivery comparisons."""

from __future__ import annotations


def create_notification_comparison_html(delivery: dict | None = None) -> str:
    """Build before/after comparison using real delivery data.
    Left: raw myQ events (what you see today).
    Right: Couchbase Eventing + AI intelligence (what you get)."""
    if not delivery:
        return ""

    # ── Left side: raw event list (Today's myQ) ──
    timeline = delivery.get("event_timeline", [])
    event_lines = []
    for evt in timeline:
        evt_type = evt.get("event_type", "event")
        summary = evt.get("summary", "")
        ts = evt.get("timestamp", "")
        time_str = ts[11:16] if len(ts) >= 16 else ts
        # Icon per event type
        icon = {
            "delivery_window_start": "&#128336;",
            "person_detected": "&#128100;",
            "door_open": "&#128682;",
            "door_close": "&#128274;",
            "camera_motion": "&#128249;",
            "package_detected": "&#128230;",
            "delivery_confirmed": "&#9989;",
            "unknown_person": "&#9888;&#65039;",
        }.get(evt_type, "&#128161;")
        event_lines.append(
            f'<div style="display:flex;align-items:center;gap:0.5rem;padding:0.35rem 0;'
            f'border-bottom:1px solid rgba(100,116,139,0.1);">'
            f'<span style="font-size:1rem;">{icon}</span>'
            f'<span style="font-size:0.82rem;color:#cbd5e1;flex:1;">{summary}</span>'
            f'<span style="font-size:0.72rem;color:#94a3b8;">{time_str}</span></div>'
        )
    events_html = "\n".join(event_lines)

    # ── Right side: Couchbase intelligence ──
    carrier = delivery.get("carrier", "Unknown")
    risk_score = delivery.get("risk_score", 0)
    scenario = delivery.get("scenario_type", "")
    status = delivery.get("status", "")
    knowledge = delivery.get("knowledge_summary", "")

    # For raw data, knowledge_summary may not exist — build a rich scenario-aware insight
    if not knowledge:
        knowledge = _scenario_intelligence(carrier, scenario, risk_score, delivery)

    # Status badges
    if risk_score >= 0.75:
        risk_label = f'<span class="notif-tag" style="color:#f87171;">&#9888;&#65039; Risk: {risk_score:.0%}</span>'
        safe_label = '<span class="notif-tag" style="color:#f87171;">&#128680; Critical</span>'
    elif risk_score >= 0.45:
        risk_label = f'<span class="notif-tag" style="color:#fbbf24;">&#9888;&#65039; Risk: {risk_score:.0%}</span>'
        safe_label = '<span class="notif-tag" style="color:#fbbf24;">&#9888; At Risk</span>'
    else:
        risk_label = f'<span class="notif-tag" style="color:#22c55e;">&#9889; Risk: {risk_score:.0%}</span>'
        safe_label = '<span class="notif-tag" style="color:#4ade80;">&#9989; Safe</span>'

    location = delivery.get("delivery_location", "garage").replace("_", " ").title()

    return f"""<div class="before-after-container">
        <div class="before-card">
            <div class="ba-label ba-label-before">Today's myQ</div>
            <div class="ba-notification ba-notif-plain">
                <div style="font-size:0.82rem;font-weight:600;color:#fbbf24;margin-bottom:0.5rem;">
                    &#128276; myQ Notifications</div>
                {events_html}
                <div style="margin-top:0.6rem;padding-top:0.5rem;border-top:1px dashed rgba(100,116,139,0.2);">
                    <div style="font-size:0.72rem;color:#94a3b8;line-height:1.5;">
                        Just raw events. No context. Was it a delivery? A burglar?
                        Is the door still open? You don't know.</div></div></div></div>
        <div class="after-card">
            <div class="ba-label ba-label-after">myQ + Couchbase Intelligence</div>
            <div class="ba-notification ba-notif-smart">
                <div style="font-size:0.82rem;font-weight:600;color:#4ade80;margin-bottom:0.5rem;">
                    &#128230; Smart Delivery Alert</div>
                <div style="font-size:0.85rem;color:#e2e8f0;line-height:1.5;">
                    {knowledge}</div>
                <div style="margin-top:0.6rem;display:flex;gap:0.5rem;flex-wrap:wrap;">
                    {safe_label}
                    <span class="notif-tag" style="color:#94a3b8;">&#127968; {location}</span>
                    <span class="notif-tag" style="color:#94a3b8;">&#128666; {carrier}</span>
                    {risk_label}</div></div></div></div>"""


def _scenario_intelligence(carrier: str, scenario: str, risk_score: float, d: dict) -> str:
    """Generate rich, scenario-aware intelligence text for the Before/After comparison."""
    n_events = len(d.get("event_timeline", []))
    factors = d.get("risk_factors", [])

    msgs = {
        "happy_path": (
            f"Your {carrier} package was safely delivered inside your garage. "
            f"Analyzed {n_events} sensor events — door opened, package confirmed, door closed and locked. "
            f"No risk factors detected. No action needed."
        ),
        "front_door_misdelivery": (
            f"{carrier} left your package at the front door instead of the garage. "
            f"Analyzed {n_events} sensor events — camera detected package outside, not in the secure garage zone. "
            f"Risk: exposed to weather and theft ({risk_score:.0%}). Retrieve your package or enable garage-only delivery."
        ),
        "package_behind_car": (
            f"Your {carrier} package was placed behind your car in the garage — "
            f"it could be crushed when you back out. "
            f"Analyzed {n_events} sensor events — camera confirmed package near vehicle. "
            f"Move the package before driving ({risk_score:.0%} risk)."
        ),
        "door_stuck_open": (
            f"Your garage door is stuck open after {carrier} delivery. "
            f"Package was placed inside, but the door failed to close — "
            f"garage is unsecured and exposed to weather and intruders. "
            f"Analyzed {n_events} events over 10+ minutes with no door-close signal. Immediate action required ({risk_score:.0%} risk)."
        ),
        "no_package_placed": (
            f"Garage door opened for {carrier} but no package was detected inside. "
            f"Analyzed {n_events} sensor events — motion was detected but camera confirmed no package in the garage zone. "
            f"Possible missed delivery or wrong drop-off location ({risk_score:.0%} risk)."
        ),
        "delivery_timeout": (
            f"Your expected {carrier} delivery never arrived. "
            f"Monitored for the full delivery window with only {n_events} events — "
            f"no carrier activity, no person detected, no package placed. "
            f"Contact {carrier} for a status update."
        ),
        "theft_suspicious": (
            f"An unknown person was detected near your {carrier} package at the front door "
            f"minutes after delivery. "
            f"Analyzed {n_events} sensor events — camera flagged a second person after the driver left. "
            f"Package may be at risk of theft ({risk_score:.0%} risk). Check your camera immediately."
        ),
    }
    return msgs.get(scenario, f"{carrier} delivery analyzed with {n_events} events. Risk: {risk_score:.0%}.")
