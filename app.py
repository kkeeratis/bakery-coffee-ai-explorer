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
    page_title="Bakery & Coffee AI Explorer", 
    page_icon="🥐☕", 
    layout="wide"
)

# --- Custom CSS ---
st.markdown("""
    <style>
    .main { background-color: #fdf5e6; }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5em;
        background-color: #6f4e37;
        color: white;
        font-weight: bold;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #4b3621;
        transform: translateY(-2px);
    }
    .report-card, .executive-card, .insight-card {
        background-color: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        line-height: 1.6;
    }
    .report-card { border-left: 8px solid #6f4e37; }
    .executive-card { border-top: 8px solid #1a237e; background-color: #f8f9fa; }
    .insight-card { border-left: 8px solid #00695c; color: #004d40; }
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
            
            # ดึงข้อมูลจากหลายๆ แท็กที่น่าจะเป็นหัวข้อข่าว
            tags_to_check = soup.find_all(['h2', 'h3', 'h4', 'a'])
            for item in tags_to_check:
                text = item.get_text().strip()
                # กรองความยาวพาดหัวข่าวที่เหมาะสม
                if 35 < len(text) < 150:
                    # ป้องกันการดึงเมนูซ้ำๆ หรือข้อความระบบ
                    if any(x in text.lower() for x in ['cookie', 'privacy', 'contact', 'subscribe', 'terms']):
                        continue
                    all_headlines.append(text)
        except:
            continue
            
    unique_all = list(dict.fromkeys(all_headlines))
    
    # หากมีการค้นหา ให้ลองกรองดู
    if search_query:
        filtered = [h for h in unique_all if search_query.lower() in h.lower()]
        if filtered:
            return filtered[:25], True # พบตรงตัว
        else:
            return unique_all[:25], False # ไม่พบตรงตัวแต่คืนค่าทั้งหมดให้ AI วิเคราะห์ต่อ
    
    return unique_all[:25], True

# --- AI Analysis ---
def analyze_trends(api_key, news_list, focus_topic, mode="General"):
    if not api_key: return "⚠️ กรุณากรอก API Key ในแถบด้านข้าง"
    
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferred = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-pro']
        models_to_try = [m for m in preferred if m in available_models] + [m for m in available_models if m not in preferred]

        context = "\n- ".join(news_list)
        safe_focus = sanitize_input(focus_topic)
        
        if mode == "Brief":
            prompt = f"คุณคือประธานที่ปรึกษาธุรกิจ สรุป 'แก่น' สำคัญจากข่าวเหล่านี้: {context} โดยเน้นไปที่หัวข้อ '{safe_focus}' แม้ในพาดหัวจะไม่มีคำนี้ตรงๆ แต่ให้วิเคราะห์ความเชื่อมโยง ตอบ 3 ข้อสั้นๆ: 1.เทรนด์ตอนนี้ 2.สิ่งที่ต้องทำทันที 3.สิ่งที่ต้องจับตาต่อ"
        elif mode == "Executive":
            prompt = f"วิเคราะห์กลยุทธ์เชิงลึกสำหรับผู้บริหาร หัวข้อ: {safe_focus} จากข้อมูลข่าว: {context} สรุป 5 หัวข้อ: Strategic Insights, ROI, Risks, Roadmap, Resources."
        else:
            prompt = f"วิเคราะห์แนวทาง Cafe & Bakery ระดับโลก หัวข้อ: {safe_focus} อ้างอิงจากข่าว: {context} สรุป 4 หัวข้อ: Global Trends, Thai Fit, Pairings, Menu Ideas."

        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name=model_name)
                response = model.generate_content(prompt)
                return f"*(วิเคราะห์โดย: `{model_name}`)*\n\n" + response.text
            except: continue
        return "❌ ไม่สามารถประมวลผล AI ได้"
    except Exception as e: return f"❌ Error: {str(e)}"

# --- UI ---
st.title("☕ Bakery & Coffee Trend AI Explorer")

with st.sidebar:
    st.header("🔑 ตั้งค่าระบบ")
    api_key_input = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else st.text_input("Gemini API Key:", type="password")
    
    category_choice = st.selectbox("เลือกหมวดหมู่:", ["Both", "Bakery", "Coffee"])
    st.info("💡 เคล็ดลับ: พิมพ์ภาษาอังกฤษ (เช่น Coffee, Sourdough) เพื่อดึงข้อมูลได้แม่นยำขึ้น")
    user_focus = sanitize_input(st.text_input("หัวข้อที่สนใจพิเศษ:", placeholder="เช่น Specialty Coffee"))
    
    st.divider()
    st.caption(f"SDK Version: {genai.__version__}")

tab1, tab2, tab3, tab4 = st.tabs(["📊 เทรนด์ล่าสุด", "💡 วิเคราะห์สินค้า", "🎯 แผนดำเนินงาน", "⚡ สรุป Insight"])

with tab1:
    if st.button("🔄 ดึงข้อมูล (Fetch Data)"):
        with st.spinner("กำลังอัปเดตข้อมูล..."):
            data, is_exact = fetch_trends(category_choice, user_focus)
            st.session_state['news_data'] = data
            if user_focus and not is_exact:
                st.warning(f"⚠️ ไม่พบคำว่า '{user_focus}' ในพาดหัวข่าววันนี้โดยตรง ระบบจึงดึงข่าวเทรนด์ภาพรวมมาให้ AI วิเคราะห์แทนครับ")
            elif data:
                st.success(f"พบข้อมูลเทรนด์ {len(data)} รายการ")

    if 'news_data' in st.session_state:
        st.table(pd.DataFrame(st.session_state['news_data'], columns=["Trending News Headlines"]))

with tab2:
    if 'news_data' in st.session_state:
        if st.button("✨ วิเคราะห์แผนสินค้า"):
            with st.spinner("AI กำลังประมวลผล..."):
                st.markdown(f'<div class="report-card">{analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "General")}</div>', unsafe_allow_html=True)

with tab3:
    if 'news_data' in st.session_state:
        if st.button("🚀 สรุป Action Plan"):
            with st.spinner("AI กำลังวาง Roadmap..."):
                st.markdown(f'<div class="executive-card">{analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Executive")}</div>', unsafe_allow_html=True)

with tab4:
    if 'news_data' in st.session_state:
        if st.button("⚡ สรุปฉบับย่อ"):
            with st.spinner("AI กำลังสกัด Insight..."):
                st.markdown(f'<div class="insight-card">{analyze_trends(api_key_input, st.session_state["news_data"], user_focus, "Brief")}</div>', unsafe_allow_html=True)