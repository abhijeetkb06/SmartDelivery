/*
 * DeliveryKnowledgePipeline
 * ─────────────────────────
 * Couchbase Eventing Function #1
 *
 * Source:   chamberlain.rawdata.deliveries
 * Bindings:
 *   - Bucket alias "dst"  → chamberlain.processeddata.deliveries (read+write)
 *   - Bucket alias "src_events" → chamberlain.rawdata.events (read)
 *
 * Trigger: fires on every mutation in rawdata.deliveries
 * Action:  enriches raw delivery with a knowledge narrative,
 *          redacts PII field (owner_name only),
 *          writes the enriched doc to processeddata.deliveries
 */

function OnUpdate(doc, meta) {
    // Only process docs that haven't been processed yet
    if (doc.processing_status !== "pending") return;

    try {
        // ── Redact PII before copying ──
        var redactedName = redactName(doc.owner_name);

        // ── Build rich narrative using redacted name but full address ──
        var narrative = buildNarrative(doc, redactedName);
        var riskAssessment = buildRiskAssessment(doc);

        // ── Create enriched document ──
        var enriched = {};
        // Copy all original fields (includes full address - ops needs it)
        for (var key in doc) {
            enriched[key] = doc[key];
        }

        // ── Redact only owner_name (the PII ops shouldn't see) ──
        enriched.owner_name = redactedName;
        // Address is kept intact — command center needs it to act

        // Add enrichment fields
        enriched.knowledge_summary = narrative;
        enriched.risk_assessment = riskAssessment;
        enriched.processing_status = "processed";
        enriched.processed_at = new Date().toISOString();
        enriched.is_ai_ready = false;   // becomes true after embedding
        enriched.enrichment_version = "2.0";
        enriched.source_scope = "rawdata";
        enriched.pii_redacted = true;

        // Build the embedding text (redacted name, full address for operational context)
        enriched.embedding_text = buildEmbeddingText(enriched);

        // Write to processeddata.deliveries
        dst[meta.id] = enriched;

        log("Enriched delivery: " + meta.id + " | scenario: " + doc.scenario_type + " | PII redacted");
    } catch (e) {
        log("ERROR enriching " + meta.id + ": " + e);
    }
}

// ── PII Redaction ──

function redactName(name) {
    if (!name || typeof name !== "string") return "R*******";
    var parts = name.trim().split(/\s+/);
    var result = [];
    for (var i = 0; i < parts.length; i++) {
        var part = parts[i];
        if (part.length > 0) {
            result.push(part.charAt(0).toUpperCase() + "***");
        }
    }
    return result.join(" ");
}

// ── Narrative Builder ──

function buildNarrative(doc, redactedName) {
    var parts = [];
    parts.push("Delivery " + doc.id + " for " + redactedName + " at " + doc.address + ".");
    parts.push("Carrier: " + doc.carrier + ". Scenario: " + formatScenario(doc.scenario_type) + ".");

    // Walk through the event timeline to tell the story
    if (doc.event_timeline && doc.event_timeline.length > 0) {
        parts.push("Event sequence:");
        for (var i = 0; i < doc.event_timeline.length; i++) {
            var evt = doc.event_timeline[i];
            parts.push("  " + (i + 1) + ". " + evt.summary + " at " + evt.location +
                       " (" + evt.event_type + ")");
        }
    }

    // Status and outcome
    parts.push("Final status: " + formatStatus(doc.status) + ".");
    parts.push("Package location: " + doc.delivery_location.replace(/_/g, " ") + ".");

    // Risk information
    if (doc.risk_score > 0) {
        parts.push("Risk score: " + (doc.risk_score * 100).toFixed(1) + "%.");
    }
    if (doc.risk_factors && doc.risk_factors.length > 0) {
        parts.push("Risk factors: " + doc.risk_factors.join(", ").replace(/_/g, " ") + ".");
    }

    return parts.join(" ");
}

function buildRiskAssessment(doc) {
    var level = "low";
    if (doc.risk_score >= 0.75) level = "critical";
    else if (doc.risk_score >= 0.45) level = "high";
    else if (doc.risk_score >= 0.20) level = "medium";

    var recommendations = [];
    if (doc.risk_factors) {
        for (var i = 0; i < doc.risk_factors.length; i++) {
            var factor = doc.risk_factors[i];
            if (factor === "door_stuck_open" || factor === "garage_accessible")
                recommendations.push("Dispatch technician to check garage door mechanism");
            else if (factor === "package_wrong_location" || factor === "not_in_garage")
                recommendations.push("Notify homeowner of misdelivered package location");
            else if (factor === "package_behind_vehicle" || factor === "crush_risk")
                recommendations.push("Send urgent alert to move package before driving");
            else if (factor === "package_theft_risk" || factor === "suspicious_activity_after_delivery")
                recommendations.push("Alert homeowner and review security camera footage");
            else if (factor === "delivery_not_received" || factor === "window_expired")
                recommendations.push("Contact carrier for delivery status update");
        }
    }

    return {
        level: level,
        score: doc.risk_score,
        factors: doc.risk_factors || [],
        recommendations: recommendations
    };
}

function buildEmbeddingText(doc) {
    var text = doc.knowledge_summary || "";
    text += " Delivery scenario: " + formatScenario(doc.scenario_type) + ".";
    text += " Delivery status: " + formatStatus(doc.status) + ".";
    // Full address kept for operational context
    text += " Location: " + doc.address + ".";
    if (doc.risk_assessment) {
        text += " Risk level: " + doc.risk_assessment.level + ".";
    }
    return text;
}

function formatScenario(s) {
    if (!s) return "unknown";
    return s.replace(/_/g, " ");
}

function formatStatus(s) {
    if (!s) return "unknown";
    return s.replace(/_/g, " ");
}

function OnDelete(meta, options) {
    // When a raw delivery is deleted, remove its processed counterpart
    try {
        delete dst[meta.id];
        log("Deleted processed delivery: " + meta.id);
    } catch (e) {
        // Ignore if it doesn't exist
    }
}
