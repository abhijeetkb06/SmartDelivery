"""
Local simulation of the Eventing pipeline.
Reads rawdata.deliveries, enriches them with PII redaction (owner_name only),
generates embeddings, writes to processeddata.deliveries.

Usage: python scripts/simulate_eventing.py
"""

import os
import sys
import time
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, ClusterTimeoutOptions
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BUCKET = os.getenv("CB_BUCKET", "chamberlain")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def connect():
    auth = PasswordAuthenticator(os.getenv("CB_USERNAME"), os.getenv("CB_PASSWORD"))
    cluster = Cluster(
        os.getenv("CB_CONN_STR"),
        ClusterOptions(auth, timeout_options=ClusterTimeoutOptions(
            kv_timeout=timedelta(seconds=10),
            query_timeout=timedelta(seconds=60),
        )),
    )
    cluster.wait_until_ready(timedelta(seconds=15))
    return cluster


# ── PII Redaction (owner_name only) ──────────────────────────

def redact_name(name: str) -> str:
    """Redact a full name: 'John Smith' -> 'J*** S***'
    Only the homeowner name is PII that ops shouldn't see.
    Address is kept intact — command center needs it to act."""
    if not name:
        return "R*******"
    parts = name.strip().split()
    result = []
    for part in parts:
        if part:
            result.append(part[0].upper() + "***")
    return " ".join(result)


def build_narrative(doc, redacted_name):
    parts = []
    parts.append(f"Delivery {doc.get('id','')} for {redacted_name} at {doc.get('address','')}.")
    parts.append(f"Carrier: {doc.get('carrier','')}. Scenario: {doc.get('scenario_type','').replace('_',' ')}.")

    timeline = doc.get("event_timeline", [])
    if timeline:
        parts.append("Event sequence:")
        for i, evt in enumerate(timeline):
            parts.append(f"  {i+1}. {evt.get('summary','')} at {evt.get('location','')} ({evt.get('event_type','')})")

    parts.append(f"Final status: {doc.get('status','').replace('_',' ')}.")
    parts.append(f"Package location: {doc.get('delivery_location','').replace('_',' ')}.")

    risk_score = doc.get("risk_score", 0)
    if risk_score > 0:
        parts.append(f"Risk score: {risk_score*100:.1f}%.")

    risk_factors = doc.get("risk_factors", [])
    if risk_factors:
        parts.append(f"Risk factors: {', '.join(f.replace('_',' ') for f in risk_factors)}.")

    return " ".join(parts)


def build_risk_assessment(doc):
    score = doc.get("risk_score", 0)
    if score >= 0.75:
        level = "critical"
    elif score >= 0.45:
        level = "high"
    elif score >= 0.20:
        level = "medium"
    else:
        level = "low"

    recommendations = []
    for factor in doc.get("risk_factors", []):
        if factor in ("door_stuck_open", "garage_accessible"):
            recommendations.append("Dispatch technician to check garage door mechanism")
        elif factor in ("package_wrong_location", "not_in_garage"):
            recommendations.append("Notify homeowner of misdelivered package location")
        elif factor in ("package_behind_vehicle", "crush_risk"):
            recommendations.append("Send urgent alert to move package before driving")
        elif factor in ("package_theft_risk", "suspicious_activity_after_delivery"):
            recommendations.append("Alert homeowner and review security camera footage")
        elif factor in ("delivery_not_received", "window_expired"):
            recommendations.append("Contact carrier for delivery status update")

    return {
        "level": level,
        "score": score,
        "factors": doc.get("risk_factors", []),
        "recommendations": recommendations,
    }


def main():
    print("=== SmartDelivery Eventing Simulator (v2 - Name Redaction) ===\n")

    cluster = connect()
    print("Connected to Couchbase.\n")

    oai = OpenAI(api_key=OPENAI_API_KEY)

    # Fetch raw deliveries
    rows = list(cluster.query(
        f"SELECT META(d).id AS doc_id, d.* FROM `{BUCKET}`.`rawdata`.`deliveries` d"
    ))
    print(f"Found {len(rows)} raw deliveries.\n")

    proc_scope = cluster.bucket(BUCKET).scope("processeddata")
    proc_col = proc_scope.collection("deliveries")

    enriched_count = 0
    embedded_count = 0

    for i, raw in enumerate(rows):
        doc_id = raw.get("doc_id", raw.get("id", ""))
        print(f"[{i+1}/{len(rows)}] Processing {doc_id}...", end=" ")

        # ── PII Redaction: only owner_name ──
        original_name = raw.get("owner_name", "")
        redacted_name = redact_name(original_name)

        # Step 1: Enrich with redacted name, full address kept
        narrative = build_narrative(raw, redacted_name)
        risk_assessment = build_risk_assessment(raw)

        enriched = dict(raw)
        enriched.pop("doc_id", None)

        # Redact only owner_name — address kept for operational use
        enriched["owner_name"] = redacted_name

        enriched["knowledge_summary"] = narrative
        enriched["risk_assessment"] = risk_assessment
        enriched["processing_status"] = "processed"
        enriched["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        enriched["is_ai_ready"] = False
        enriched["enrichment_version"] = "2.0"
        enriched["source_scope"] = "rawdata"
        enriched["pii_redacted"] = True

        # Embedding text uses redacted name + full address for context
        embedding_text = narrative + f" Delivery scenario: {raw.get('scenario_type','').replace('_',' ')}."
        embedding_text += f" Delivery status: {raw.get('status','').replace('_',' ')}."
        embedding_text += f" Location: {raw.get('address','')}."
        embedding_text += f" Risk level: {risk_assessment['level']}."
        enriched["embedding_text"] = embedding_text

        enriched_count += 1
        print(f"enriched ({redacted_name})...", end=" ")

        # Step 2: Generate embedding
        try:
            resp = oai.embeddings.create(model="text-embedding-3-small", input=embedding_text)
            embedding = resp.data[0].embedding
            enriched["embedding"] = embedding
            enriched["is_ai_ready"] = True
            enriched["embedding_model"] = "text-embedding-3-small"
            enriched["embedding_dimensions"] = len(embedding)
            enriched["embedding_generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            embedded_count += 1
            print(f"embedded ({len(embedding)} dims)...", end=" ")
        except Exception as e:
            print(f"embedding failed: {e}...", end=" ")

        # Step 3: Write to processeddata.deliveries
        proc_col.upsert(doc_id, enriched)
        print("saved.")

    print(f"\nDone! Enriched: {enriched_count}, Embedded: {embedded_count}")
    print("Processed deliveries are now in processeddata.deliveries (owner_name redacted, address intact).")

    # Also copy alerts to processeddata
    print("\nCopying alerts to processeddata.alerts...")
    alert_rows = list(cluster.query(
        f"SELECT META(a).id AS doc_id, a.* FROM `{BUCKET}`.`rawdata`.`alerts` a"
    ))
    proc_alerts = proc_scope.collection("alerts")
    for a in alert_rows:
        aid = a.pop("doc_id", a.get("id", ""))
        proc_alerts.upsert(aid, a)
    print(f"Copied {len(alert_rows)} alerts.")


if __name__ == "__main__":
    main()
