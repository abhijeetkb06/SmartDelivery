# Couchbase Eventing Deployment Guide
## SmartDelivery - Chamberlain Demo

### Prerequisites
- Data loaded via Go event generator into `rawdata.*` collections
- OpenAI API key active

---

## Function 1: DeliveryKnowledgePipeline

### Purpose
Watches `rawdata.deliveries` for new/updated delivery documents. When a delivery
with `processing_status: "pending"` arrives, it enriches the document with a
knowledge narrative and risk assessment, then writes it to `processeddata.deliveries`.

### Deployment Steps

1. Go to **Capella UI** → **Data Tools** → **Eventing**
2. Click **Add Function**
3. Settings:
   - **Name**: `DeliveryKnowledgePipeline`
   - **Source Bucket**: `chamberlain`
   - **Source Scope**: `rawdata`
   - **Source Collection**: `deliveries`
   - **Eventing Storage** (metadata):
     - Bucket: `chamberlain`
     - Scope: `_default`
     - Collection: `_default`

4. **Bindings** — Add the following:
   | Type   | Alias        | Bucket        | Scope           | Collection  | Access     |
   |--------|-------------|---------------|-----------------|-------------|------------|
   | Bucket | `dst`       | `chamberlain` | `processeddata` | `deliveries`| Read+Write |
   | Bucket | `src_events`| `chamberlain` | `rawdata`       | `events`    | Read       |

5. Paste the code from `eventing/delivery_knowledge_pipeline.js`
6. Click **Save**
7. Click **Deploy** → **Deploy Function**
8. Wait for status to show **Deployed**

---

## Function 2: VectorEmbeddingPipeline

### Purpose
Watches `processeddata.deliveries` for enriched documents. When a delivery with
`processing_status: "processed"` and no embedding arrives, it calls OpenAI to
generate a 1536-dimension embedding vector and marks the document as AI-ready.

### Deployment Steps

1. Go to **Capella UI** → **Data Tools** → **Eventing**
2. Click **Add Function**
3. Settings:
   - **Name**: `VectorEmbeddingPipeline`
   - **Source Bucket**: `chamberlain`
   - **Source Scope**: `processeddata`
   - **Source Collection**: `deliveries`
   - **Eventing Storage** (metadata):
     - Bucket: `chamberlain`
     - Scope: `_default`
     - Collection: `_default`

4. **Bindings** — Add the following:
   | Type   | Alias    | Details                                                    |
   |--------|----------|------------------------------------------------------------|
   | Bucket | `dst`    | Bucket: `chamberlain`, Scope: `processeddata`, Collection: `deliveries`, Access: Read+Write |
   | URL    | `openai` | URL: `https://api.openai.com`, Auth: **Bearer Token**, Token: `<your OPENAI_API_KEY>` |

5. Paste the code from `eventing/vector_embedding_pipeline.js`
6. Click **Save**
7. Click **Deploy** → **Deploy Function**
8. Wait for status to show **Deployed**

---

## Verification

After deploying both functions, check the processing:

1. **Capella UI** → **Data Tools** → **Documents**
2. Select `processeddata.deliveries` → documents should appear with:
   - `processing_status: "processed"` (from Function 1)
   - `knowledge_summary` field with narrative text
   - `embedding` array with 1536 floats (from Function 2)
   - `is_ai_ready: true`

### Expected Flow
```
rawdata.deliveries (pending)
    → Function 1: DeliveryKnowledgePipeline
        → processeddata.deliveries (processed, has narrative)
            → Function 2: VectorEmbeddingPipeline
                → processeddata.deliveries (AI-ready, has embedding)
```

### Troubleshooting
- Check Eventing logs in Capella UI for error messages
- Ensure OpenAI API key is valid and has credits
- If embeddings aren't generated, check the URL binding auth token
- If Function 1 doesn't trigger, verify documents in rawdata.deliveries have `processing_status: "pending"`

---

## After Eventing Processes All Documents

Once all 50 deliveries are processed and have embeddings, create the vector index:

```sql
CREATE INDEX idx_delivery_embedding
ON chamberlain.processeddata.deliveries(embedding VECTOR)
WITH {"dimension": 1536, "similarity": "DOT", "description": "IVF,SQ8"};
```

Run this in the Capella Query Workbench. The IVF index requires training data
(the embeddings), which is why it must be created after eventing has processed
the documents.
