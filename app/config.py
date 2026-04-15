"""Configuration loader for SmartDelivery app."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CB_CONN_STR = os.getenv("CB_CONN_STR", "")
CB_USERNAME = os.getenv("CB_USERNAME", "")
CB_PASSWORD = os.getenv("CB_PASSWORD", "")
CB_BUCKET = os.getenv("CB_BUCKET", "chamberlain")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SCOPE_RAW = "rawdata"
SCOPE_PROCESSED = "processeddata"

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
CHAT_MODEL = "gpt-4o-mini"
