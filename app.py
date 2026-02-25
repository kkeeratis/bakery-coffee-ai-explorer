import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import google.generativeai as genai
import pandas as pd
import time
import re

# --- UI Configuration ---
st.set_page_config(
    page_title="Bakery & Coffee Global Insights", 
    page_icon="🥐", 
    layout="wide"
)

# --- Enhanced Custom CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main { 
        background-color: #fdfaf6; 
    }
    
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        background-color: #4b3621;
        color: white;
        font-weight: 600;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        background-color: #6f4e37;
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    .report-card, .executive-card, .insight-card {
        background-color: white;
        padding: 30px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        margin-bottom: 25px;
        line-height: 1.7;
        color: #2d241e;
    }
    
    .report-card { border-left: 6px solid #8d6e63; }
    .executive-card { border-top: 6px solid #1a237e; background-color: #fcfdfe; }
    .insight-card { border-left: 6px solid #00796b; }
    
    h1, h2, h3 {
        color: #3e2723;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }

    .stTabs [aria-selected="true"] {
        background-color: #f5ebe0;
        border-bottom: 3px solid #6f4e37;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Network Setup ---
def get_secure_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def sanitize_input(text):
    if not text: return ""
    return re.sub(r'[<>{}\[\]]', '', text[:100]).strip()

# --- Advanced Scraping Logic ---
def fetch_trends(category="Both", search_query=""):
    all_headlines = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    sources = []
    if category in ["Bakery", "Both"]: sources.append("https://www.bakeryandsnacks.com/Trends")
    if category in ["Coffee", "Both"]: sources.append("https://www.worldcoffeeportal.com/News")

    session = get_secure_session()

    for url in sources:
        try:
            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            tags_to_check = soup.find_all(['h2', 'h3', 'h4', 'a'])
            for item in tags_to_check:
                text = item.get_text().strip()
                if 35 < len(text) < 150:
                    if any(x in text.lower() for x in ['cookie', 'privacy', 'contact', 'subscribe', 'terms']):
                        continue
                    all_headlines.append(text)
        except:
            continue
            
    unique_all = list(dict.fromkeys(all_headlines))
    
    if search_query:
        filtered = [h for h in unique_all if search_query.lower() in h.lower()]
        if filtered:
            return filtered[:25], True
        else:
            return unique_all[:25], False
    
    return unique_all[:25], True

# --- AI Analysis ---
def analyze_trends(api_key, news_list, focus_topic, mode="General"):
    if not api_key: return "⚠️ Please provide a valid API Key in the sidebar."
    
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferred = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-pro']
        models_to_try = [m for m in preferred if m in available_models] + [m for m in available_models if m not in preferred]

        context = "\n- ".join(news_list)
        safe_focus = sanitize_input(focus_topic)
        
        # Prompts strictly asking for Thai Response for local stakeholders
        if mode == "Brief":
            prompt = f"Act as a C-suite Strategic Advisor. Synthesize core insights from these news items: {context}. Focus on '{safe_focus}'. Provide 3 concise points: 1. Current Trend Landscape, 2. Immediate Strategic Actions, 3. Future Monitoring Items. ANSWER IN THAI LANGUAGE for Thai Executives."
        elif mode == "Executive":
            prompt = f"Act as a Business Consultant. Provide an in-depth strategic analysis for executives regarding: {safe_focus}. Based on: {context}. Structured in 5 sections: Strategic Insights, Business Impact/ROI, Risk Assessment, Executive Roadmap, and Resource Requirements. ANSWER IN THAI LANGUAGE for Thai Executives."
        else:
            prompt = f"Act as a Global Bakery & Coffee Market Expert. Analyze trends and innovation for: {safe_focus}. Based on news: {context}. Provide 4 sections: Global Trends Analysis, Local Market Adaptation, Signature Pairings, and Product Innovation Ideas. ANSWER IN THAI LANGUAGE for Thai Executives."

        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name=model_name)
                response = model.generate_content(prompt)
                return f"*(Analysed by: `{model_name}`)*\n\n" + response.text
            except: continue
        return "❌ AI Processing Failed. Please try again later."
    except Exception as e: return f"❌ Error: {str(e)}"

# --- UI Header ---
st.markdown("<h1 style='text-align: center;'>🥐 Bakery & Coffee Global AI Explorer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.2em; color: #6d4c41;'>Strategic Market Intelligence and Trend Analysis</p>", unsafe_allow_html=True)

# Visual Assets with standardized image format
col_img1, col_img2 = st.columns(2)
with col_img1:
    st.markdown("")
with col_img2:
    st.markdown("")

# --- Sidebar ---
with st.sidebar:
    # Fixed sidebar header with Emoji and Title for better compatibility
    st.markdown("### 🏛️ SYSTEM CONFIG")
    api_key_input = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else st.text_input("Gemini API Key:", type="password")
    
    st.divider()
    category_choice = st.selectbox("Market Category:", ["Both", "Bakery", "Coffee"])
    st.info("💡 Pro Tip: Use English keywords for better search results, but the AI will analyze in Thai.")
    user_focus = sanitize_input(st.text_input("Area of Interest:", placeholder="e.g., Specialty Coffee"))
    
    st.divider()
    st.caption(f"Engine Version: {genai.__version__}")
    st.caption("© 2024 AI Market Intelligence")

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Market Headlines", 
    "💡 Product Strategy", 
    "🎯 Executive Roadmap", 
    "⚡ Quick Insights"
])

with tab1:
    st.subheader("Global Market Intelligence Feed")
    if st.button("🔄 Fetch Latest Trends"):
        with st.spinner("Connecting to global news servers..."):
            data, is_exact = fetch_trends(category_choice, user_focus)
            st.session_state['news_data'] = data
            if user_focus and not is_exact:
                st.warning(f"Note: Specific headlines for '{user_focus}' were not found. Displaying general market trends for AI correlation.")
            elif data:
                st.success(f"Successfully fetched {len(data)} global headlines.")

    if 'news_data' in st.session_state:
        st.table(pd.DataFrame(st.session_state['news_data'], columns=["Global Trending Topics"]))
    else:
        st.info("Click 'Fetch Latest Trends' to start gathering market data.")

with tab2:
    if 'news_data' in st.session_state:
        st.subheader("AI-Driven Product Strategy (Thai Analysis)")
        if st.button("✨ Generate Strategy"):
            with st.spinner("AI is synthesizing market data in Thai..."):
                analysis = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "General")
                st.markdown(f'<div class="report-card">{analysis}</div>', unsafe_allow_html=True)
    else:
        st.info("Please fetch market headlines first.")

with tab3:
    if 'news_data' in st.session_state:
        st.subheader("Strategic Executive Roadmap (Thai Analysis)")
        if st.button("🚀 Develop Roadmap"):
            with st.spinner("Designing executive action plan in Thai..."):
                roadmap = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Executive")
                st.markdown(f'<div class="executive-card">{roadmap}</div>', unsafe_allow_html=True)
    else:
        st.info("Please fetch market headlines first.")

with tab4:
    if 'news_data' in st.session_state:
        st.subheader("Executive Quick Brief (Thai Analysis)")
        if st.button("⚡ Get Quick Insights"):
            with st.spinner("Extracting core insights in Thai..."):
                brief = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Brief")
                st.markdown(f'<div class="insight-card">{brief}</div>', unsafe_allow_html=True)
    else:
        st.info("Please fetch market headlines first.")

st.divider()
st.markdown("<div style='text-align: center; color: #9e9e9e;'>Global AI Insights Engine for Modern Bakeries & Roasteries</div>", unsafe_allow_html=True)