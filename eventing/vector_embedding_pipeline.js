/*
 * VectorEmbeddingPipeline
 * ───────────────────────
 * Couchbase Eventing Function #2
 *
 * Source:   smartdelivery.processeddata.deliveries
 * Bindings:
 *   - Bucket alias "dst"     → smartdelivery.processeddata.deliveries (read+write)
 *   - URL    alias "openai"  → https://api.openai.com  (auth: Bearer <OPENAI_API_KEY>)
 *
 * Trigger: fires on every mutation in processeddata.deliveries
 * Action:  generates OpenAI embedding for the enriched delivery,
 *          stores the 1536-dim vector, marks doc as AI-ready
 *
 * Note: Self-mutations (when this function updates the same doc) are
 *       NOT re-processed by Eventing, so there is no infinite loop.
 *       The guard clause below is an extra safety measure.
 */

function OnUpdate(doc, meta) {
    // Guard: skip if already has embedding or not yet enriched
    if (doc.is_ai_ready === true) return;
    if (doc.processing_status !== "processed") return;
    if (doc.embedding && doc.embedding.length > 0) return;

    try {
        // ── Build text for embedding ──
        var text = doc.embedding_text || doc.knowledge_summary || "";
        if (!text || text.length < 10) {
            log("SKIP " + meta.id + ": no text for embedding");
            return;
        }

        // ── Call OpenAI Embeddings API ──
        var request = {
            path: "/v1/embeddings",
            headers: {
                "Content-Type": "application/json"
            },
            body: {
                "model": "text-embedding-3-small",
                "input": text
            }
        };

        var response = curl("POST", openai, request);

        if (response.status !== 200) {
            log("ERROR embedding " + meta.id + ": HTTP " + response.status +
                " body=" + JSON.stringify(response.body).substring(0, 200));
            return;
        }

        var result = response.body;
        if (!result || !result.data || !result.data[0] || !result.data[0].embedding) {
            log("ERROR embedding " + meta.id + ": unexpected response structure");
            return;
        }

        var embedding = result.data[0].embedding;

        // ── Update the document with embedding ──
        doc.embedding = embedding;
        doc.is_ai_ready = true;
        doc.embedding_model = "text-embedding-3-small";
        doc.embedding_dimensions = embedding.length;
        doc.embedding_generated_at = new Date().toISOString();

        dst[meta.id] = doc;

        log("Embedded delivery: " + meta.id +
            " | dims=" + embedding.length +
            " | text_len=" + text.length);
    } catch (e) {
        log("ERROR embedding " + meta.id + ": " + e);
    }
}

function OnDelete(meta, options) {
    // No action needed on delete - the doc is already gone
}
