"""Tab 3 - Vector Search & AI Copilot: semantic delivery search and RAG-powered Q&A."""

from __future__ import annotations
import streamlit as st
import streamlit_shadcn_ui as ui
from couchbase.cluster import Cluster
from openai import OpenAI

import couchbase_client as cb
from config import OPENAI_API_KEY, EMBEDDING_MODEL, CHAT_MODEL, CB_BUCKET, SCOPE_PROCESSED
from styles import status_badge, risk_badge, risk_bar_html, scenario_icon, scenario_friendly_name


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
                oai = OpenAI(api_key=OPENAI_API_KEY)
                emb_resp = oai.embeddings.create(model=EMBEDDING_MODEL, input=query)
                query_vec = emb_resp.data[0].embedding

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
            risk_score = r.get("risk_score", 0)

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
                            <span class="detail-item">🚚 {r.get('carrier', 'N/A')}</span>
                            <span class="detail-item">📍 {r.get('address', 'N/A')}</span>
                            <span class="detail-item">⚠️ Risk: {risk_score:.0%}</span>
                            <span class="detail-item" style="color:#4ade80;">👤 {r.get('owner_name', 'N/A')}</span>
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

SYSTEM_PROMPT = """You are the myQ SmartDelivery AI assistant for operations teams.
You help operations teams understand package delivery events, garage activity, and security risks.

You have access to real-time data from Couchbase about deliveries, events, and alerts.
When answering questions, reference specific delivery IDs, addresses, and event details from context.

Be concise, helpful, and security-aware. When risk is involved, always recommend appropriate action.
Format your responses with clear structure using bullet points and bold text for key information."""

EXAMPLE_QUESTIONS = [
    "What deliveries had suspicious activity?",
    "Compare delivery outcomes by carrier",
    "Which homes have the highest risk scores?",
]


def render_copilot(cluster):
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

    # Process pending question from example buttons
    if st.session_state.get("pending_question"):
        question = st.session_state.pending_question
        st.session_state.pending_question = None
        _process_question(cluster, question)
        st.rerun()

    # Chat input + Ask button
    col1, col2 = st.columns([5, 1])
    with col1:
        user_input = st.text_input("Ask a question",
            placeholder="Ask anything about deliveries, risks, carriers, or scenarios...",
            label_visibility="collapsed", key="copilot_input")
    with col2:
        ask_clicked = st.button("Ask", type="primary", use_container_width=True, key="copilot_ask")

    # Process typed question
    if ask_clicked and user_input:
        _process_question(cluster, user_input)
        st.rerun()

    # Display chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

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

                # Show Couchbase Query & RAG Flow
                if msg.get("couchbase_query"):
                    with st.expander("View Couchbase Query & RAG Flow", expanded=False):
                        st.markdown("#### Step 1: Vector Search Query")
                        st.markdown(f'<div class="query-box">{msg["couchbase_query"]}</div>',
                                    unsafe_allow_html=True)

                        st.markdown("---")
                        st.markdown("#### Step 2: Context Injected to LLM")
                        st.markdown("The retrieved delivery records are formatted and sent to GPT-4o-mini:")

                        context_preview = msg.get("context_text", "")[:1500]
                        if len(msg.get("context_text", "")) > 1500:
                            context_preview += "\n\n... (truncated)"
                        st.code(context_preview, language=None)

                        st.markdown("---")
                        st.markdown("#### RAG Flow Breakdown")
                        st.markdown("""
                        ```
                        1. USER QUESTION
                           "Which deliveries had suspicious activity?"
                                    │
                                    ▼
                        2. EMBED QUESTION (OpenAI)
                           text-embedding-3-small → 1,536-dim vector
                                    │
                                    ▼
                        3. VECTOR SEARCH (Couchbase)
                           APPROX_VECTOR_DISTANCE finds top 5 similar deliveries
                           Uses Hyperscale Vector Index for fast retrieval
                                    │
                                    ▼
                        4. FORMAT CONTEXT
                           Delivery records → structured text for LLM
                                    │
                                    ▼
                        5. LLM COMPLETION (OpenAI GPT-4o-mini)
                           System prompt + delivery context + user question
                           → Natural language answer with citations
                        ```
                        """)

                # Show sources
                if msg.get("sources"):
                    with st.expander(f"View {len(msg['sources'])} source deliveries", expanded=False):
                        for i, src in enumerate(msg["sources"], 1):
                            scenario = scenario_friendly_name(src.get("scenario_type", ""))
                            st.markdown(f"""
                            <div class="source-card">
                                <strong>Delivery {i}:</strong> {scenario} |
                                {src.get('carrier', 'N/A')} |
                                Risk: {src.get('risk_score', 0):.0%} |
                                {src.get('owner_name', 'N/A')} at {src.get('address', 'N/A')}
                            </div>
                            """, unsafe_allow_html=True)

        # Clear chat button
        if st.button("Clear Chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()
    else:
        st.markdown("""
        ---
        ### How it works

        1. **You ask a question** about deliveries, risks, carriers, or scenarios
        2. **Vector search retrieves** the most relevant delivery records from Couchbase
        3. **GPT-4o-mini analyzes** the retrieved deliveries and generates insights
        4. **Sources are cited** so you can verify the analysis

        This is **Retrieval Augmented Generation (RAG)** - combining your enterprise data with AI reasoning.
        """)


def _process_question(cluster, question):
    """Process a question through the RAG pipeline."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    with st.spinner("Retrieving relevant deliveries and generating response..."):
        oai = OpenAI(api_key=OPENAI_API_KEY)

        # 1. Generate embedding
        emb_resp = oai.embeddings.create(model=EMBEDDING_MODEL, input=question)
        query_vec = emb_resp.data[0].embedding

        # 2. Vector search
        results, display_query = cb.vector_search_with_filters(cluster, query_vec, limit=8)

        # 3. Build context
        context_parts = []
        for i, r in enumerate(results):
            ra = r.get("risk_assessment", {})
            ctx = (
                f"\nDelivery {i+1}: {r.get('id','')}\n"
                f"- Scenario: {r.get('scenario_type','')}\n"
                f"- Status: {r.get('status','')}\n"
                f"- Carrier: {r.get('carrier','')}\n"
                f"- Risk Score: {r.get('risk_score', 0):.2f}\n"
                f"- Risk Level: {ra.get('level','') if ra else 'N/A'}\n"
                f"- Address: {r.get('address','')}\n"
                f"- Location: {r.get('delivery_location','')}\n"
                f"- Homeowner: {r.get('owner_name','')} (redacted)\n"
                f"- Summary: {r.get('knowledge_summary','No summary')}\n"
            )
            if ra and ra.get("recommendations"):
                ctx += f"- Recommendations: {', '.join(ra['recommendations'])}\n"
            context_parts.append(ctx)

        context_text = "\n".join(context_parts)

        # 4. Call GPT
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context from Couchbase knowledge base:\n{context_text}\n\nUser question: {question}"},
        ]
        chat_resp = oai.chat.completions.create(model=CHAT_MODEL, messages=messages, temperature=0.3)
        answer = chat_resp.choices[0].message.content

        st.session_state.chat_history.append({"role": "user", "content": question})
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer,
            "sources": results,
            "couchbase_query": display_query,
            "context_text": context_text,
        })


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
