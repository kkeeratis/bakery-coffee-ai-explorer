import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import google.generativeai as genai
import pandas as pd
import re
import json
import time
from datetime import datetime

# --- Constants & Configuration ---
REQUEST_TIMEOUT: int = 15
MAX_HEADLINES: int = 25

# --- Security & Limits Configuration ---
DAILY_AI_LIMIT: int = 20        # โควตาสูงสุดต่อวันต่อผู้ใช้
COOLDOWN_SECONDS: int = 30      # เวลาหน่วง (วินาที) ป้องกันการกดรัว
ACCESS_PASSWORD: str = "bakery2026" # รหัสผ่านสำหรับปลดล็อค AI

REQUEST_HEADERS: dict[str, str] = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
BAKERY_URL: str = "https://www.bakeryandsnacks.com/Trends"
COFFEE_URL: str = "https://www.worldcoffeeportal.com/News"

# --- UI Configuration ---
st.set_page_config(
    page_title="Bakery & Coffee Global Insights", 
    layout="wide"
)

# --- Session State (AI Usage Tracking) ---
if "last_ai_time" not in st.session_state:
    st.session_state.last_ai_time = 0

if "daily_ai_count" not in st.session_state:
    st.session_state.daily_ai_count = 0

if "request_date" not in st.session_state:
    st.session_state.request_date = datetime.now().date()

# รีเซ็ตโควตาทุกวันใหม่
if st.session_state.request_date != datetime.now().date():
    st.session_state.daily_ai_count = 0
    st.session_state.request_date = datetime.now().date()

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
    
    .report-card, .executive-card, .insight-card, .dashboard-card, .social-card {
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
    .social-card { border-left: 8px solid #e91e63; background-color: #fff9fa; } 
    
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

# --- Utilities & Checks ---
def get_secure_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def sanitize_input(text: str) -> str:
    if not text: 
        return ""
    return re.sub(r'[<>{}\[\]`\'"]', '', str(text)[:100]).strip()

def check_ai_allowance() -> tuple[bool, str]:
    """ตรวจสอบโควตาและเวลาหน่วง (Cooldown) ก่อนเรียก AI"""
    if st.session_state.daily_ai_count >= DAILY_AI_LIMIT:
        return False, "❌ ท่านใช้งาน AI ครบโควตารายวันแล้ว (20 ครั้ง/วัน)"
    
    now = time.time()
    elapsed = now - st.session_state.last_ai_time
    if elapsed < COOLDOWN_SECONDS:
        remain = int(COOLDOWN_SECONDS - elapsed)
        return False, f"⏳ กรุณารอ {remain} วินาทีก่อนวิเคราะห์ครั้งถัดไป"
        
    return True, ""

# --- Network & Scraper (Cached) ---
# การดึงข่าวฟรี ซ่อน Spinner และ Cache ไว้ 1 ชั่วโมง
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_trends(category: str = "Both", search_query: str = "") -> tuple[list[str], bool]:
    all_headlines: list[str] = []
    sources: list[str] = []
    
    if category in ["Bakery", "Both"]: sources.append(BAKERY_URL)
    if category in ["Coffee", "Both"]: sources.append(COFFEE_URL)
        
    session = get_secure_session()
    
    for url in sources:
        try:
            response = session.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
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
        except requests.RequestException:
            continue
            
    unique_all = list(dict.fromkeys(all_headlines))
    
    if search_query:
        filtered = [h for h in unique_all if search_query.lower() in h.lower()]
        if filtered:
            return filtered[:MAX_HEADLINES], True
        else:
            return unique_all[:MAX_HEADLINES], False
            
    return unique_all[:MAX_HEADLINES], True

# --- AI Core Logic (Cached & Secured) ---
@st.cache_data(ttl=3600, show_spinner=False)
def _get_ai_response(api_key: str, context: str, safe_focus: str, mode: str) -> str:
    """ฟังก์ชันเนื้อแท้ของ AI ที่ถูก Cache เพื่อประหยัดโควตา API หากค้นหาเรื่องเดิม"""
    genai.configure(api_key=api_key)
    available_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    preferred = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']
    models_to_try = [m for m in preferred if m in available_models] + [m for m in available_models if m not in preferred]
    
    brand_context = """
    ในฐานะ 'Chief Strategist' ของ 2 แบรนด์หลัก:
    1. 'Kudsan' (คัดสรร): จุดแข็งคือ กาแฟและเบเกอรี่ในร้านสะดวกซื้อ, เน้น Mass Premium, ความรวดเร็ว (Grab & Go), เข้าถึงง่าย
    2. 'Bellinee's' (เบลลินี่): จุดแข็งคือ ร้านเบเกอรี่เฮ้าส์ระดับ Premium, อบสดใหม่ในร้าน (Bake-in-store), บรรยากาศสไตล์ยุโรป, นั่งทานในร้าน
    """
    base_instruction = "IMPORTANT: คุณต้องตอบเป็นภาษาไทยเท่านั้น โดยสรุปเนื้อหาให้เป็นมืออาชีพ นำไปใช้งานเจาะตลาดไทยแข่งกับแบรนด์อื่นได้จริง ห้ามใช้ HTML tags เด็ดขาด"
    
    gen_config = genai.types.GenerationConfig(temperature=0.7)
    
    if mode == "Dashboard":
        gen_config = genai.types.GenerationConfig(temperature=0.2, response_mime_type="application/json")
        prompt = f"""
        Analyze these news headlines and provide a JSON response for a business dashboard.
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
    elif mode == "Social":
        prompt = f"""
        {brand_context}
        คุณคือผู้เชี่ยวชาญด้าน 'Social Listening' และพฤติกรรมผู้บริโภคชาวไทย (เช่น ชาว Pantip, X/Twitter, TikTok)
        หัวข้อที่สนใจคือ: '{safe_focus if safe_focus else 'เทรนด์ร้านกาแฟและเบเกอรี่ทั่วไป'}'
        
        โปรดวิเคราะห์ 'เสียงสะท้อนของลูกค้า (Voice of Customer)' ในตลาดไทยปัจจุบัน โดยแบ่งเป็น 4 ส่วนดังนี้:
        1. 💬 สิ่งที่ลูกค้าชาวไทย 'ชอบ' และ 'ชื่นชม' (Gain Points / Expectations)
        2. 😡 สิ่งที่ลูกค้าชาวไทยมัก 'บ่น' หรือ 'ไม่พอใจ' จากแบรนด์คู่แข่ง (Pain Points / Complaints เช่น ราคา, รสชาติ, บริการ)
        3. 🎯 โอกาสทอง (Unmet Needs) ที่ Kudsan หรือ Bellinee's สามารถเข้าไปแก้ปัญหาจากข้อ 2 ได้
        4. 📝 ตัวอย่างคอมเมนต์จำลองสไตล์คนไทย 4 คอมเมนต์ (คำพูดสมจริง มีทั้งบวกและลบ เช่น "ทำไมสาขานี้..." หรือ "อันนี้อร่อยมากก...")
        {base_instruction}
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
            
            if mode == "Dashboard": return response.text
            return f"*(Analysed by: `{model_name}`)*\n\n" + response.text.replace("<", "&lt;").replace(">", "&gt;")
        except Exception:
            continue
            
    return "❌ AI Processing Failed. ขัดข้องหรือโควต้ารายวันอาจจะเต็ม กรุณาลองใหม่ภายหลัง"

def analyze_trends(api_key: str, news_list: list[str], focus_topic: str, mode: str = "General") -> str:
    """Wrapper สำหรับนับการใช้งานและอัปเดตเวลา Cooldown ก่อนเรียก AI จริง"""
    if not api_key: return "⚠️ Please provide a Gemini API Key in the sidebar."
    
    context = "\n- ".join(news_list)
    safe_focus = sanitize_input(focus_topic)
    
    # อัปเดต State การใช้งาน
    st.session_state.last_ai_time = time.time()
    st.session_state.daily_ai_count += 1
    
    # เรียกใช้ฟังก์ชัน AI ที่มีระบบ Cache
    return _get_ai_response(api_key, context, safe_focus, mode)

# --- UI Header ---
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>Bakery & Coffee Global Insights</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1em; color: #8d6e63; margin-top: 0;'>Professional Market Intelligence Engine</p>", unsafe_allow_html=True)

st.write("") 
col_header_1, col_header_2 = st.columns(2)
with col_header_1:
    st.image("https://images.unsplash.com/photo-1509440159596-0249088772ff?q=80&w=800&auto=format&fit=crop", use_container_width=True)
with col_header_2:
    st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?q=80&w=800&auto=format&fit=crop", use_container_width=True)
st.write("")

# --- Sidebar ---
with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 10px 0 20px 0; border-bottom: 1px solid #e0e0e0; margin-bottom: 20px;'>
            <div style='font-size: 3.5rem; line-height: 1;'>☕🥐</div>
            <h3 style='color: #4b3621; margin-top: 15px; margin-bottom: 0; font-weight: 700; font-size: 1.2rem; letter-spacing: 1px;'>AI INSIGHTS</h3>
            <p style='color: #8d6e63; font-size: 0.8rem; margin-top: 5px;'>Strategic Engine</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.header("⚙️ SYSTEM CONTROL")
    api_key_input = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else st.text_input("Gemini API Key:", type="password")
    
    # ระบบรหัสผ่านรักษาความปลอดภัย
    user_pass = st.text_input("Access Password:", type="password", help="กรุณาใส่รหัสผ่านเพื่อปลดล็อคการวิเคราะห์ AI")
    is_authorized = (user_pass == ACCESS_PASSWORD)
    
    st.divider()
    category_choice = st.selectbox("Market Domain:", ["Both", "Bakery", "Coffee"])
    user_focus = sanitize_input(st.text_input("Special Focus Area:", placeholder="e.g., Plant-based Milk"))
    
    st.divider()
    # แสดงหลอดพลังงานการใช้งาน AI รายวัน
    st.caption("AI Usage Quota (Today)")
    st.progress(min(st.session_state.daily_ai_count / DAILY_AI_LIMIT, 1.0))
    st.caption(f"Used: {st.session_state.daily_ai_count} / {DAILY_AI_LIMIT} Requests")
    
    st.caption(f"Engine Status: {genai.__version__} | Secured")
    st.caption("© 2026 Bakery AI Intelligence Platform")

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Market Headlines", 
    "💡 Product Strategy", 
    "🎯 Executive Roadmap", 
    "⚡ Quick Insights",
    "📈 Strategic Dashboard",
    "🗣️ Voice of Customer"
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
        allowed, msg = check_ai_allowance()
        
        if not is_authorized:
            st.warning("🔒 กรุณาใส่รหัสผ่านใน Sidebar เพื่อปลดล็อคฟีเจอร์ AI")
        else:
            if st.button("✨ Synthesize Strategy", disabled=not allowed):
                with st.spinner("Analysing global trends for your brands..."):
                    analysis = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "General")
                    st.markdown(f'<div class="report-card">{analysis}</div>', unsafe_allow_html=True)
            if not allowed:
                st.caption(msg)

with tab3:
    if 'news_data' in st.session_state:
        st.subheader("C-Level Roadmap (Kudsan & Bellinee's Focus)")
        allowed, msg = check_ai_allowance()
        
        if not is_authorized:
            st.warning("🔒 กรุณาใส่รหัสผ่านใน Sidebar เพื่อปลดล็อคฟีเจอร์ AI")
        else:
            if st.button("🚀 Draft Roadmap", disabled=not allowed):
                with st.spinner("Preparing executive roadmap..."):
                    roadmap = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Executive")
                    st.markdown(f'<div class="executive-card">{roadmap}</div>', unsafe_allow_html=True)
            if not allowed:
                st.caption(msg)

with tab4:
    if 'news_data' in st.session_state:
        st.subheader("Quick Insight Brief (Brand Specific)")
        allowed, msg = check_ai_allowance()
        
        if not is_authorized:
            st.warning("🔒 กรุณาใส่รหัสผ่านใน Sidebar เพื่อปลดล็อคฟีเจอร์ AI")
        else:
            if st.button("⚡ Get Summary", disabled=not allowed):
                with st.spinner("Extracting core brief..."):
                    brief = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Brief")
                    st.markdown(f'<div class="insight-card">{brief}</div>', unsafe_allow_html=True)
            if not allowed:
                st.caption(msg)

with tab5:
    if 'news_data' in st.session_state:
        st.subheader("Strategic Market Dashboard")
        allowed, msg = check_ai_allowance()
        
        if not is_authorized:
            st.warning("🔒 กรุณาใส่รหัสผ่านใน Sidebar เพื่อปลดล็อคฟีเจอร์ AI")
        else:
            if st.button("📊 Generate Visualization", disabled=not allowed):
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
                                    st.progress(min(max(score / 10, 0.0), 1.0))
                        except json.JSONDecodeError:
                            st.error("AI could not structure visual data securely. Please try again.")
            if not allowed:
                st.caption(msg)
    else:
        st.info("Fetch headlines first.")

with tab6:
    if 'news_data' in st.session_state:
        st.subheader("AI Social Listening & Customer Insights")
        st.caption("จำลองเสียงสะท้อนผู้บริโภคชาวไทย (Pain Points & Gain Points) เพื่อหาช่องว่างทางการตลาด")
        allowed, msg = check_ai_allowance()
        
        if not is_authorized:
            st.warning("🔒 กรุณาใส่รหัสผ่านใน Sidebar เพื่อปลดล็อคฟีเจอร์ AI")
        else:
            if st.button("🗣️ Analyze Customer Voice", disabled=not allowed):
                with st.spinner("กำลังสแกนพฤติกรรมและความคิดเห็นของผู้บริโภคชาวไทย..."):
                    social_insight = analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Social")
                    st.markdown(f'<div class="social-card">{social_insight}</div>', unsafe_allow_html=True)
            if not allowed:
                st.caption(msg)
    else:
        st.info("Please fetch market headlines first.")

st.divider()
st.markdown("<div style='text-align: center; color: #bdbdbd; font-size: 0.8em;'>Global AI Insights Engine | Secured Enterprise Grade | <b>Tailored for Kudsan & Bellinee's</b></div>", unsafe_allow_html=True)