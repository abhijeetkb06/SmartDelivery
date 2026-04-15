"""Plotly chart builders for SmartDelivery (dark theme)."""

from __future__ import annotations
import plotly.graph_objects as go

_FONT = dict(family="Inter, sans-serif", color="#94a3b8")
_TRANSPARENT = "rgba(0,0,0,0)"

def _base_layout(**overrides) -> dict:
    defaults = dict(
        paper_bgcolor=_TRANSPARENT, plot_bgcolor=_TRANSPARENT,
        font=_FONT, margin=dict(l=20, r=20, t=30, b=20),
    )
    defaults.update(overrides)
    return defaults

_SCENARIO_COLORS = {
    "happy_path": "#22c55e", "front_door_misdelivery": "#fbbf24",
    "package_behind_car": "#f97316", "door_stuck_open": "#ef4444",
    "no_package_placed": "#a855f7", "delivery_timeout": "#6366f1",
    "theft_suspicious": "#dc2626",
}
_SCENARIO_NAMES = {
    "happy_path": "Happy Path", "front_door_misdelivery": "Front Door Misdelivery",
    "package_behind_car": "Package Behind Car", "door_stuck_open": "Door Stuck Open",
    "no_package_placed": "Missing Package", "delivery_timeout": "Delivery Timeout",
    "theft_suspicious": "Suspicious Activity",
}

def create_scenario_donut(scenario_data: list[dict]) -> go.Figure:
    labels = [_SCENARIO_NAMES.get(r["scenario_type"], r["scenario_type"]) for r in scenario_data]
    values = [r["cnt"] for r in scenario_data]
    colors = [_SCENARIO_COLORS.get(r["scenario_type"], "#64748b") for r in scenario_data]
    total = sum(values)
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.5,
        marker=dict(colors=colors, line=dict(color="#0f172a", width=2)),
        textinfo="percent", textfont=dict(size=11, color="#e2e8f0"),
        hovertemplate="<b>%{label}</b><br>%{value} deliveries (%{percent})<extra></extra>"))
    fig.add_annotation(text=f"<b>{total}</b><br><span style='font-size:11px;color:#94a3b8'>Total</span>",
                       showarrow=False, font=dict(size=20, color="#e2e8f0"))
    fig.update_layout(**_base_layout(height=300, showlegend=True,
        legend=dict(font=dict(size=10, color="#94a3b8"), bgcolor=_TRANSPARENT, x=1, y=0.5)))
    return fig

_STATUS_META = [
    ("success", "Successful", "#22c55e"),
    ("risk", "Completed w/ Risk", "#fbbf24"),
    ("failed", "Failed", "#ef4444"),
    ("suspicious", "Suspicious", "#a855f7"),
]

def create_status_bar(stats: dict) -> go.Figure:
    fig = go.Figure()
    for key, label, color in _STATUS_META:
        val = stats.get(key, 0)
        fig.add_trace(go.Bar(y=[label], x=[val], orientation="h", name=label,
            marker=dict(color=color, line=dict(color="#0f172a", width=1)),
            text=[str(val)], textposition="auto",
            textfont=dict(color="#e2e8f0", size=12),
            hovertemplate=f"<b>{label}</b>: %{{x}}<extra></extra>"))
    fig.update_layout(**_base_layout(height=250, showlegend=False, barmode="stack",
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, tickfont=dict(size=11, color="#94a3b8"))))
    return fig

def create_risk_gauge(risk_score: float) -> go.Figure:
    pct = risk_score * 100
    bar_color = "#ef4444" if risk_score >= 0.75 else "#fbbf24" if risk_score >= 0.45 else "#6366f1" if risk_score >= 0.20 else "#22c55e"
    fig = go.Figure(go.Indicator(mode="gauge+number", value=pct,
        number=dict(suffix="%", font=dict(size=28, color="#e2e8f0")),
        gauge=dict(axis=dict(range=[0,100], tickwidth=1, tickcolor="#334155", tickfont=dict(size=10, color="#64748b")),
            bar=dict(color=bar_color, thickness=0.7), bgcolor="rgba(15,23,42,0.5)",
            borderwidth=1, bordercolor="rgba(99,102,241,0.2)",
            steps=[dict(range=[0,20], color="rgba(34,197,94,0.15)"), dict(range=[20,45], color="rgba(99,102,241,0.10)"),
                   dict(range=[45,75], color="rgba(251,191,36,0.15)"), dict(range=[75,100], color="rgba(239,68,68,0.15)")],
        )))
    fig.update_layout(**_base_layout(height=200, margin=dict(l=30, r=30, t=20, b=10)))
    return fig

_CARRIER_COLORS = {"UPS": "#7c4a1e", "FedEx": "#6366f1", "USPS": "#2563eb", "Amazon": "#f97316", "DHL": "#eab308"}

def create_carrier_pie(carrier_data: list[dict]) -> go.Figure:
    labels = [r["carrier"] for r in carrier_data]
    values = [r["cnt"] for r in carrier_data]
    colors = [_CARRIER_COLORS.get(r["carrier"], "#64748b") for r in carrier_data]
    fig = go.Figure(go.Pie(labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color="#0f172a", width=2)),
        textinfo="label+percent", textfont=dict(size=11, color="#e2e8f0"),
        hovertemplate="<b>%{label}</b><br>%{value} deliveries (%{percent})<extra></extra>"))
    fig.update_layout(**_base_layout(height=280, showlegend=False))
    return fig

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

    # For raw data, knowledge_summary may not exist — build one
    if not knowledge:
        location = delivery.get("delivery_location", "garage").replace("_", " ")
        if scenario == "happy_path":
            knowledge = f"Your {carrier} package was delivered safely inside your {location}. The garage door has been confirmed closed. No action needed."
        elif scenario == "theft_suspicious":
            knowledge = f"Suspicious activity detected after {carrier} delivery at your {location}. An unknown person was detected near your package. Please check your security camera immediately."
        elif scenario == "door_stuck_open":
            knowledge = f"Your garage door is stuck open after {carrier} delivery. Package is inside but the garage is unsecured. Action required."
        else:
            knowledge = f"{carrier} delivery to your {location}. Status: {status.replace('_', ' ')}."

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
