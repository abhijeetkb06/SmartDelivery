# myQ Smart Delivery Intelligence

**AI-powered package delivery monitoring for your garage -- powered by Couchbase**

A real-time IoT delivery event processing pipeline that demonstrates how Couchbase can power an end-to-end smart delivery platform with **zero middleware**. No Kafka, no Spark, no Lambda -- just Couchbase.

---

## What It Does

This demo simulates a fleet of 100K smart garage homes processing package deliveries in real time. Events flow through Couchbase Eventing for automatic PII redaction, data enrichment, and vector embedding generation -- all serverless, all inside the database.

**Six delivery scenarios** run continuously:
- Happy path delivery
- Door stuck / mechanical failure
- Package behind car (obstruction)
- No package detected (false trigger)
- Delivery timeout
- Theft risk alert

---

## Screenshots

### My myQ -- Homeowner View
The consumer-facing dashboard shows real-time garage door status, active deliveries, and AI-powered notifications that explain what happened in plain English.

![My myQ Tab](screenshots/my-myq-tab.png)

### myQ Command Center -- Fleet Operations
Live fleet monitoring with real-time stats across all 1 million homes. Watch deliveries, alerts, and AI-ready records climb at 50,000+ ops/sec. Includes live pipeline throughput metrics and automatic PII redaction powered by Couchbase Eventing.

![myQ Command Center](screenshots/command-center-tab.png)

### Vector Search & AI Copilot
Semantic delivery search using Couchbase Vector Search with `APPROX_VECTOR_DISTANCE`. Ask natural language questions about deliveries and get RAG-powered answers grounded in real event data.

![Vector Search & AI Copilot](screenshots/vector-search-ai-tab.png)

---

## Architecture

```
Go Event Generator (50,000+ ops/sec)
        |
        v
  Couchbase Capella
  +-----------------------------------------+
  |  KV Store (sub-ms reads/writes)         |
  |       |                                 |
  |  Eventing Functions (serverless)        |
  |    - PII redaction (SSN, email, phone)  |
  |    - Risk scoring & geo-tagging         |
  |    - Scenario classification            |
  |    - Vector embedding generation        |
  |       |                                 |
  |  Vector Search Index (APPROX_VECTOR_DISTANCE) |
  |  N1QL Analytics                         |
  +-----------------------------------------+
        |
        v
  Streamlit Dashboard (3 tabs)
    - My myQ (homeowner view)
    - Command Center (fleet ops)
    - Vector Search & AI Copilot (RAG)
```

**Key: No middleware.** Couchbase Eventing replaces what would typically require Kafka + Spark + Lambda + a separate vector database.

---

## High-Throughput Event Generator

The Go-based event generator uses a **producer-consumer pattern** with the Couchbase `collection.Do()` bulk API:

- **40 parallel worker goroutines** consuming from a buffered channel
- **Batch writes of 100 documents** per bulk operation
- **Atomic counters** for real-time throughput metrics
- Result: **40k to 80,000+ ops/sec** sustained depending on network speed (570x faster than individual upserts)

```bash
cd event-generator
go build -o smart-delivery-gen .
./smart-delivery-gen --continuous --workers 40 --batch 100
```

---

## Couchbase Services Used

| Service | Purpose |
|---------|---------|
| **KV** | Sub-millisecond document reads/writes for delivery events |
| **Eventing** | Serverless PII redaction, data enrichment, vector embedding triggers |
| **Vector Search** | Semantic similarity search with `APPROX_VECTOR_DISTANCE` |
| **N1QL** | Ad-hoc SQL++ analytics and aggregations |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Go 1.21+ (needed to compile the event generator binary -- see below)
- Couchbase Capella cluster (or self-managed 7.6+)
- OpenAI API key (for embeddings + RAG)

### Setup

```bash
# Clone
git clone https://github.com/abhijeetkb06/SmartDelivery.git
cd SmartDelivery

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure (see Environment Configuration below)
cp .env.example .env
# Edit .env with your credentials
```

### Building the Event Generator

The Go event generator binary (`event-generator/smart-delivery-gen`) is not checked into git and must be compiled after cloning. `run_dashboard.sh`, `run_generator.sh`, and the Streamlit dashboard all **auto-build** it if Go is on your PATH.

To build manually:

```bash
cd event-generator
go build -o smart-delivery-gen .
cd ..
```

Verify it works:

```bash
./event-generator/smart-delivery-gen --help
```

### Environment Configuration

Configuration is split into two files:

- **`.env`** -- Secrets only (passwords, API keys). Gitignored -- you must create it after every fresh clone.
- **`settings.toml`** -- Operational config (bucket name, generator rate, AI models, dashboard port). Checked into git -- works out of the box.

After copying `.env.example` to `.env`, fill in your credentials:

```bash
# ── Couchbase Capella Connection ──
CB_CONN_STR=couchbases://cb.<your-cluster>.cloud.couchbase.com
CB_USERNAME=<username>
CB_PASSWORD=<password>

# ── Capella Management API ──
CAPELLA_API_KEY=<capella-api-key>
CAPELLA_API_SECRET=<capella-api-secret-base64>

# ── OpenAI ──
OPENAI_API_KEY=<openai-api-key>
```

Operational settings are in `settings.toml` (no need to edit unless you want to tune):

```toml
[generator]
rate = 5000           # deliveries/sec
workers = 50          # parallel goroutines
batch = 200           # docs per bulk write

[ai]
embedding_model = "text-embedding-3-small"
chat_model = "gpt-4o-mini"

[dashboard]
port = 8503
```

**Where to get each value:**

| Variable | Where to find it |
|----------|-----------------|
| `CB_CONN_STR` | Capella UI -> Cluster -> Connect -> Connection String (starts with `couchbases://`) |
| `CB_USERNAME` | Capella UI -> Cluster -> Settings -> Database Access -> create a database user |
| `CB_PASSWORD` | Set when creating the database user above |
| `CAPELLA_API_KEY` | Capella UI -> Settings (org level) -> API Keys -> Create API Key -> copy the Key ID |
| `CAPELLA_API_SECRET` | Shown once when creating the API key -- copy the base64-encoded secret token |
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) -> Create new secret key |

**Capella cluster prerequisites (do these before running any scripts):**

1. **IP Whitelist** -- Capella UI -> Cluster -> Settings -> Allowed IP Addresses -> Add your IP (or `0.0.0.0/0` for demo)
2. **Database user** -- Capella UI -> Cluster -> Settings -> Database Access -> Create Credentials (read/write on all buckets)
3. **Management API key** -- Capella UI -> Settings -> API Keys -> Create API Key (Organization Owner or Project Owner role)

### Running the Demo

```bash
# Create bucket, scopes, collections, indexes, and deploy eventing
./reset_bucket.sh

# Run the dashboard
./run_dashboard.sh

# In another terminal -- start the event generator
./run_generator.sh
```

### Demo Scripts

All demo scripts live at the repo root. Run them from the `SmartDelivery/` directory.

| Script | Purpose |
|--------|---------|
| `./reset_bucket.sh` | Nuke bucket + eventing, recreate everything from scratch |
| `./run_dashboard.sh` | Launch Streamlit dashboard + open browser (default port 8503) |
| `./run_generator.sh` | Build and start Go event generator (5000/sec default) |
| `./kill_generator.sh` | Emergency kill switch for the generator |
| `./vector_index.sh` | Create the vector search index (after embeddings exist) |

### Couchbase Eventing Functions

The eventing functions are automatically deployed by `reset_bucket.sh` via `scripts/setup_couchbase.py`.
- `delivery_knowledge_pipeline.js` -- PII redaction + data enrichment
- `vector_embedding_pipeline.js` -- Automatic OpenAI embedding generation

See [eventing/DEPLOY.md](eventing/DEPLOY.md) for manual deployment instructions.

---

## Project Structure

```
SmartDelivery/
  reset_bucket.sh            # Nuke + recreate bucket from scratch
  run_dashboard.sh           # Launch Streamlit dashboard
  run_generator.sh           # Build & start Go event generator
  kill_generator.sh          # Emergency kill switch for generator
  vector_index.sh            # Create vector search index
  app/
    main.py                  # Streamlit entry point (3 tabs)
    tab_home.py              # My myQ -- homeowner dashboard
    tab_ops.py               # Command Center -- fleet operations
    tab_search_copilot.py    # Vector Search & AI Copilot
    couchbase_client.py      # Couchbase connection + queries
    charts.py                # Plotly chart components
    styles.py                # Dark theme CSS
    config.py                # Environment config
  event-generator/
    main.go                  # Producer-consumer bulk loader
    couchbase/client.go      # Couchbase Go SDK connection
    generator/               # Event, delivery, home generators
    models/                  # Go structs (event, delivery, alert, home)
    config/config.go         # CLI flags and config
  eventing/
    delivery_knowledge_pipeline.js   # PII redaction + enrichment
    vector_embedding_pipeline.js     # Vector embedding generation
  scripts/
    setup_couchbase.py       # Bucket/scope/collection/index setup
    vector_index.py          # Vector index creation
```

---

## Built With

- [Couchbase Capella](https://cloud.couchbase.com) -- Cloud database platform
- [Couchbase Go SDK](https://docs.couchbase.com/go-sdk/current/hello-world/overview.html) -- High-throughput bulk operations
- [Streamlit](https://streamlit.io) -- Python dashboard framework
- [OpenAI](https://openai.com) -- Embeddings + chat completions for RAG
