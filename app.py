import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import google.generativeai as genai
import pandas as pd
import time
import re
import json

# --- UI Configuration ---
st.set_page_config(
    page_title="Bakery & Coffee Global Insights", 
    page_icon="🥐", 
    layout="wide"
)

# --- Enhanced Custom CSS for Global Professional Look ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main { 
        background-color: #fcfaf8; 
    }
    
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        background-color: #4b3621;
        color: white;
        font-weight: 600;
        border: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        background-color: #6f4e37;
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    
    .report-card, .executive-card, .insight-card, .dashboard-card {
        background-color: white;
        padding: 30px;
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        margin-bottom: 25px;
        border: 1px solid #f1f1f1;
    }
    
    .report-card { border-left: 8px solid #a1887f; }
    .executive-card { border-top: 8px solid #283593; background-color: #fbfcfe; }
    .insight-card { border-left: 8px solid #00897b; }
    .dashboard-card { border-top: 4px solid #4b3621; }
    
    h1, h2, h3 {
        color: #3e2723;
        font-weight: 700;
    }
    
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }
    </style>
    """, unsafe_allow_html=True)

# --- Network & Scraper ---
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

def fetch_trends(category="Both", search_query=""):
    all_headlines = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    sources = []
    if category in ["Bakery", "Both"]: sources.append("https://www.bakeryandsnacks.com/Trends")
    if category in ["Coffee", "Both"]: sources.append("https://www.worldcoffeeportal.com/News")
    session = get_secure_session()
    for url in sources:
        try:
            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            for item in soup.find_all(['h2', 'h3', 'h4', 'a']):
                text = item.get_text().strip()
                if 35 < len(text) < 150:
                    if any(x in text.lower() for x in ['cookie', 'privacy', 'contact', 'subscribe', 'terms']): continue
                    all_headlines.append(text)
        except: continue
    unique_all = list(dict.fromkeys(all_headlines))
    if search_query:
        filtered = [h for h in unique_all if search_query.lower() in h.lower()]
        return (filtered[:25], True) if filtered else (unique_all[:25], False)
    return unique_all[:25], True

# --- AI Core Logic ---
def analyze_trends(api_key, news_list, focus_topic, mode="General"):
    if not api_key: return "⚠️ Please provide a Gemini API Key in the sidebar."
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferred = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']
        models_to_try = [m for m in preferred if m in available_models] + [m for m in available_models if m not in preferred]
        context = "\n- ".join(news_list)
        safe_focus = sanitize_input(focus_topic)
        
        base_instruction = "IMPORTANT: Provide the analysis in THAI LANGUAGE ONLY."
        
        if mode == "Dashboard":
            # Mode พิเศษสำหรับสร้าง JSON เพื่อทำกราฟ
            prompt = f"""
            Analyze these news headlines and provide a structured JSON response for a business dashboard.
            Headlines: {context}
            Focus: {safe_focus}
            
            Format:
            {{
                "sentiment_score": 0-100 (0=bearish, 100=bullish),
                "market_vibrancy": 0-100,
                "top_categories": {{"Category Name": count}},
                "trending_keywords": {{"Keyword": relevance_score 1-10}},
                "thai_summary": "Short 1-sentence summary in Thai"
            }}
            Return ONLY the JSON string.
            """
        elif mode == "Brief":
            prompt = f"Act as a Strategic Advisor. Synthesize core insights from: {context}. Focus on '{safe_focus}'. Provide 3 points: 1. Current Trends, 2. Immediate Actions, 3. Future Monitoring. {base_instruction}"
        elif mode == "Executive":
            prompt = f"Act as a Business Consultant. In-depth strategy for: {safe_focus} based on: {context}. Sections: Strategic Insights, ROI, Risk, Roadmap, Resources. {base_instruction}"
        else:
            prompt = f"Global Market Expert analysis for: {safe_focus}. News base: {context}. Sections: Global Trends, Thai Market Adaptation, Signatures, Menu Innovation. {base_instruction}"

        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name=model_name)
                # ใช้ GenerationConfig สำหรับ JSON mode ถ้าเป็น Dashboard
                response = model.generate_content(prompt)
                return response.text
            except: continue
        return "❌ AI Processing Failed."
    except Exception as e: return f"❌ System Error: {str(e)}"

# --- Layout Design ---
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>🥐 Bakery & Coffee Global Insights</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1em; color: #8d6e63; margin-top: 0;'>Premier AI Intelligence for Modern Entrepreneurs</p>", unsafe_allow_html=True)

# Correcting the Image Placeholders
col_header_1, col_header_2 = st.columns(2)
with col_header_1:
    st.markdown("")
with col_header_2:
    st.markdown("")

# --- Sidebar Management ---
with st.sidebar:
    st.markdown("")
    st.markdown("### 🏛️ SYSTEM CONTROL")
    
    api_key_input = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else st.text_input("Gemini API Key:", type="password")
    
    st.divider()
    category_choice = st.selectbox("Intelligence Domain:", ["Both", "Bakery", "Coffee"])
    st.info("💡 Hint: Enter keywords like 'Vegan' or 'Arabica' for focused analysis.")
    user_focus = sanitize_input(st.text_input("Special Interest:", placeholder="e.g., Artisan Sourdough"))
    
    st.divider()
    st.caption(f"Engine Status: {genai.__version__} | Active")
    st.caption("© 2026 Bakery AI Global Intelligence")

# --- Interactive Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Market Headlines", 
    "💡 Product Strategy", 
    "🎯 Executive Roadmap", 
    "⚡ Quick Insights",
    "📈 Strategic Dashboard"
])

with tab1:
    st.subheader("Live Global Market Feed")
    if st.button("🔄 Refresh Data Streams"):
        with st.spinner("Accessing global industrial news..."):
            data, is_exact = fetch_trends(category_choice, user_focus)
            st.session_state['news_data'] = data
            if user_focus and not is_exact:
                st.warning(f"Note: Direct matches for '{user_focus}' were sparse. Analyzing related market movements.")
            elif data:
                st.success(f"Successfully integrated {len(data)} market signals.")

    if 'news_data' in st.session_state:
        st.table(pd.DataFrame(st.session_state['news_data'], columns=["Industrial Headlines Found"]))

with tab2:
    if 'news_data' in st.session_state:
        st.subheader("Strategic Product Analysis (Thai)")
        if st.button("✨ Synthesize Strategy"):
            with st.spinner("AI analyzing in Thai for local implementation..."):
                analysis = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "General")
                st.markdown(f'<div class="report-card">{analysis}</div>', unsafe_allow_html=True)

with tab3:
    if 'news_data' in st.session_state:
        st.subheader("C-Level Operational Roadmap (Thai)")
        if st.button("🚀 Draft Roadmap"):
            with st.spinner("Synthesizing executive roadmap..."):
                roadmap = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Executive")
                st.markdown(f'<div class="executive-card">{roadmap}</div>', unsafe_allow_html=True)

with tab4:
    if 'news_data' in st.session_state:
        st.subheader("Daily Insight Brief (Thai)")
        if st.button("⚡ Generate Brief"):
            with st.spinner("Extracting critical insights..."):
                brief = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Brief")
                st.markdown(f'<div class="insight-card">{brief}</div>', unsafe_allow_html=True)

# --- NEW: Tab 5 Dashboard ---
with tab5:
    if 'news_data' in st.session_state:
        st.subheader("Market Visual Insights")
        if st.button("📊 Generate Strategic Dashboard"):
            with st.spinner("AI is calculating market metrics..."):
                raw_json = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Dashboard")
                try:
                    # พยายามแกะ JSON จาก AI
                    clean_json = re.search(r'\{.*\}', raw_json, re.DOTALL).group()
                    dash_data = json.loads(clean_json)
                    
                    # Display Metrics
                    m1, m2 = st.columns(2)
                    m1.metric("Market Sentiment Score", f"{dash_data['sentiment_score']}/100", f"{dash_data['sentiment_score']-50}%")
                    m2.metric("Market Vibrancy Index", f"{dash_data['market_vibrancy']}%")
                    
                    st.divider()
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("#### 🔝 Top Trending Categories")
                        cat_df = pd.DataFrame(dash_data['top_categories'].items(), columns=['Category', 'Count'])
                        st.bar_chart(cat_df.set_index('Category'))
                        
                    with c2:
                        st.markdown("#### 🔍 Key Insight Summary")
                        st.info(dash_data['thai_summary'])
                        st.markdown("---")
                        st.markdown("#### ⭐ Hot Keywords")
                        for kw, score in dash_data['trending_keywords'].items():
                            st.write(f"**{kw}**")
                            st.progress(score / 10)
                            
                except Exception as e:
                    st.error("Could not parse Dashboard data. The AI response might not be in JSON format. Please try again.")
                    with st.expander("Show AI Raw Response"):
                        st.write(raw_json)
    else:
        st.info("Please fetch market headlines first.")

st.divider()
st.markdown("<div style='text-align: center; color: #bdbdbd; font-size: 0.8em;'>Global AI Insights Engine for Premier Food & Beverage Entities</div>", unsafe_allow_html=True)