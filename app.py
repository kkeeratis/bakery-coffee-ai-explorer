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
import html

# --- UI Configuration ---
st.set_page_config(
    page_title="Bakery & Coffee Global Insights", 
    page_icon="🥐☕", 
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
        padding: 35px;
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        margin-bottom: 25px;
        border: 1px solid #f1f1f1;
        color: #2d241e;
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
    # อนุญาตเฉพาะตัวอักษร ตัวเลข และช่องว่าง ป้องกัน Injection เบื้องต้น
    return re.sub(r'[<>{}\[\]`\'"]', '', text[:100]).strip()

def safe_html_render(text):
    """ ป้องกัน XSS Injection โดยแปลงแท็ก HTML แต่รักษา Markdown ไว้ """
    return html.escape(text).replace("\n", "<br>")

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
            
            potential_items = soup.find_all(['h2', 'h3', 'h4', 'a'])
            for item in potential_items:
                text = item.get_text().strip()
                if 40 < len(text) < 160:
                    ignore_list = ['privacy', 'cookie', 'subscribe', 'terms', 'contact', 'about us', 'advertise', 'sign in']
                    if any(x in text.lower() for x in ignore_list):
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
        
        base_instruction = "IMPORTANT: คุณต้องตอบเป็นภาษาไทยเท่านั้น โดยสรุปเนื้อหาให้เป็นมืออาชีพและนำไปใช้งานทางธุรกิจได้จริง ห้ามใช้ HTML tags เด็ดขาด"
        
        # กำหนด Configuration เริ่มต้น
        gen_config = genai.types.GenerationConfig(temperature=0.7)
        
        if mode == "Dashboard":
            # บังคับให้ AI ส่งกลับเป็น JSON 100% ป้องกันแอปพัง (JSON Parsing Fix)
            gen_config = genai.types.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json"
            )
            prompt = f"""
            Analyze these news headlines and provide a JSON response.
            Headlines: {context}
            Focus Topic: {safe_focus}
            
            Required JSON Schema:
            {{
                "sentiment_score": integer between 0 and 100,
                "market_vibrancy": integer between 0 and 100,
                "top_categories": {{"Category Name 1": integer, "Category Name 2": integer}},
                "trending_keywords": {{"Keyword 1": integer, "Keyword 2": integer}},
                "thai_summary": "string containing 1 sentence summary in Thai"
            }}
            """
        elif mode == "Brief":
            prompt = f"ทำหน้าที่เป็นประธานที่ปรึกษา สรุปข่าวเหล่านี้: {context} โดยเน้นเรื่อง {safe_focus} ตอบ 3 หัวข้อสั้นๆ: 1.เทรนด์ตอนนี้ 2.สิ่งที่ต้องทำ 3.สิ่งที่ต้องจับตา {base_instruction}"
        elif mode == "Executive":
            prompt = f"วิเคราะห์แผนงานระดับผู้บริหารสำหรับ: {safe_focus} อ้างอิงข้อมูล: {context} แบ่งเป็น 5 ส่วน: Strategic Insights, ROI, Risk, Roadmap, Resources. {base_instruction}"
        else:
            prompt = f"วิเคราะห์ภาพรวมตลาดเบเกอรี่และกาแฟสำหรับ: {safe_focus} ข้อมูลอ้างอิง: {context} แบ่งเป็น 4 ส่วน: Global Trends, Thai Adaptation, Signature Pairings, Menu Ideas. {base_instruction}"

        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name=model_name)
                response = model.generate_content(prompt, generation_config=gen_config)
                
                # หากเป็นโหมด Dashboard ให้คืนค่าเป็น raw text (ที่การันตีว่าเป็น JSON แล้ว)
                if mode == "Dashboard":
                    return response.text
                
                # ทำความสะอาดข้อมูลก่อนส่งกลับ ป้องกัน XSS Injection
                safe_response = response.text.replace("<", "&lt;").replace(">", "&gt;")
                return f"*(Analysed by: `{model_name}`)*\n\n" + safe_response
            except Exception as e:
                print(f"Model Error ({model_name}): {e}") # Log หลังบ้าน
                continue
        return "❌ AI Processing Failed. ขัดข้องหรือโควต้ารายวันอาจจะเต็ม กรุณาลองใหม่ภายหลัง"
    except Exception as e: 
        print(f"System Error: {str(e)}") # Log หลังบ้าน ไม่โชว์รายละเอียดให้ผู้ใช้เห็น
        return "❌ ระบบขัดข้องในการเชื่อมต่อ AI กรุณาตรวจสอบการตั้งค่า"

# --- UI Header ---
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>🥐 Bakery & Coffee Global Insights</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1em; color: #8d6e63; margin-top: 0;'>Professional Market Intelligence Engine</p>", unsafe_allow_html=True)

# Visual Header
col_header_1, col_header_2 = st.columns(2)
with col_header_1:
    st.markdown("")
with col_header_2:
    st.markdown("")

# --- Sidebar ---
with st.sidebar:
    st.markdown("")
    st.header("⚙️ SYSTEM CONTROL")
    api_key_input = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else st.text_input("Gemini API Key:", type="password")
    
    st.divider()
    category_choice = st.selectbox("Market Domain:", ["Both", "Bakery", "Coffee"])
    user_focus = sanitize_input(st.text_input("Special Focus Area:", placeholder="e.g., Plant-based Milk"))
    
    st.divider()
    st.caption(f"Engine Status: {genai.__version__} | Secured")
    st.caption("© 2026 Bakery AI Intelligence Platform")

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Market Headlines", 
    "💡 Product Strategy", 
    "🎯 Executive Roadmap", 
    "⚡ Quick Insights",
    "📈 Strategic Dashboard"
])

with tab1:
    st.subheader("Global Market Intelligence Feed")
    if st.button("🔄 Fetch Latest Trends"):
        with st.spinner("Connecting to global industry servers..."):
            data, is_exact = fetch_trends(category_choice, user_focus)
            st.session_state['news_data'] = data
            if user_focus and not is_exact:
                st.warning(f"Note: Specific mentions of '{user_focus}' are trending implicitly. Displaying broader signals for AI analysis.")
            elif data:
                st.success(f"Successfully integrated {len(data)} latest market signals.")

    if 'news_data' in st.session_state:
        st.table(pd.DataFrame(st.session_state['news_data'], columns=["Trending Industrial Headlines"]))

with tab2:
    if 'news_data' in st.session_state:
        st.subheader("AI Strategic Product Analysis (Thai)")
        if st.button("✨ Synthesize Strategy"):
            with st.spinner("Analysing global trends in Thai..."):
                analysis = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "General")
                # แสดงผลอย่างปลอดภัย ป้องกัน XSS
                st.markdown(f'<div class="report-card">{analysis}</div>', unsafe_allow_html=True)

with tab3:
    if 'news_data' in st.session_state:
        st.subheader("C-Level Roadmap (Thai)")
        if st.button("🚀 Draft Roadmap"):
            with st.spinner("Preparing executive roadmap..."):
                roadmap = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Executive")
                st.markdown(f'<div class="executive-card">{roadmap}</div>', unsafe_allow_html=True)

with tab4:
    if 'news_data' in st.session_state:
        st.subheader("Quick Insight Brief (Thai)")
        if st.button("⚡ Get Summary"):
            with st.spinner("Extracting core brief..."):
                brief = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Brief")
                st.markdown(f'<div class="insight-card">{brief}</div>', unsafe_allow_html=True)

with tab5:
    if 'news_data' in st.session_state:
        st.subheader("Strategic Market Dashboard")
        if st.button("📊 Generate Visualization"):
            with st.spinner("AI is quantifying market data..."):
                raw_json = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Dashboard")
                if "❌" in raw_json:
                    st.error(raw_json)
                else:
                    try:
                        dash_data = json.loads(raw_json)
                        
                        m1, m2 = st.columns(2)
                        m1.metric("Sentiment Score", f"{dash_data.get('sentiment_score', 50)}/100")
                        m2.metric("Market Vibrancy", f"{dash_data.get('market_vibrancy', 50)}%")
                        
                        st.divider()
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown("#### 🔝 Market Categories")
                            if dash_data.get('top_categories'):
                                st.bar_chart(pd.DataFrame(dash_data['top_categories'].items(), columns=['Cat', 'Val']).set_index('Cat'))
                            else:
                                st.info("No category data available.")
                        with c2:
                            st.markdown("#### 🔍 Strategic Insight")
                            st.info(dash_data.get('thai_summary', 'ไม่มีข้อสรุป'))
                            st.markdown("#### ⭐ Hot Keywords")
                            for kw, score in dash_data.get('trending_keywords', {}).items():
                                st.write(f"**{kw}**")
                                st.progress(min(max(score / 10, 0.0), 1.0)) # ป้องกัน Error กรณีคะแนนเกิน
                    except json.JSONDecodeError:
                        st.error("AI could not structure visual data securely. Please try again.")
    else:
        st.info("Fetch headlines first.")

st.divider()
st.markdown("<div style='text-align: center; color: #bdbdbd; font-size: 0.8em;'>Global AI Insights Engine | Secured Enterprise Grade</div>", unsafe_allow_html=True)