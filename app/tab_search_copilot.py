"""Tab 3 - Vector Search & AI Copilot: semantic delivery search and RAG-powered Q&A."""

from __future__ import annotations
import time

import streamlit as st
import streamlit_shadcn_ui as ui
from couchbase.cluster import Cluster
from openai import OpenAI

import couchbase_client as cb
from config import OPENAI_API_KEY, EMBEDDING_MODEL, CHAT_MODEL, CB_BUCKET, SCOPE_PROCESSED
from styles import status_badge, risk_badge, risk_bar_html, scenario_icon, scenario_friendly_name, icon


# ── Cached Embedding Helper ─────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _get_embedding(question: str) -> list[float]:
    """Generate embedding for a question. Cached for 1 hour to avoid repeat API calls."""
    oai = OpenAI(api_key=OPENAI_API_KEY)
    resp = oai.embeddings.create(model=EMBEDDING_MODEL, input=question)
    return resp.data[0].embedding


# ── Vector Search Tab ───────────────────────────────────────────

def render_search(cluster):
    st.markdown("### Semantic Delivery Search")
    st.markdown("Search deliveries by meaning using Couchbase Vector Search with APPROX_VECTOR_DISTANCE.")

    # Search input + button
    search_col, btn_col = st.columns([5, 1])
    with search_col:
        query = st.text_input("Search Query",
            placeholder="Describe the delivery scenario (e.g., suspicious activity at garage door)",
            label_visibility="collapsed", key="search_query")
    with btn_col:
        search_clicked = st.button("Search", type="primary", use_container_width=True, key="search_btn")

    # Filters row
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        st.markdown('<div class="filter-label">Carrier</div>', unsafe_allow_html=True)
        carrier = st.selectbox("Carrier", ["All", "UPS", "FedEx", "USPS", "Amazon", "DHL"],
                               label_visibility="collapsed", key="filter_carrier")
    with f2:
        st.markdown('<div class="filter-label">Scenario</div>', unsafe_allow_html=True)
        scenario = st.selectbox("Scenario", ["All", "happy_path", "front_door_misdelivery",
                               "package_behind_car", "door_stuck_open", "no_package_placed",
                               "delivery_timeout", "theft_suspicious"],
                               label_visibility="collapsed", key="filter_scenario")
    with f3:
        st.markdown('<div class="filter-label">Status</div>', unsafe_allow_html=True)
        status = st.selectbox("Status", ["All", "completed_success", "completed_risk", "failed", "suspicious"],
                              label_visibility="collapsed", key="filter_status")
    with f4:
        st.markdown('<div class="filter-label">Risk Level</div>', unsafe_allow_html=True)
        risk_level = st.selectbox("Risk", ["All", "critical", "high", "medium", "low"],
                                  label_visibility="collapsed", key="filter_risk")
    with f5:
        st.markdown('<div class="filter-label">Results</div>', unsafe_allow_html=True)
        limit = st.selectbox("Limit", [5, 10, 20, 50], index=1, label_visibility="collapsed", key="filter_limit")

    # Session state for results
    if "search_results" not in st.session_state:
        st.session_state.search_results = None
    if "search_query_display" not in st.session_state:
        st.session_state.search_query_display = None
    if "searched" not in st.session_state:
        st.session_state.searched = False

    # Search execution
    if search_clicked:
        if not query:
            st.warning("Please enter a search query")
        else:
            with st.spinner("Searching similar deliveries..."):
                try:
                    query_vec = _get_embedding(query)
                    results, display_query = cb.vector_search_with_filters(
                        cluster, query_vec,
                        carrier="" if carrier == "All" else carrier,
                        scenario="" if scenario == "All" else scenario,
                        status="" if status == "All" else status,
                        risk_level="" if risk_level == "All" else risk_level,
                        limit=limit,
                    )
                    st.session_state.search_results = results
                    st.session_state.search_query_display = display_query
                    st.session_state.searched = True
                except Exception as e:
                    st.error(f"Search failed: {e}")

    # Results display
    if st.session_state.searched and st.session_state.search_results:
        results = st.session_state.search_results
        st.markdown("---")

        # Result badges
        badge_list = [("Results", "default"), (str(len(results)), "secondary")]
        if carrier != "All":
            badge_list.append((carrier, "outline"))
        if scenario != "All":
            badge_list.append((scenario.replace("_", " "), "outline"))
        if status != "All":
            badge_list.append((status.replace("_", " "), "outline"))
        if risk_level != "All":
            badge_list.append((risk_level, "outline"))
        ui.badges(badge_list=badge_list, class_name="flex gap-2", key="result_badges")

        # Query expander
        if st.session_state.search_query_display:
            with st.expander("View Couchbase Query", expanded=False):
                st.markdown(f'<div class="query-box">{st.session_state.search_query_display}</div>',
                            unsafe_allow_html=True)

                st.markdown("---")
                st.markdown("#### How the Query Works:")
                st.markdown("""
                ```
                1. EMBED QUERY (OpenAI)
                   text-embedding-3-small → 1,536-dim vector

                2. VECTOR SIMILARITY (Couchbase)
                   APPROX_VECTOR_DISTANCE finds most similar deliveries
                   Uses Hyperscale Vector Index with COSINE similarity

                3. SCALAR FILTERS (optional)
                   WHERE carrier = "Amazon" AND scenario_type = "theft_suspicious"
                   Pre-filtering reduces search space before vector search

                4. RANKING (ORDER BY)
                   Results sorted by similarity score
                   Most similar deliveries appear first

                5. LIMIT
                   Returns top N most similar matches
                ```
                """)

                st.markdown("""
                #### Why Hyperscale Vector Index?

                - **Native SQL++**: Uses standard Couchbase query language
                - **Approximate NN**: Fast similarity search at scale
                - **COSINE similarity**: Measures semantic meaning between vectors
                - **Pre-filtering**: Scalar conditions applied before vector search
                - **Single Query**: Combines filtering + similarity in one call
                """)

        # Result cards
        st.markdown("")
        for i, r in enumerate(results, 1):
            score = abs(r.get("score", r.get("similarity", 0)))
            scenario_name = scenario_friendly_name(r.get("scenario_type", ""))
            summary = r.get("knowledge_summary", "No summary available")
            risk_score = r.get("risk_score", 0) or 0
            st.markdown(f"""
            <div class="result-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="flex: 1;">
                        <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                            <span class="result-rank">{i}</span>
                            <span class="result-condition">{scenario_name}</span>
                            <span style="margin-left: 0.75rem;" class="score-badge">Score: {score:.4f}</span>
                        </div>
                        <div class="result-summary">{summary[:250]}{"..." if len(summary) > 250 else ""}</div>
                        <div class="result-details">
                            <span class="detail-item">{icon("truck", size=14, color="#94a3b8")} {r.get('carrier', 'N/A')}</span>
                            <span class="detail-item">{icon("map-pin", size=14, color="#94a3b8")} {r.get('address', 'N/A')}</span>
                            <span class="detail-item">{icon("alert-triangle", size=14, color="#fbbf24")} Risk: {risk_score:.0%}</span>
                            <span class="detail-item" style="color:#4ade80;">{icon("user", size=14, color="#4ade80")} {r.get('owner_name', 'N/A')}</span>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div class="badge {('badge-success' if risk_score < 0.2 else 'badge-risk' if risk_score < 0.75 else 'badge-failed')}">
                            {risk_score:.0%}</div>
                        <div style="color: #64748b; font-size: 0.75rem; margin-top: 0.25rem;">{r.get('status', '').replace('_', ' ')}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    elif st.session_state.searched:
        st.info("No deliveries found matching your criteria. Try adjusting your search or filters.")

    else:
        st.markdown("---")
        st.markdown("""
        ### How to Use

        1. **Enter a natural language query** describing the delivery scenario you're looking for
        2. **Apply filters** to narrow results by carrier, scenario, status, or risk level
        3. **Click Search** to find semantically similar deliveries using vector similarity

        ---

        #### Example Queries
        - `package left outside garage door in the rain`
        - `suspicious person detected near garage after delivery`
        - `garage door stuck open after Amazon delivery`
        - `delivery completed safely with no risk factors`
        """)


# ── AI Copilot Tab ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are the myQ SmartDelivery operations intelligence analyst.
You analyze delivery data from Couchbase to find patterns, explain risks, and recommend actions.

ANALYSIS METHOD:
- Group deliveries by pattern (scenario type, shared risk factors, carrier) — never just list addresses.
- For each group, explain WHY those deliveries are flagged by walking through the event timeline.
  Point out time gaps between events that indicate suspicious activity or system failures.
- Look for cross-delivery correlations: repeated carriers, geographic clusters, common risk factors.

RESPONSE FORMAT:
- Use markdown headers (###) to separate pattern groups.
- Bold delivery IDs, risk levels, and carrier names.
- Show abbreviated event timelines when they reveal the cause (e.g., "14:32 package placed → 14:38 unknown person detected (+6 min gap)").
- End with a prioritized "Recommended Actions" section ranked by severity.

TONE: Concise, decisive, operationally focused. Treat every critical/high risk as requiring action.
Reference specific delivery IDs, addresses, risk factors, and event sequences from the context provided."""

EXAMPLE_QUESTIONS = [
    "What patterns exist in high-risk deliveries?",
    "Walk me through suspicious activity timelines and what triggered alerts",
    "Which carriers or locations have repeat delivery issues?",
]

# RAG flow step definitions (label, icon, color, rgb)
_RAG_STEPS = [
    ("EMBED", "cpu", "#f97316", "249,115,22"),
    ("VECTOR SEARCH", "eye", "#6366f1", "99,102,241"),
    ("BUILD CONTEXT", "clipboard", "#22d3ee", "34,211,238"),
    ("GENERATE", "zap", "#22c55e", "34,197,94"),
]


def _render_rag_flow():
    """Render RAG pipeline flow diagram (process steps only, no timings)."""
    values = ["1,536 dims", "Top 8", "Summarize", "Stream"]
    descs = ["text-embedding-3-small", "Couchbase Hyperscale Index", "Fleet + timeline analysis", "GPT-4o-mini RAG"]

    step_parts = []
    for i, (label, icon_name, color, rgb) in enumerate(_RAG_STEPS):
        step_parts.append(
            f'<div style="text-align:center;padding:0.5rem 0.75rem;background:rgba({rgb},0.1);'
            f'border-radius:8px;border:1px solid rgba({rgb},0.3);min-width:110px;">'
            f'<div style="font-size:0.72rem;color:{color};font-weight:600;">'
            f'{icon(icon_name, size=14, color=color)} {label}</div>'
            f'<div style="font-size:1.1rem;font-weight:700;color:#e2e8f0;">{values[i]}</div>'
            f'<div style="font-size:0.68rem;color:#64748b;">{descs[i]}</div></div>'
        )
        if i < len(_RAG_STEPS) - 1:
            step_parts.append(f'<div style="line-height:1;">{icon("arrow-right", size=20, color="#6366f1")}</div>')

    st.markdown(
        f'<div class="glass-card" style="padding:0.75rem;margin:0.5rem 0;">'
        f'<div style="display:flex;align-items:center;justify-content:center;gap:0.6rem;flex-wrap:wrap;">'
        f'{"".join(step_parts)}</div>'
        f'<div style="text-align:center;margin-top:0.5rem;font-size:0.72rem;color:#64748b;">'
        f'Retrieval Augmented Generation (RAG) &mdash; '
        f'Couchbase Vector Search + OpenAI</div></div>',
        unsafe_allow_html=True)


def _retrieve_context(cluster, question: str) -> dict:
    """RAG Steps 1-4: Embed query, vector search, build context. Returns context + timings."""
    timings = {}

    # Step 1: Generate embedding (cached after first call)
    t0 = time.perf_counter()
    query_vec = _get_embedding(question)
    timings["embed_ms"] = (time.perf_counter() - t0) * 1000

    # Step 2: Vector search
    t0 = time.perf_counter()
    results, display_query = cb.vector_search_with_filters(cluster, query_vec, limit=8)
    timings["search_ms"] = (time.perf_counter() - t0) * 1000

    if not results:
        timings["context_ms"] = 0
        return {"context_text": "", "results": [], "display_query": display_query, "timings": timings}

    # Steps 3-4: Build fleet summary + per-delivery context
    t0 = time.perf_counter()

    n = len(results)
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    carriers = set()
    scenarios = set()
    all_factors = []
    for r in results:
        rs = r.get("risk_score", 0) or 0
        if rs >= 0.75:
            risk_counts["critical"] += 1
        elif rs >= 0.45:
            risk_counts["high"] += 1
        elif rs >= 0.20:
            risk_counts["medium"] += 1
        else:
            risk_counts["low"] += 1
        carriers.add(r.get("carrier", ""))
        scenarios.add(r.get("scenario_type", ""))
        all_factors.extend(r.get("risk_factors", []))

    factor_freq = {}
    for f in all_factors:
        factor_freq[f] = factor_freq.get(f, 0) + 1
    top_factors = sorted(factor_freq, key=factor_freq.get, reverse=True)[:5]

    summary_header = (
        f"FLEET SUMMARY: {n} deliveries retrieved by semantic similarity\n"
        f"Risk distribution: {risk_counts['critical']} critical, {risk_counts['high']} high, "
        f"{risk_counts['medium']} medium, {risk_counts['low']} low\n"
        f"Carriers: {', '.join(sorted(c for c in carriers if c))}\n"
        f"Scenarios: {', '.join(sorted(s.replace('_', ' ') for s in scenarios if s))}\n"
        f"Common risk factors: {', '.join(f.replace('_', ' ') for f in top_factors) if top_factors else 'none'}\n"
    )

    context_parts = [summary_header]
    for i, r in enumerate(results):
        ra = r.get("risk_assessment") or {}
        risk_score = r.get("risk_score", 0) or 0
        level = ra.get("level", "") if ra else ""
        factors = r.get("risk_factors", [])
        recs = ra.get("recommendations", []) if ra else []
        timeline = r.get("event_timeline", [])

        timeline_str = _format_timeline(timeline)

        ctx = (
            f"\n--- Delivery {i+1}: {r.get('id','')} ---\n"
            f"Scenario: {r.get('scenario_type','').replace('_',' ')} | "
            f"Status: {r.get('status','').replace('_',' ')} | "
            f"Carrier: {r.get('carrier','')}\n"
            f"Address: {r.get('address','')} | "
            f"Location: {r.get('delivery_location','').replace('_',' ')}\n"
            f"Owner: {r.get('owner_name','')} (redacted)\n"
            f"Risk: {risk_score:.0%} [{level}]\n"
            f"Risk Factors: {', '.join(f.replace('_',' ') for f in factors) if factors else 'none'}\n"
        )
        if timeline_str:
            ctx += f"Event Timeline:\n{timeline_str}\n"
        ctx += f"Intelligence: {r.get('knowledge_summary','No summary available')}\n"
        if recs:
            ctx += f"Recommendations: {'; '.join(recs)}\n"
        context_parts.append(ctx)

    timings["context_ms"] = (time.perf_counter() - t0) * 1000

    return {
        "context_text": "\n".join(context_parts),
        "results": results,
        "display_query": display_query,
        "timings": timings,
    }


def _format_timeline(event_timeline: list | None, max_events: int = 8) -> str:
    """Format event timeline with short timestamps and time deltas."""
    if not event_timeline:
        return ""
    lines = []
    prev_ts = None
    for evt in event_timeline[:max_events]:
        ts = evt.get("timestamp", "")
        short_ts = ts[11:16] if len(ts) >= 16 else ts
        summary = evt.get("summary", "")
        location = evt.get("location", "")
        evt_type = evt.get("event_type", "")

        # Compute delta from previous event
        delta_str = ""
        if prev_ts and len(ts) >= 19 and len(prev_ts) >= 19:
            try:
                from datetime import datetime
                cur = datetime.fromisoformat(ts[:19])
                prv = datetime.fromisoformat(prev_ts[:19])
                diff_min = int((cur - prv).total_seconds() / 60)
                if diff_min > 0:
                    delta_str = f" +{diff_min}m"
            except (ValueError, TypeError):
                pass

        lines.append(f"  [{short_ts}{delta_str}] {summary} @ {location} ({evt_type})")
        prev_ts = ts

    return "\n".join(lines)


def render_copilot(cluster):
    """AI Copilot with streaming responses and RAG flow visualization."""
    st.markdown("### Ask myQ AI")
    st.markdown("The AI Copilot retrieves relevant delivery records and generates insights based on your questions.")

    # Example questions (3 columns)
    st.markdown("**Try asking:**")
    example_cols = st.columns(3)
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        with example_cols[i]:
            if st.button(q, key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_question = q
                st.rerun()

    st.markdown("---")

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Determine if there's a question to process
    question = None
    if st.session_state.get("pending_question"):
        question = st.session_state.pending_question
        st.session_state.pending_question = None

    # Chat input + Ask button
    col1, col2 = st.columns([5, 1])
    with col1:
        user_input = st.text_input("Ask a question",
            placeholder="Ask anything about deliveries, risks, carriers, or scenarios...",
            label_visibility="collapsed", key="copilot_input")
    with col2:
        ask_clicked = st.button("Ask", type="primary", use_container_width=True, key="copilot_ask")

    if ask_clicked and user_input:
        question = user_input

    # ── Process new question (streaming RAG pipeline) ────────────
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})

        # Show user message
        st.markdown(f'''
        <div class="chat-message user-message">
            <strong>You:</strong> {question}
        </div>
        ''', unsafe_allow_html=True)

        # Steps 1-4: Retrieve context with timing
        try:
            with st.spinner("Retrieving relevant deliveries..."):
                ctx = _retrieve_context(cluster, question)
        except Exception as e:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"Sorry, I couldn't retrieve delivery context: {e}",
                "sources": [],
            })
            st.rerun()

        if not ctx["results"]:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "No relevant deliveries found matching your question. Try rephrasing or asking about a different topic.",
                "sources": [],
                "timings": {**ctx["timings"], "generate_ms": 0,
                            "total_ms": ctx["timings"]["embed_ms"] + ctx["timings"]["search_ms"]},
            })
            st.rerun()

        # Step 5: Stream LLM response
        try:
            oai = OpenAI(api_key=OPENAI_API_KEY)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context from Couchbase knowledge base:\n{ctx['context_text']}\n\nUser question: {question}"},
            ]

            gen_start = time.perf_counter()
            stream = oai.chat.completions.create(model=CHAT_MODEL, messages=messages, temperature=0.3, stream=True)
            gen_timings = {}

            def _token_gen():
                first_token = True
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        if first_token:
                            gen_timings["ttft_ms"] = (time.perf_counter() - gen_start) * 1000
                            first_token = False
                        yield delta.content
                gen_timings["generate_ms"] = (time.perf_counter() - gen_start) * 1000

            full_response = st.write_stream(_token_gen())
        except Exception as e:
            full_response = f"Sorry, I encountered an error generating a response: {e}"
            st.error(full_response)
            gen_timings = {}

        # Build final timings
        timings = ctx["timings"].copy()
        timings["generate_ms"] = gen_timings.get("generate_ms", 0)
        timings["ttft_ms"] = gen_timings.get("ttft_ms", 0)
        timings["total_ms"] = (timings["embed_ms"] + timings["search_ms"]
                               + timings["context_ms"] + timings["generate_ms"])

        # Store in history
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": full_response,
            "sources": ctx["results"],
            "couchbase_query": ctx["display_query"],
            "timings": timings,
        })

        st.rerun()

    # ── Display chat history ─────────────────────────────────────
    if st.session_state.chat_history:
        st.markdown("---")
        for idx, msg in enumerate(st.session_state.chat_history):
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="chat-message user-message">
                    <strong>You:</strong> {msg["content"]}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="chat-message assistant-message">
                    <strong>myQ AI:</strong><br>{msg["content"]}
                </div>
                """, unsafe_allow_html=True)

                # Show RAG pipeline flow with query details
                if msg.get("timings") or msg.get("couchbase_query"):
                    with st.expander("View Couchbase Query", expanded=False):
                        # Flow diagram
                        _render_rag_flow()

                        # Actual Couchbase query
                        if msg.get("couchbase_query"):
                            st.markdown(f'<div class="query-box">{msg["couchbase_query"]}</div>',
                                        unsafe_allow_html=True)

                        st.markdown("---")
                        st.markdown("#### How the RAG Pipeline Works:")
                        st.markdown("""
```
1. EMBED USER QUERY (OpenAI)
   User's natural language question is converted into
   a 1,536-dimension vector using text-embedding-3-small

2. VECTOR SEARCH (Couchbase)
   The query vector is sent to Couchbase SQL++ using
   APPROX_VECTOR_DISTANCE with COSINE similarity
   Hyperscale Vector Index finds the top 8 most
   semantically similar delivery records

3. BUILD CONTEXT FROM RESULTS
   Retrieved deliveries are assembled into structured
   context blocks including:
   - Fleet summary (risk distribution, carriers, scenarios)
   - Per-delivery details (timelines, risk factors, addresses)
   - Intelligence summaries and recommendations

4. FEED CONTEXT + QUESTION TO LLM (OpenAI GPT-4o-mini)
   The Couchbase search results are combined with the
   original user question and sent to the LLM
   The model analyzes patterns across deliveries and
   generates operationally-focused insights

5. STREAM RESPONSE
   The LLM response is streamed token-by-token back
   to the user with cited delivery IDs and sources
```
                        """)

                        st.markdown("""
#### Why Couchbase Vector Search + RAG?

- **Native SQL++**: Vector search is a standard Couchbase query — no external vector DB
- **Single query**: Combines vector similarity + scalar filters in one call
- **Enterprise data grounding**: LLM responses are based on your actual delivery records
- **Cited sources**: Every insight is traceable to specific delivery IDs
- **Real-time**: Vector index updates as new deliveries are processed by Eventing
                        """)

                # Show sources
                if msg.get("sources"):
                    with st.expander(f"View {len(msg['sources'])} source deliveries", expanded=False):
                        for i, src in enumerate(msg["sources"], 1):
                            scenario_name = scenario_friendly_name(src.get("scenario_type", ""))
                            st.markdown(f"""
                            <div class="source-card">
                                <strong>Delivery {i}:</strong> {scenario_name} |
                                {src.get('carrier', 'N/A')} |
                                Risk: {src.get('risk_score', 0):.0%} |
                                {src.get('owner_name', 'N/A')} at {src.get('address', 'N/A')}
                            </div>
                            """, unsafe_allow_html=True)

        # Clear chat button
        if st.button("Clear Chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()
    elif not question:
        st.markdown("---")
        st.markdown("### How it works")
        _render_rag_flow()


# ── Main render function (sub-tabs) ────────────────────────────

def render(cluster: Cluster):
    """Render Vector Search & AI Copilot with sub-tabs."""
    st.markdown('<div class="section-title">Vector Search & AI Copilot</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Search deliveries by semantic meaning and ask natural language questions &mdash; '
        'powered by Couchbase Vector Search + RAG.</div>',
        unsafe_allow_html=True)

    # Auto-detect and create vector index when ready (fallback if watcher hasn't run yet)
    vector_ready, vector_msg = cb.ensure_vector_index(cluster)

    if not vector_ready:
        st.warning(vector_msg)
        st.markdown(
            '<div style="font-size:0.78rem;color:#64748b;margin-top:0.5rem;">'
            'The vector index is created automatically after starting the Event Stream. '
            'Navigate to Command Center and click <b>Start Event Stream</b> to begin.</div>',
            unsafe_allow_html=True)
        return

    selected = ui.tabs(
        options=["Delivery Search", "AI Copilot"],
        default_value="Delivery Search",
        key="search_copilot_tabs",
    )

    st.markdown("")

    if selected == "Delivery Search":
        render_search(cluster)
    else:
        render_copilot(cluster)
