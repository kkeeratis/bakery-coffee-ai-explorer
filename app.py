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
        color: white;
        transform: translateY(-2px);
    }
    .report-card {
        background-color: white;
        padding: 25px;
        border-radius: 15px;
        border-left: 8px solid #6f4e37;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        color: #333;
        line-height: 1.6;
    }
    .executive-card {
        background-color: #f8f9fa;
        padding: 25px;
        border-radius: 15px;
        border-top: 8px solid #1a237e;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        color: #1a237e;
    }
    .insight-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 15px;
        border-left: 8px solid #00695c;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        color: #004d40;
        font-size: 1.1em;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Security & Network Setup ---
def get_secure_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def sanitize_input(text):
    if not text:
        return ""
    text = text[:100]
    text = re.sub(r'[<>{}\[\]]', '', text)
    return text.strip()

# --- Scraping Logic ---
def fetch_trends(category="Both", search_query=""):
    headlines = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    sources = []
    if category in ["Bakery", "Both"]:
        sources.append("https://www.bakeryandsnacks.com/Trends")
    if category in ["Coffee", "Both"]:
        sources.append("https://www.worldcoffeeportal.com/News")

    session = get_secure_session()

    for url in sources:
        try:
            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for item in soup.find_all(['h2', 'h3', 'h4']):
                text = item.get_text().strip()
                if 25 < len(text) < 150 and not text.isnumeric():
                    if not search_query or search_query.lower() in text.lower():
                        headlines.append(text)
        except requests.exceptions.RequestException:
            continue
            
    unique_headlines = list(dict.fromkeys(headlines))
    
    if not unique_headlines:
        return ["ไม่พบข้อมูลใหม่จากแหล่งข่าว กรุณาลองเปลี่ยนคำค้นหา"]
        
    return unique_headlines[:25]

# --- AI Analysis Logic ---
def analyze_trends(api_key, news_list, focus_topic, mode="General"):
    if not api_key:
        return "⚠️ กรุณากรอก API Key ในแถบด้านข้าง"
        
    if len(news_list) == 1 and "ไม่พบข้อมูล" in news_list[0]:
        return "⚠️ ไม่มีข้อมูลข่าวสารเพียงพอให้ AI วิเคราะห์ กรุณาดึงข้อมูลใหม่"
    
    try:
        genai.configure(api_key=api_key)
        
        # 1. ดึงรายชื่อโมเดลทั้งหมดที่ Key นี้มีสิทธิ์ใช้
        available_models = [
            m.name.replace('models/', '') 
            for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        
        if not available_models:
            return "❌ API Key ของคุณไม่มีสิทธิ์เข้าถึงโมเดลใดๆ เลย โปรดตรวจสอบที่ Google AI Studio"

        # 2. จัดลำดับความน่าใช้ (เพิ่ม 2.5-flash เข้าไปอย่างเป็นทางการ)
        preferred_order = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-pro', 'gemini-1.0-pro']
        models_to_try = []
        
        for pref in preferred_order:
            if pref in available_models:
                models_to_try.append(pref)
                
        for m in available_models:
            if m not in models_to_try:
                models_to_try.append(m)

        # 3. สร้าง Prompt ที่เข้มงวดขึ้น (Strict Prompt)
        context = "\n- ".join(news_list)
        safe_focus = sanitize_input(focus_topic)
        
        if mode == "Brief":
            prompt = f"""
            คุณคือที่ปรึกษากลยุทธ์ธุรกิจระดับประธานบริษัท (C-Level Advisor)
            ข้อมูลอ้างอิง:
            {context}
            
            [หัวข้อเน้นย้ำพิเศษ]: {safe_focus if safe_focus else 'ภาพรวมตลาด'}
            
            คำสั่งสำคัญที่สุด: ผู้บริหารไม่มีเวลาอ่านข้อความยาวๆ จงสรุปข้อมูลทั้งหมดให้เหลือเพียง "แก่น" ที่สำคัญที่สุดแบบสั้น กระชับ ตรงไปตรงมา (ไม่ต้องเกริ่นนำ ไม่ต้องมีคำลงท้าย) ให้ตอบแค่ 3 หัวข้อนี้เท่านั้น (หัวข้อละ 1-3 บรรทัด):
            
            1. **🔥 เทรนด์ตอนนี้เป็นอย่างไร:** (ภาพรวมตลาดตอนนี้เกิดอะไรขึ้นที่สำคัญที่สุด)
            2. **🎯 ควรดำเนินการอย่างไร:** (Action ที่ต้องสั่งลูกน้องไปทำเดี๋ยวนี้คืออะไร)
            3. **🔍 สิ่งที่ควรวิเคราะห์/จับตาต่อ:** (โอกาส ความเสี่ยง หรือประเด็นที่ต้องไปขุดข้อมูลเพิ่ม)
            """
        elif mode == "Executive":
            prompt = f"""
            คุณคือที่ปรึกษากลยุทธ์ธุรกิจระดับสูง (Executive Consultant) 
            จงวิเคราะห์ข้อมูลเทรนด์ข่าวสารเหล่านี้เพื่อทำสรุปแผนงานโดยละเอียด (Executive Roadmap):
            
            [ข้อมูลอ้างอิง]
            {context}
            
            [หัวข้อเน้นย้ำพิเศษ]: {safe_focus if safe_focus else 'ภาพรวมตลาด'}
            
            คำสั่งสำคัญ: จงเขียนอธิบายให้ละเอียดและครบถ้วนทั้ง 5 ข้อด้านล่างนี้ ห้ามเขียนสั้นกุด และต้องมีคำอธิบายขยายความในแต่ละข้อ (ตอบเป็นภาษาไทย):
            1. **Strategic Insights:** สรุปสาระสำคัญที่มีผลต่อทิศทางบริษัทในระยะยาว
            2. **Business Impact & ROI:** วิเคราะห์ความคุ้มค่าหากลงทุนตามเทรนด์นี้
            3. **Risk Assessment:** ความเสี่ยงที่ควรระวัง
            4. **Executive Roadmap:** ขั้นตอน 1, 2, 3 ที่ต้องสั่งการทันที
            5. **Key Resource Required:** ทรัพยากรหลักที่ต้องใช้
            """
        else:
            prompt = f"""
            คุณคือผู้เชี่ยวชาญด้านกลยุทธ์ธุรกิจ Cafe & Bakery ระดับโลก
            จงนำข้อมูลเทรนด์ข่าวสารล่าสุดเหล่านี้มาวิเคราะห์:
            
            [ข้อมูลอ้างอิง]
            {context}
            
            [หัวข้อเน้นย้ำพิเศษ]: {safe_focus if safe_focus else 'ภาพรวมตลาด'}
            
            คำสั่งสำคัญ: จงเขียนบทวิเคราะห์ให้ละเอียดและครบถ้วนตาม 4 หัวข้อด้านล่างนี้ ห้ามเขียนสั้นกุด หรือตัดจบกลางคัน (ตอบเป็นภาษาไทย):
            1. **Global Trends:** อธิบาย 3 เทรนด์ใหญ่ที่กำลังมาแรง (เรื่องกาแฟ/เมล็ดกาแฟ/ขนม) พร้อมยกตัวอย่างจากข้อมูลอ้างอิง
            2. **Thai Market Fit:** แนะนำวิธีนำเทรนด์เหล่านี้มาปรับใช้ในประเทศไทยให้เข้ากับพฤติกรรมผู้บริโภค
            3. **Signature Pairings:** แนะนำ 2 ชุดจับคู่เครื่องดื่มและขนมที่น่าสนใจ พร้อมบอกจุดขาย
            4. **Menu Innovation:** เสนอไอเดียเมนูใหม่ที่ควรทำขายเพื่อดึงดูดลูกค้า
            """
            
        generation_config = genai.types.GenerationConfig(
            temperature=0.7 if mode != "Brief" else 0.4 # ลดอุณหภูมิให้ Brief ตอบตรงประเด็น ไม่น้ำเยอะ
        )
        
        # 4. ทดลองยิง AI
        last_error = ""
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name=model_name)
                response = model.generate_content(prompt, generation_config=generation_config)
                
                # ตรวจสอบว่า AI ตอบมาสั้นผิดปกติหรือไม่ (ยกเว้นโหมด Brief ที่ต้องการความสั้น)
                if mode != "Brief" and len(response.text) < 100:
                    last_error = "AI ตอบสั้นเกินไป ระบบกำลังพยายามลองใหม่..."
                    continue
                    
                return f"*(วิเคราะห์สำเร็จโดยใช้โมเดล: `{model_name}`)*\n\n" + response.text
            except Exception as e:
                last_error = str(e)
                continue
                
        return f"❌ AI Error (ทดลองทุกโมเดลแล้วแต่ไม่สำเร็จ): {last_error}"
        
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาดของระบบ: {str(e)}"

# --- User Interface ---
st.title("☕ Bakery & Coffee Trend AI Explorer")
st.markdown("ระบบวิเคราะห์เทรนด์และวางแผนกลยุทธ์สำหรับผู้บริหารแบบ Real-time (Auto-Fallback Version)")

with st.sidebar:
    st.header("🔑 การตั้งค่าระบบ")
    
    default_api_key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
    
    api_key_input = st.text_input(
        "Gemini API Key:", 
        value=default_api_key,
        type="password",
        help="กรุณาใส่ API Key ของคุณเพื่อความปลอดภัย ระบบจะไม่บันทึกคีย์ของคุณ"
    )
    
    category_choice = st.selectbox(
        "เลือกหมวดหมู่ข้อมูล:",
        ["Both", "Bakery", "Coffee"]
    )
    
    raw_focus = st.text_input("หัวข้อที่สนใจ (จำกัด 100 ตัวอักษร):", max_chars=100)
    user_focus = sanitize_input(raw_focus)
    
    st.divider()
    st.write(f"📦 SDK Version: `{genai.__version__}`")
    st.caption("อัปเดตระบบเพิ่ม Executive Briefing Tab")

# --- เพิ่มแท็บที่ 4 (Brief Insight) ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 ข้อมูลเทรนด์ล่าสุด", 
    "💡 วิเคราะห์กลยุทธ์ AI", 
    "🎯 แผนการดำเนินงาน", 
    "⚡ สรุป Insight ฉบับย่อ"
])

with tab1:
    if st.button("🔄 ดึงข้อมูลเทรนด์ (Fetch Data)"):
        with st.spinner("กำลังเชื่อมต่อเซิร์ฟเวอร์ต่างประเทศอย่างปลอดภัย..."):
            news_data = fetch_trends(category_choice, user_focus)
            st.session_state['news_data'] = news_data
            if len(news_data) > 0 and "ไม่พบข้อมูล" not in news_data[0]: 
                st.success(f"พบข้อมูล {len(news_data)} รายการ")
            else:
                st.warning(news_data[0] if news_data else "ไม่พบข้อมูล")
            
    if 'news_data' in st.session_state:
        df = pd.DataFrame(st.session_state['news_data'], columns=["Trending Topics"])
        st.table(df)
        
        with st.expander("🔍 ดูข้อมูลดิบที่จะส่งให้ AI วิเคราะห์"):
            st.write(st.session_state['news_data'])

with tab2:
    if 'news_data' in st.session_state:
        if st.button("✨ วิเคราะห์แผนสินค้า"):
            with st.spinner("AI กำลังวิเคราะห์ข้อมูลเชิงลึก... (อาจใช้เวลา 10-20 วินาที)"):
                result = analyze_trends(api_key_input, st.session_state['news_data'], user_focus, mode="General")
                st.markdown(f'<div class="report-card">{result}</div>', unsafe_allow_html=True)
    else:
        st.info("กรุณาดึงข้อมูลที่แท็บแรกก่อนครับ")

with tab3:
    if 'news_data' in st.session_state:
        st.subheader("📋 บทสรุปเชิงกลยุทธ์แบบละเอียด (Roadmap)")
        if st.button("🚀 สรุป Action Plan ฉบับเต็ม"):
            with st.spinner("AI กำลังประมวลผลกลยุทธ์..."):
                exec_result = analyze_trends(api_key_input, st.session_state['news_data'], user_focus, mode="Executive")
                st.markdown(f'<div class="executive-card">{exec_result}</div>', unsafe_allow_html=True)
                
                st.download_button(
                    label="📥 ดาวน์โหลด Roadmap",
                    data=exec_result,
                    file_name=f"executive_roadmap_{time.strftime('%Y%m%d')}.md",
                    mime="text/markdown"
                )
    else:
        st.info("กรุณาดึงข้อมูลที่แท็บแรกก่อน เพื่อให้ AI มีฐานข้อมูลสำหรับวิเคราะห์แผนงาน")

with tab4:
    if 'news_data' in st.session_state:
        st.subheader("⚡ สรุป Insight ฉบับย่อ (อ่านจบใน 1 นาที)")
        if st.button("⚡ สรุปประเด็นสำหรับผู้บริหาร (Executive Brief)"):
            with st.spinner("AI กำลังสกัดเฉพาะเนื้อหาที่สำคัญที่สุด..."):
                brief_result = analyze_trends(api_key_input, st.session_state['news_data'], user_focus, mode="Brief")
                st.markdown(f'<div class="insight-card">{brief_result}</div>', unsafe_allow_html=True)
                
                st.download_button(
                    label="📥 ดาวน์โหลด Insight",
                    data=brief_result,
                    file_name=f"executive_insight_{time.strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
    else:
        st.info("กรุณาดึงข้อมูลที่แท็บแรกก่อน เพื่อให้ AI นำมาสรุป Insight ได้ครับ")

st.divider()
st.caption("Bakery & Coffee AI Explorer Pro | Detailed Analysis & Brief Insight Version")