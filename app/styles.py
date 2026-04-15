"""Dark glassmorphic theme CSS + helper functions for SmartDelivery."""

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global ── */
.stApp {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    font-family: 'Inter', sans-serif;
    color: #e2e8f0;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { display: none; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
.block-container { max-width: 1280px; padding: 1rem 2rem 2rem; }

/* ── Header ── */
.app-header {
    background: linear-gradient(135deg, rgba(30,41,59,0.95), rgba(15,23,42,0.98));
    backdrop-filter: blur(12px);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 16px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    text-align: center;
}
.app-header h1 {
    margin: 0; font-size: 2rem; font-weight: 700;
    background: linear-gradient(135deg, #818cf8, #6366f1, #4f46e5);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
}
.app-header p {
    margin: 0.4rem 0 0; color: #94a3b8; font-size: 0.95rem;
}
.connection-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    background: #22c55e; margin-right: 0.4rem; vertical-align: middle;
    box-shadow: 0 0 6px rgba(34,197,94,0.5);
}

/* ── Stat cards ── */
.stat-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95));
    backdrop-filter: blur(10px);
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    text-align: center;
    transition: border-color 0.2s ease;
}
.stat-card:hover { border-color: rgba(99,102,241,0.35); }
.stat-card .stat-icon { font-size: 1.4rem; margin-bottom: 0.2rem; }
.stat-card .stat-value { font-size: 1.6rem; font-weight: 700; color: #818cf8; }
.stat-card .stat-label { font-size: 0.78rem; color: #94a3b8; margin-top: 0.2rem; }

/* ── Glass cards ── */
.glass-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.85), rgba(15,23,42,0.90));
    backdrop-filter: blur(10px);
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 12px;
    padding: 1.25rem;
    margin-bottom: 0.75rem;
    transition: border-color 0.2s ease;
}
.glass-card:hover { border-color: rgba(99,102,241,0.35); }

/* ── Status badges ── */
.badge {
    display: inline-block; padding: 0.2rem 0.6rem;
    border-radius: 20px; font-size: 0.72rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.03em;
}
.badge-success { background: rgba(34,197,94,0.2); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }
.badge-risk    { background: rgba(251,191,36,0.2); color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); }
.badge-failed  { background: rgba(239,68,68,0.2);  color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
.badge-suspicious { background: rgba(168,85,247,0.2); color: #c084fc; border: 1px solid rgba(168,85,247,0.3); }
.badge-info    { background: rgba(99,102,241,0.2);  color: #818cf8; border: 1px solid rgba(99,102,241,0.3); }
.badge-ai      { background: rgba(34,197,94,0.15);  color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }

/* ── Score badge ── */
.score-badge {
    background: linear-gradient(135deg, rgba(34,197,94,0.2), rgba(22,163,74,0.3));
    border: 1px solid rgba(34,197,94,0.3);
    color: #4ade80; padding: 0.25rem 0.75rem;
    border-radius: 20px; font-size: 0.8rem; font-weight: 500;
    display: inline-block;
}

/* ── myQ Device Card ── */
.myq-device-card {
    background: linear-gradient(135deg, #004C99, #0066CC);
    border-radius: 16px; padding: 1.5rem; color: #ffffff;
    position: relative; overflow: hidden; margin-bottom: 1rem;
}
.myq-device-card::after {
    content: ''; position: absolute; top: -30%; right: -10%;
    width: 200px; height: 200px;
    background: rgba(255,255,255,0.05); border-radius: 50%;
}
.myq-device-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.myq-device-name { font-size: 0.8rem; font-weight: 500; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 0.05em; }
.myq-device-location { font-size: 1.1rem; font-weight: 600; color: #ffffff; }
.myq-door-icon { width: 48px; height: 48px; background: rgba(255,255,255,0.15); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; }
.myq-door-status { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.75rem; }
.myq-door-status-dot { width: 10px; height: 10px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,0.6); }
.myq-door-status-dot.open { background: #f59e0b; box-shadow: 0 0 8px rgba(245,158,11,0.6); }
.myq-door-status-text { font-size: 0.9rem; font-weight: 600; color: #ffffff; }
.myq-delivery-banner { background: rgba(255,255,255,0.12); border-radius: 10px; padding: 0.75rem 1rem; margin-top: 1rem; backdrop-filter: blur(4px); }
.myq-delivery-banner-title { font-size: 0.75rem; font-weight: 600; color: rgba(255,255,255,0.7); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.3rem; }
.myq-delivery-banner-text { font-size: 0.85rem; color: #ffffff; line-height: 1.45; }
.myq-delivery-banner-tag { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.15rem 0.5rem; border-radius: 12px; background: rgba(255,255,255,0.1); font-size: 0.72rem; color: rgba(255,255,255,0.9); }

/* ── Notification Cards ── */
.notification-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.85), rgba(15,23,42,0.90));
    border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 0.75rem; transition: all 0.2s ease;
}
.notification-card:hover { transform: translateY(-2px); }
.notification-card-safe { border-left: 4px solid #22c55e; border-top: 1px solid rgba(34,197,94,0.15); border-right: 1px solid rgba(34,197,94,0.15); border-bottom: 1px solid rgba(34,197,94,0.15); }
.notification-card-risk { border-left: 4px solid #fbbf24; border-top: 1px solid rgba(251,191,36,0.15); border-right: 1px solid rgba(251,191,36,0.15); border-bottom: 1px solid rgba(251,191,36,0.15); }
.notification-card-critical { border-left: 4px solid #ef4444; border-top: 1px solid rgba(239,68,68,0.15); border-right: 1px solid rgba(239,68,68,0.15); border-bottom: 1px solid rgba(239,68,68,0.15); animation: pulse-red 2.5s ease-in-out infinite; }
@keyframes pulse-red { 0%, 100% { box-shadow: 0 0 10px rgba(239,68,68,0.08); } 50% { box-shadow: 0 0 20px rgba(239,68,68,0.2); } }
.notif-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.notif-icon { font-size: 1.2rem; margin-right: 0.5rem; }
.notif-id { font-weight: 600; color: #e2e8f0; font-size: 0.88rem; }
.notif-time { color: #64748b; font-size: 0.72rem; }
.notif-body { color: #cbd5e1; font-size: 0.85rem; line-height: 1.5; margin-bottom: 0.5rem; }
.notif-tags { display: flex; gap: 0.6rem; flex-wrap: wrap; font-size: 0.75rem; color: #94a3b8; }
.notif-tag { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.15rem 0.5rem; border-radius: 12px; background: rgba(15,23,42,0.6); }

/* ── Before / After ── */
.before-after-container { display: flex; gap: 1.5rem; margin-bottom: 1.5rem; }
.before-card { flex: 1; background: linear-gradient(135deg, rgba(30,41,59,0.85), rgba(15,23,42,0.90)); border: 1px solid rgba(251,191,36,0.2); border-left: 4px solid #fbbf24; border-radius: 12px; padding: 1.25rem; }
.after-card { flex: 1; background: linear-gradient(135deg, rgba(30,41,59,0.85), rgba(15,23,42,0.90)); border: 1px solid rgba(34,197,94,0.25); border-left: 4px solid #22c55e; border-radius: 12px; padding: 1.25rem; box-shadow: 0 0 20px rgba(34,197,94,0.08); }
.ba-label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.75rem; padding-bottom: 0.4rem; border-bottom: 1px solid rgba(100,116,139,0.2); }
.ba-label-before { color: #fbbf24; }
.ba-label-after { color: #4ade80; }
.ba-notification { border-radius: 10px; padding: 0.8rem 1rem; margin-top: 0.5rem; }
.ba-notif-plain { background: rgba(15,23,42,0.3); border: 1px solid rgba(100,116,139,0.1); }
.ba-notif-smart { background: rgba(34,197,94,0.05); border: 1px solid rgba(34,197,94,0.15); }

/* ── Alert Banners ── */
.alert-banner { border-radius: 10px; padding: 0.8rem 1rem; margin-bottom: 0.6rem; display: flex; align-items: center; gap: 0.75rem; }
.alert-banner-critical { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.25); border-left: 4px solid #ef4444; }
.alert-banner-warning { background: rgba(251,191,36,0.08); border: 1px solid rgba(251,191,36,0.2); border-left: 4px solid #fbbf24; }
.alert-banner-icon { font-size: 1.3rem; flex-shrink: 0; }
.alert-banner-content { flex: 1; }
.alert-banner-title { font-weight: 600; font-size: 0.85rem; color: #e2e8f0; }
.alert-banner-desc { font-size: 0.78rem; color: #94a3b8; margin-top: 0.15rem; }

/* ── PII Redaction Visual ── */
.pii-comparison { display: flex; gap: 1.5rem; margin-bottom: 1.5rem; }
.pii-raw-card { flex: 1; background: linear-gradient(135deg, rgba(30,41,59,0.85), rgba(15,23,42,0.90)); border: 1px solid rgba(239,68,68,0.2); border-left: 4px solid #ef4444; border-radius: 12px; padding: 1.25rem; }
.pii-safe-card { flex: 1; background: linear-gradient(135deg, rgba(30,41,59,0.85), rgba(15,23,42,0.90)); border: 1px solid rgba(34,197,94,0.25); border-left: 4px solid #22c55e; border-radius: 12px; padding: 1.25rem; box-shadow: 0 0 15px rgba(34,197,94,0.06); }
.pii-label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.75rem; padding-bottom: 0.4rem; border-bottom: 1px solid rgba(100,116,139,0.2); }
.pii-label-raw { color: #f87171; }
.pii-label-safe { color: #4ade80; }
.pii-field { display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0; border-bottom: 1px solid rgba(99,102,241,0.08); }
.pii-field:last-child { border-bottom: none; }
.pii-field-name { font-size: 0.75rem; color: #64748b; text-transform: uppercase; }
.pii-field-value-raw { font-size: 0.85rem; color: #f87171; font-weight: 500; }
.pii-field-value-safe { font-size: 0.85rem; color: #4ade80; font-weight: 500; }
.pii-arrow { display: flex; align-items: center; justify-content: center; font-size: 1.5rem; color: #6366f1; flex-shrink: 0; }

/* ── Ops Alert Card ── */
.ops-alert-card { background: rgba(30,41,59,0.7); border: 1px solid rgba(99,102,241,0.1); border-radius: 8px; padding: 0.7rem 0.9rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.6rem; }
.ops-alert-severity { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

/* ── Result Cards (Vector Search) ── */
.result-card { background: linear-gradient(135deg, rgba(30,41,59,0.7), rgba(15,23,42,0.85)); border: 1px solid rgba(99,102,241,0.1); border-radius: 12px; padding: 1.25rem; margin-bottom: 0.75rem; transition: all 0.2s ease; }
.result-card:hover { border-color: rgba(99,102,241,0.3); background: linear-gradient(135deg, rgba(30,41,59,0.8), rgba(15,23,42,0.9)); }
.result-rank { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; background: linear-gradient(135deg, #6366f1, #4f46e5); border-radius: 8px; font-weight: 600; font-size: 0.85rem; color: white; margin-right: 0.75rem; }
.result-condition { font-size: 1.1rem; font-weight: 600; color: #e2e8f0; }
.result-summary { color: #cbd5e1; font-size: 0.9rem; font-style: italic; margin: 0.75rem 0; padding-left: 1rem; border-left: 2px solid rgba(99,102,241,0.4); }
.result-details { display: flex; gap: 1.5rem; margin-top: 0.75rem; flex-wrap: wrap; }
.detail-item { display: flex; align-items: center; gap: 0.35rem; color: #94a3b8; font-size: 0.85rem; }

/* ── Risk bar ── */
.risk-bar-container { width: 100px; height: 6px; background: rgba(15,23,42,0.8); border-radius: 3px; overflow: hidden; display: inline-block; vertical-align: middle; margin-left: 0.4rem; }
.risk-bar-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }

/* ── Query box ── */
.query-box { background: rgba(6,78,59,0.3); border: 1px solid rgba(34,197,94,0.3); border-radius: 12px; padding: 1rem; font-family: 'JetBrains Mono','Fira Code',monospace; font-size: 0.8rem; color: #4ade80; white-space: pre-wrap; overflow-x: auto; }

/* ── Breakdown cards ── */
.breakdown-card { background: rgba(15,23,42,0.6); border: 1px solid rgba(99,102,241,0.1); border-radius: 10px; padding: 1rem; }
.breakdown-title { font-size: 0.75rem; color: #818cf8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem; font-weight: 600; }
.breakdown-item { display: flex; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid rgba(99,102,241,0.08); font-size: 0.85rem; }
.breakdown-item:last-child { border-bottom: none; }
.breakdown-name { color: #94a3b8; }
.breakdown-count { color: #e2e8f0; font-weight: 600; }

/* ── Chat styles ── */
.chat-message { padding: 1rem; border-radius: 12px; margin-bottom: 1rem; }
.user-message { background: linear-gradient(135deg, rgba(99,102,241,0.2), rgba(79,70,229,0.3)); border: 1px solid rgba(99,102,241,0.3); margin-left: 2rem; }
.assistant-message { background: linear-gradient(135deg, rgba(30,41,59,0.8), rgba(15,23,42,0.9)); border: 1px solid rgba(99,102,241,0.15); margin-right: 2rem; }
.source-card { background: rgba(15,23,42,0.6); border: 1px solid rgba(99,102,241,0.1); border-radius: 8px; padding: 0.75rem; margin-top: 0.5rem; font-size: 0.85rem; }

/* ── Section title ── */
.section-title { font-size: 1.1rem; font-weight: 600; color: #e2e8f0; margin: 1.25rem 0 0.75rem; padding-bottom: 0.4rem; border-bottom: 1px solid rgba(99,102,241,0.15); }
.section-subtitle { font-size: 0.85rem; color: #94a3b8; margin: -0.5rem 0 0.75rem; }

/* ── Tabs styling ── */
.stTabs [data-baseweb="tab-list"] { gap: 0.5rem; background: rgba(15,23,42,0.5); border-radius: 12px; padding: 0.3rem; }
.stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 0.5rem 1.2rem; font-weight: 500; color: #94a3b8; }
.stTabs [aria-selected="true"] { background: rgba(99,102,241,0.2) !important; color: #818cf8 !important; }
.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ── Selectbox / input ── */
.stSelectbox > div > div { background: rgba(15,23,42,0.8); border: 1px solid rgba(99,102,241,0.2); border-radius: 8px; color: #e2e8f0; }
div[data-baseweb="select"] > div { background: rgba(15,23,42,0.8); border-color: rgba(99,102,241,0.2); }
.stTextInput > div > div > input, .stTextArea > div > div > textarea { background: rgba(15,23,42,0.8) !important; border: 1px solid rgba(99,102,241,0.2) !important; border-radius: 8px !important; color: #e2e8f0 !important; }
.stTextInput > div > div > input:focus { border-color: #6366f1 !important; box-shadow: 0 0 0 2px rgba(99,102,241,0.2) !important; }

/* ── Buttons ── */
.stButton > button { background: linear-gradient(135deg, #6366f1, #4f46e5); border: none; border-radius: 10px; color: white; font-weight: 600; padding: 0.75rem 2rem; transition: all 0.2s ease; }
.stButton > button:hover { background: linear-gradient(135deg, #818cf8, #6366f1); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99,102,241,0.4); }

/* ── Expander ── */
.streamlit-expanderHeader { background: rgba(30,41,59,0.6); border-radius: 8px; font-size: 0.85rem; color: #94a3b8; }
.stExpander { background: rgba(15,23,42,0.5); border: 1px solid rgba(99,102,241,0.15); border-radius: 12px; }

/* ── Filter label ── */
.filter-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
</style>
"""


# ── Badge helpers ────────────────────────────────────────────────
def status_badge(status: str) -> str:
    css_class = {
        "completed_success": "badge-success",
        "completed_risk": "badge-risk",
        "failed": "badge-failed",
        "suspicious": "badge-suspicious",
    }.get(status, "badge-info")
    label = status.replace("_", " ").title()
    return f'<span class="badge {css_class}">{label}</span>'


def risk_badge(score: float) -> str:
    if score >= 0.75:
        cls = "badge-failed"
    elif score >= 0.45:
        cls = "badge-risk"
    elif score >= 0.20:
        cls = "badge-info"
    else:
        cls = "badge-success"
    return f'<span class="badge {cls}">Risk: {score:.0%}</span>'


def ai_badge(is_ready: bool) -> str:
    if is_ready:
        return '<span class="badge badge-ai">AI Ready</span>'
    return '<span class="badge badge-info">Processing</span>'


def risk_bar_html(score: float) -> str:
    pct = score * 100
    if score >= 0.75:
        color = "#ef4444"
    elif score >= 0.45:
        color = "#fbbf24"
    elif score >= 0.20:
        color = "#6366f1"
    else:
        color = "#22c55e"
    return (
        f'<span class="risk-bar-container">'
        f'<span class="risk-bar-fill" style="width:{pct:.0f}%;background:{color};"></span>'
        f'</span>'
    )


# ── Icon / name helpers ─────────────────────────────────────────
_EVENT_ICONS = {
    "delivery_window_start": "🕐", "delivery_window_end": "🕐",
    "person_detected": "👤", "unknown_person": "🕵️",
    "door_open": "🚪", "door_close": "🔒", "door_stuck": "⚠️",
    "camera_motion": "📹", "package_detected": "📦",
    "package_not_detected": "❌", "delivery_confirmed": "✅",
    "delivery_timeout": "⏰",
}

_EVENT_COLORS = {
    "delivery_window_start": "#64748b", "delivery_window_end": "#64748b",
    "person_detected": "#fbbf24", "unknown_person": "#f97316",
    "door_open": "#6366f1", "door_close": "#6366f1", "door_stuck": "#ef4444",
    "camera_motion": "#22d3ee", "package_detected": "#22c55e",
    "package_not_detected": "#ef4444", "delivery_confirmed": "#22c55e",
    "delivery_timeout": "#ef4444",
}

_SCENARIO_ICONS = {
    "happy_path": "✅", "front_door_misdelivery": "🏠",
    "package_behind_car": "🚗", "door_stuck_open": "🚪",
    "no_package_placed": "📭", "delivery_timeout": "⏰",
    "theft_suspicious": "🚨",
}

_SCENARIO_NAMES = {
    "happy_path": "Happy Path", "front_door_misdelivery": "Front Door Misdelivery",
    "package_behind_car": "Package Behind Car", "door_stuck_open": "Door Stuck Open",
    "no_package_placed": "Missing Package", "delivery_timeout": "Delivery Timeout",
    "theft_suspicious": "Suspicious Activity",
}


def event_icon(event_type: str) -> str:
    return _EVENT_ICONS.get(event_type, "📋")

def event_color(event_type: str) -> str:
    return _EVENT_COLORS.get(event_type, "#6366f1")

def scenario_icon(scenario_type: str) -> str:
    return _SCENARIO_ICONS.get(scenario_type, "📦")

def scenario_friendly_name(scenario_type: str) -> str:
    return _SCENARIO_NAMES.get(scenario_type, scenario_type.replace("_", " ").title())
