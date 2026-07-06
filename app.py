import os
import sys
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Add project root directory to path to ensure modules are found
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from analytics.engine import AnalyticsEngine, CLASSIFIED_DATA_PATH
from rag.indexer import CivicRAG
from agent.handler import ConversationalAgent

# Page configuration
st.set_page_config(
    page_title="CityPulse AI | Civic Intelligence",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium CSS styling (custom fonts, gradients, glassmorphism cards)
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
    /* Main app styles */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0f121d 0%, #151a30 100%);
        color: #e2e8f0;
    }
    
    /* Header card styling */
    .header-card {
        background: linear-gradient(90deg, rgba(108, 93, 211, 0.25) 0%, rgba(0, 196, 140, 0.15) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        backdrop-filter: blur(12px);
    }
    .header-title {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 32px;
        color: #ffffff;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .header-subtitle {
        font-size: 16px;
        color: #a0aec0;
        margin: 6px 0 0 0;
    }
    
    /* KPI metric cards style */
    .metric-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 20px;
        text-align: left;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    }
    .metric-label {
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 28px;
        color: #ffffff;
        margin-top: 4px;
        margin-bottom: 4px;
    }
    .metric-delta {
        font-size: 13px;
        font-weight: 500;
    }
    .delta-up { color: #f87171; }
    .delta-down { color: #4ade80; }
    
    /* Section headers */
    .section-header {
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        font-size: 20px;
        color: #ffffff;
        margin-bottom: 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 8px;
    }
    
    /* Custom table highlighting */
    div[data-testid="stDataFrame"] {
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Chat bubbles custom style */
    .user-msg {
        background-color: rgba(108, 93, 211, 0.15);
        border-left: 4px solid #6c5dd3;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    
    .agent-msg {
        background-color: rgba(30, 41, 59, 0.5);
        border-left: 4px solid #00c48c;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize engines and agents in session state for speed/caching
@st.cache_resource
def init_agent():
    return ConversationalAgent()

@st.cache_resource
def init_rag():
    rag = CivicRAG()
    rag.load_index()
    return rag

@st.cache_resource
def init_analytics():
    return AnalyticsEngine()

agent = init_agent()
rag_indexer = init_rag()
analytics_engine = init_analytics()

# Load main classified data for calculations
@st.cache_data
def load_cached_data():
    df = pd.read_csv(CLASSIFIED_DATA_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

try:
    df_data = load_cached_data()
except Exception as e:
    st.error(f"Error loading classified data: {e}. Make sure to run generator and classifier first!")
    st.stop()

# Header Banner
st.markdown("""
<div class="header-card">
    <div class="header-title">🏙️ CityPulse AI</div>
    <div class="header-subtitle">Conversational Civic Intelligence Platform & Prioritization Engine for Municipal Ward Officers</div>
</div>
""", unsafe_allow_html=True)

# Sidebar setup
with st.sidebar:
    st.markdown("### 🛠️ PLATFORM CONTROL PANEL")
    
    # Showcase Fallback Systems explicitly
    st.markdown("#### Operational Status")
    
    # 1. Gemini / Mistral status
    if agent.use_gemini:
        st.success("🟢 Gemini API: LIVE")
    elif agent.use_mistral:
        st.success("🟢 Mistral API: LIVE")
    else:
        st.warning("🟡 Gemini API: MOCK (fallback)")
        st.caption("⚠️ `GEMINI_API_KEY` (or Mistral key) is not set or the API connection test failed. Local heuristic processing is active.")
        
    # 2. BigQuery status
    if analytics_engine.use_bigquery:
        st.success("🟢 BigQuery: LIVE")
    else:
        st.info("🔵 BigQuery: LOCAL (fallback)")
        st.caption("ℹ️ `USE_BIGQUERY` set to false or Google credentials invalid/missing. Local CSV analytics engine is active.")
        
    # 3. RAG Status
    if rag_indexer.engine_type == "faiss":
        st.success("🟢 RAG Search: FAISS INDEX")
    elif rag_indexer.engine_type == "tfidf":
        st.info("🔵 RAG Search: scikit-learn TF-IDF")
    else:
        st.warning("🟡 RAG Search: PURE-PYTHON TF-IDF")
        
    st.divider()
    
    # Ward Filter
    st.markdown("#### Operations Overview")
    selected_wards = st.multiselect(
        "Filter Wards for Trend Charts",
        options=sorted(df_data["ward_name"].unique()),
        default=["Ward 4", "Ward 3", "Ward 7"]
    )
    
    selected_categories = st.multiselect(
        "Filter Categories for Trend Charts",
        options=sorted(df_data["category_classified"].unique()),
        default=["pothole", "water_leak", "garbage"]
    )
    
    st.divider()
    st.caption("CityPulse AI APAC Hackathon Edition - Smarter Communities Track")

# Calculate Global KPIs for latest week vs prior week
latest_week_start = df_data["timestamp"].dt.to_period("W").dt.start_time.max()
prev_week_start = latest_week_start - pd.Timedelta(weeks=1)

df_latest = df_data[df_data["timestamp"].dt.to_period("W").dt.start_time == latest_week_start]
df_prev = df_data[df_data["timestamp"].dt.to_period("W").dt.start_time == prev_week_start]

total_complaints = len(df_data)
active_open_complaints = len(df_data[df_data["status"] == "open"])
resolved_complaints = len(df_data[df_data["status"] == "resolved"])
resolution_rate = (resolved_complaints / total_complaints) * 100

latest_complaints = len(df_latest)
prev_complaints = len(df_prev)
wow_growth = ((latest_complaints - prev_complaints) / prev_complaints * 100) if prev_complaints > 0 else 0

# Count active spike anomalies (>50% WoW increase)
spikes_df = analytics_engine.get_wow_spikes()
latest_spikes = spikes_df[
    (pd.to_datetime(spikes_df["complaint_week"]) == latest_week_start) & 
    (spikes_df["wow_growth_percentage"] > 50.0)
]
num_spikes = len(latest_spikes)

# Render Custom CSS KPIs
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Active Open Complaints</div>
        <div class="metric-value">{active_open_complaints:,}</div>
        <div class="metric-delta">Total Logged: {total_complaints:,}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Resolution Rate</div>
        <div class="metric-value">{resolution_rate:.1f}%</div>
        <div class="metric-delta delta-down">✔ {resolved_complaints:,} Closed Cases</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">WoW Volume Trend</div>
        <div class="metric-value">{latest_complaints:,}</div>
        <div class="metric-delta delta-up">▲ {wow_growth:+.1f}% vs last week</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Active WoW Spikes (>50%)</div>
        <div class="metric-value">{num_spikes} Wards/Cats</div>
        <div class="metric-delta delta-up">⚠️ Requires Attention</div>
    </div>
    """, unsafe_allow_html=True)

st.write("") # Spacer

# Tabs Layout
tab_priority, tab_chat, tab_rag = st.tabs([
    "📈 Civic Priority Index & Trends", 
    "💬 CityPulse AI Agent Chat", 
    "🔍 RAG Solution Finder & Inspector"
])

# ================= TAB 1: PRIORITY & TRENDS =================
with tab_priority:
    col_left, col_right = st.columns([11, 9])
    
    with col_left:
        st.markdown('<div class="section-header">🚨 Ward Urgency Priority List</div>', unsafe_allow_html=True)
        st.write("Wards are ranked using a weighted index: `(Open Complaints * 0.4) + (Avg Urgency * 10) + (WoW Growth * 0.2)`.")
        
        # Load Rankings
        rankings_df = analytics_engine.get_ward_rankings()
        
        # Format table with highlighting and icons
        styled_rankings = rankings_df.copy()
        styled_rankings.columns = [
            "Ward Name", "Urgency Index", "Open Complaints", "Avg Complaint Urgency", 
            "WoW Growth %", "Top Issue Area", "WoW Anomaly Spikes (>50%)"
        ]
        
        # Display DataFrame nicely
        st.dataframe(
            styled_rankings,
            use_container_width=True,
            column_config={
                "Urgency Index": st.column_config.NumberColumn(format="%.2f"),
                "Avg Complaint Urgency": st.column_config.NumberColumn(format="%.2f"),
                "WoW Growth %": st.column_config.NumberColumn(format="%.1f%%"),
                "WoW Anomaly Spikes (>50%)": st.column_config.TextColumn()
            },
            hide_index=True
        )
        
    with col_right:
        st.markdown('<div class="section-header">📉 Weekly Trend Analytics</div>', unsafe_allow_html=True)
        st.write("Aggregated weekly complaint frequency for selected filters:")
        
        # Aggregate weekly trends
        df_filtered = df_data[
            (df_data["ward_name"].isin(selected_wards)) & 
            (df_data["category_classified"].isin(selected_categories))
        ].copy()
        
        df_filtered["complaint_week"] = df_filtered["timestamp"].dt.to_period("W").dt.start_time
        trend_df = df_filtered.groupby(["complaint_week", "ward_name", "category_classified"]).size().reset_index(name="complaint_count")
        
        if len(trend_df) > 0:
            fig = px.line(
                trend_df,
                x="complaint_week",
                y="complaint_count",
                color="ward_name",
                line_dash="category_classified",
                labels={"complaint_week": "Week Start Date", "complaint_count": "Complaints", "ward_name": "Ward", "category_classified": "Category"},
                template="plotly_dark",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=10, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data matches selected sidebar filters.")

# ================= TAB 2: CONVERSATIONAL AGENT CHAT =================
with tab_chat:
    st.markdown('<div class="section-header">💬 Grounded Conversational AI Panel</div>', unsafe_allow_html=True)
    st.write("Ask natural-language questions to analyze trends, priority rankings, or retrieve past resolutions. The assistant uses live grounding from the data engine and RAG index.")
    
    # Initialize message memory in session state
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I am CityPulse AI. I have analyzed current weekly complaint rankings and past resolutions. Ask me things like:\n- *'Which wards need urgent attention this week?'*\n- *'What is causing the spike in Ward 4?'*\n- *'How did we resolve similar streetlight issues?'*"}
        ]
        
    # Render chat history
    for message in st.session_state.messages:
        role_class = "user-msg" if message["role"] == "user" else "agent-msg"
        st.markdown(f'<div class="{role_class}"><b>{"👤 Officer" if message["role"] == "user" else "🤖 CityPulse AI"}:</b><br>{message["content"]}</div>', unsafe_allow_html=True)
        
    # Accept user input
    if user_query := st.chat_input("Enter your query (e.g., 'What is causing the spike in Ward 4?'):"):
        # Display user message
        st.markdown(f'<div class="user-msg"><b>👤 Officer:</b><br>{user_query}</div>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "user", "content": user_query})
        
        # Generate response using agent
        with st.spinner("Analyzing operational records and synthesizing response..."):
            agent_response = agent.generate_response(user_query)
            
        # Display agent response
        st.markdown(f'<div class="agent-msg"><b>🤖 CityPulse AI:</b><br>{agent_response}</div>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": agent_response})
        
        # Rerun to clear input and adjust scroll
        st.rerun()

# ================= TAB 3: RAG INSPECTOR =================
with tab_rag:
    st.markdown('<div class="section-header">🔎 Interactive RAG Solution Finder</div>', unsafe_allow_html=True)
    st.write("Browse open complaints in the current week, select one, and immediately search the RAG index to find the top-3 most similar past complaints and their successful resolutions.")
    
    col_sel_ward, col_sel_comp = st.columns(2)
    
    # Get active open complaints from latest week
    open_latest_df = df_latest[df_latest["status"] == "open"]
    
    with col_sel_ward:
        sel_ward = st.selectbox(
            "Select Ward to view open complaints:",
            options=sorted(df_data["ward_name"].unique())
        )
        
    ward_open = open_latest_df[open_latest_df["ward_name"] == sel_ward]
    
    if len(ward_open) > 0:
        with col_sel_comp:
            selected_desc = st.selectbox(
                "Select active open complaint to inspect resolutions:",
                options=ward_open["description_text"].tolist()
            )
            
        # Fetch corresponding complaint details
        target_complaint = ward_open[ward_open["description_text"] == selected_desc].iloc[0]
        
        st.divider()
        
        col_comp_details, col_rag_matches = st.columns(2)
        
        with col_comp_details:
            st.markdown("#### 📋 Selected Complaint Details")
            st.write(f"**ID:** `{target_complaint['complaint_id']}`")
            st.write(f"**Category:** `{target_complaint['category_classified'].upper()}`")
            st.write(f"**Urgency Severity Score (Gemini):** `{target_complaint['urgency_score']}/5`")
            st.write(f"**Description:** \"*{target_complaint['description_text']}*\"")
            
        with col_rag_matches:
            st.markdown("#### 🧠 Grounded Similar Past Resolutions (RAG top-3)")
            
            with st.spinner("Querying FAISS/TF-IDF index for historic resolutions..."):
                rag_matches = rag_indexer.search(selected_desc, k=3)
                
            if len(rag_matches) > 0:
                for idx, match in enumerate(rag_matches):
                    with st.expander(f"Match #{idx+1}: {match['category'].title()} (Similarity: {match['score']:.2f})"):
                        st.markdown(f"**Past Complaint:** \"*{match['description_text']}*\"")
                        st.markdown(f"**Verified Action Taken:** ✅ *{match['resolution_notes']}*")
            else:
                st.info("No matching historical records found in index.")
    else:
        st.info(f"No open complaints reported in {sel_ward} for the current week.")
