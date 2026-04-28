"""Configuration loader for SmartDelivery app.

Secrets come from .env (gitignored).
Operational config comes from settings.toml (checked into git).
"""

import os
import tomllib
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Secrets (.env) ─────────────────────────────────────────────
load_dotenv(_PROJECT_ROOT / ".env")

CB_CONN_STR = os.getenv("CB_CONN_STR", "")
CB_USERNAME = os.getenv("CB_USERNAME", "")
CB_PASSWORD = os.getenv("CB_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── Operational config (settings.toml) ─────────────────────────
with open(_PROJECT_ROOT / "settings.toml", "rb") as _f:
    _cfg = tomllib.load(_f)

CB_BUCKET = os.getenv("CB_BUCKET") or _cfg["database"]["bucket"]

GENERATOR_RATE = _cfg["generator"]["rate"]
GENERATOR_WORKERS = _cfg["generator"]["workers"]
GENERATOR_BATCH = _cfg["generator"]["batch"]
GENERATOR_COUNT = _cfg["generator"]["count"]

VECTOR_INDEX_THRESHOLD = _cfg["vector"]["index_threshold"]

EMBEDDING_MODEL = _cfg["ai"]["embedding_model"]
CHAT_MODEL = _cfg["ai"]["chat_model"]

DASHBOARD_PORT = _cfg["dashboard"]["port"]
AUTO_REFRESH_MS = _cfg["dashboard"]["auto_refresh_ms"]

HOMES_COUNT = _cfg["demo"]["homes_count"]

# ── Schema constants (not configurable) ────────────────────────
SCOPE_RAW = "rawdata"
SCOPE_PROCESSED = "processeddata"
