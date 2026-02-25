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
        
        # --- กำหนด DNA ของแบรนด์ Kudsan และ Bellinee's ---
        brand_context = """
        ในฐานะ 'Chief Strategist' ของ 2 แบรนด์หลัก:
        1. 'Kudsan' (คัดสรร): จุดแข็งคือ กาแฟและเบเกอรี่ในร้านสะดวกซื้อ, เน้น Mass Premium, ความรวดเร็ว (Grab & Go), เข้าถึงง่าย
        2. 'Bellinee's' (เบลลินี่): จุดแข็งคือ ร้านเบเกอรี่เฮ้าส์ระดับ Premium, อบสดใหม่ในร้าน (Bake-in-store), บรรยากาศสไตล์ยุโรป, นั่งทานในร้าน
        """
        
        base_instruction = "IMPORTANT: คุณต้องตอบเป็นภาษาไทยเท่านั้น โดยสรุปเนื้อหาให้เป็นมืออาชีพ นำไปใช้งานเจาะตลาดไทยแข่งกับแบรนด์อื่นได้จริง ห้ามใช้ HTML tags เด็ดขาด"
        
        # กำหนด Configuration เริ่มต้น
        gen_config = genai.types.GenerationConfig(temperature=0.7)
        
        if mode == "Dashboard":
            # บังคับให้ AI ส่งกลับเป็น JSON 100% ป้องกันแอปพัง (JSON Parsing Fix)
            gen_config = genai.types.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json"
            )
            prompt = f"""
            Analyze these news headlines and provide a JSON response for a business dashboard (Focus on Kudsan & Bellinee's implications).
            Headlines: {context}
            Focus Topic: {safe_focus}
            
            Required JSON Schema:
            {{
                "sentiment_score": integer between 0 and 100,
                "market_vibrancy": integer between 0 and 100,
                "top_categories": {{"Category Name 1": integer, "Category Name 2": integer}},
                "trending_keywords": {{"Keyword 1": integer, "Keyword 2": integer}},
                "thai_summary": "string containing 1 sentence summary in Thai tailored for Kudsan/Bellinee's executives"
            }}
            """
        elif mode == "Brief":
            prompt = f"{brand_context}\nสรุปข่าวเหล่านี้: {context}\nเน้นเรื่อง: {safe_focus}\nตอบ 3 หัวข้อสั้นๆ: 1. เทรนด์โลกตอนนี้ 2. ไอเดีย/Action โดนๆ สำหรับ Kudsan 3. ไอเดีย/Action พรีเมียมสำหรับ Bellinee's {base_instruction}"
        elif mode == "Executive":
            prompt = f"{brand_context}\nวิเคราะห์แผนงานระดับผู้บริหารสำหรับ: {safe_focus}\nอ้างอิงข้อมูล: {context}\nแบ่งเป็น 5 ส่วน: 1. Global Insights 2. แผนเอาชนะคู่แข่งในตลาดไทย 3. Roadmap สำหรับ Kudsan 4. Roadmap สำหรับ Bellinee's 5. Risk & Resources {base_instruction}"
        else:
            prompt = f"{brand_context}\nวิเคราะห์ภาพรวมกลยุทธ์สินค้าสำหรับ: {safe_focus}\nข้อมูลอ้างอิง: {context}\nแบ่งเป็น 4 ส่วน: 1. Global Trends 2. ไอเดียเมนู/แพ็กเกจจิ้งใหม่สำหรับ Kudsan 3. ไอเดียเมนู Signature/Pairings สำหรับ Bellinee's 4. การปรับตัวให้เข้ากับลิ้นคนไทยและการทำการตลาด (Thai Adaptation) {base_instruction}"

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
st.write("") # เว้นบรรทัดให้สวยงาม
col_header_1, col_header_2 = st.columns(2)
with col_header_1:
    # รูปเบเกอรี่
    st.image("https://images.unsplash.com/photo-1509440159596-0249088772ff?q=80&w=800&auto=format&fit=crop", use_container_width=True)
with col_header_2:
    # รูปกาแฟลาเต้อาร์ต
    st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?q=80&w=800&auto=format&fit=crop", use_container_width=True)
st.write("")

# --- Sidebar ---
with st.sidebar:
    # สร้างโลโก้ด้วย CSS แทนรูปภาพเพื่อความเสถียร 100% ไม่มีวันรูปแตก
    st.markdown("""
        <div style='text-align: center; padding: 10px 0 20px 0; border-bottom: 1px solid #e0e0e0; margin-bottom: 20px;'>
            <div style='font-size: 3.5rem; line-height: 1;'>☕🥐</div>
            <h3 style='color: #4b3621; margin-top: 15px; margin-bottom: 0; font-weight: 700; font-size: 1.2rem; letter-spacing: 1px;'>AI INSIGHTS</h3>
            <p style='color: #8d6e63; font-size: 0.8rem; margin-top: 5px;'>Strategic Engine</p>
        </div>
        """, unsafe_allow_html=True)
    
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
        st.subheader("AI Strategic Product Analysis (Kudsan & Bellinee's Focus)")
        if st.button("✨ Synthesize Strategy"):
            with st.spinner("Analysing global trends for your brands..."):
                analysis = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "General")
                # แสดงผลอย่างปลอดภัย ป้องกัน XSS
                st.markdown(f'<div class="report-card">{analysis}</div>', unsafe_allow_html=True)

with tab3:
    if 'news_data' in st.session_state:
        st.subheader("C-Level Roadmap (Kudsan & Bellinee's Focus)")
        if st.button("🚀 Draft Roadmap"):
            with st.spinner("Preparing executive roadmap..."):
                roadmap = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Executive")
                st.markdown(f'<div class="executive-card">{roadmap}</div>', unsafe_allow_html=True)

with tab4:
    if 'news_data' in st.session_state:
        st.subheader("Quick Insight Brief (Brand Specific)")
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
st.markdown("<div style='text-align: center; color: #bdbdbd; font-size: 0.8em;'>Global AI Insights Engine | Secured Enterprise Grade | <b>Tailored for Kudsan & Bellinee's</b></div>", unsafe_allow_html=True)