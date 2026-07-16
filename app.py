import streamlit as st
import os
import datetime
import sqlite3
import PyPDF2
import docx
from smolagents import CodeAgent, InferenceClientModel, tool

# =====================================================================
# 💾 SQLite 資料庫初始化 (提供 Agent 待辦事項儲存空間)
# =====================================================================
def init_db():
    conn = sqlite3.connect('secretary.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_name TEXT,
                  status TEXT,
                  created_at TEXT)''')
    conn.commit()
    conn.close()

# 確保伺服器啟動時，資料庫與資料表已建立
init_db()


# =====================================================================
# 🛠️ 秘書的五大核心工具定義
# =====================================================================

@tool
def get_current_date() -> str:
    """取得今天的日期，這對秘書安排時程非常重要"""
    return datetime.date.today().strftime("%Y-%m-%d")

@tool
def add_tasks(tasks: list[str]) -> str:
    """將多個子任務清單加入到系統的 SQLite 資料庫中
    
    Args:
        tasks: 一個包含多個子任務字串的列表 (例如：['買書', '讀第一章'])
    """
    conn = sqlite3.connect('secretary.db')
    c = conn.cursor()
    today = datetime.date.today().strftime("%Y-%m-%d")
    for task in tasks:
        c.execute("INSERT INTO tasks (task_name, status, created_at) VALUES (?, ?, ?)", (task, '未完成', today))
    conn.commit()
    conn.close()
    return f"報告：已成功將 {len(tasks)} 項任務永久存入資料庫。"

@tool
def view_tasks() -> str:
    """查看目前資料庫中所有的待辦事項"""
    conn = sqlite3.connect('secretary.db')
    c = conn.cursor()
    c.execute("SELECT id, task_name, status FROM tasks")
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "報告：目前清單是空的，您沒有任何待辦事項。"
    return "\n".join([f"{row[0]}. [{row[2]}] {row[1]}" for row in rows])

@tool
def send_email(subject: str, content: str, recipient_email: str) -> str:
    """發送電子郵件給指定對象
    
    Args:
        subject: 郵件主旨
        content: 郵件內文
        recipient_email: 收件者的 Email 信箱地址
    """
    # 【模擬發送機制 (Mocking)】
    print("\n" + "="*50)
    print("📧 [系統模擬寄信] 攔截到一封即將發送的 Email")
    print(f"收件者: {recipient_email}")
    print(f"主旨  : {subject}")
    print(f"內容  :\n{content}")
    print("="*50 + "\n")
    
    return f"報告：已成功(透過模擬系統)發送郵件給 {recipient_email}。信件主旨為「{subject}」。"

@tool
def read_document(file_path: str) -> str:
    """讀取指定路徑的 PDF 或 Word(docx) 檔案內容，並回傳裡面的文字。
    
    Args:
        file_path: 檔案的名稱或路徑 (例如：'專案企劃書.pdf' 或 '會議記錄.docx')
    """
    if not os.path.exists(file_path):
        return f"錯誤：找不到檔案 {file_path}，請確認老闆是否已經上傳至系統。"
        
    ext = file_path.lower().split('.')[-1]
    text_content = ""
    
    try:
        if ext == 'pdf':
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text_content += page.extract_text() + "\n"
        elif ext == 'docx':
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text_content += para.text + "\n"
        else:
            return f"錯誤：不支援的檔案格式 .{ext}，目前只支援 PDF 與 DOCX。"
            
        # 防止檔案過大撐爆 LLM 的處理上限
        if len(text_content) > 5000:
            text_content = text_content[:5000] + "...(內容過長已截斷)"
            
        return f"【{file_path} 的內容擷取如下】：\n{text_content}"
    except Exception as e:
        return f"讀取檔案失敗：{str(e)}"


# =====================================================================
# 🎨 Streamlit 網頁基本設定與視覺風格 (酒紅與白)
# =====================================================================
st.set_page_config(
    page_title="AI 專業秘書", 
    page_icon="💼", 
    layout="centered",
    initial_sidebar_state="expanded" 
)

st.markdown("""
<style>
    .stApp {
        background-color: #FFFFFF;
    }
    #MainMenu {visibility: hidden;} 
    .stDeployButton {display: none;} 
    
    .block-container {
        padding-top: 3rem;
        max-width: 800px; 
    }
    
    .hero-title {
        text-align: center;
        font-size: 3.5rem;
        font-weight: 800;
        color: #5C0612;
        margin-bottom: 0.5rem;
        line-height: 1.2;
    }
    .hero-subtitle {
        text-align: center;
        font-size: 1.2rem;
        color: #4B5563;
        margin-bottom: 2.5rem;
        font-weight: 500;
    }
    .hero-highlight {
        color: #5C0612;
        border-bottom: 2px solid #5C0612;
    }
    
    [data-testid="stSidebar"] {
        background-color: #5C0612;
    }
    
    [data-testid="stSidebar"] __element__ , 
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] li {
        color: #FFFFFF !important;
    }

    p, span, label, li {
        color: #1F2937 !important;
    }
    
    .stTextInput div[data-baseweb="input"]:focus-within {
        border-color: #5C0612 !important;
    }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 🧠 初始化 AI 大腦與裝備工具
# =====================================================================
@st.cache_resource
def load_agent():
    model = InferenceClientModel(model_id="Qwen/Qwen2.5-Coder-32B-Instruct")
    # 這裡的 smolagents 會自動從系統環境變數中取得 Secrets 設定的 HF_TOKEN
    return CodeAgent(
        tools=[get_current_date, add_tasks, view_tasks, send_email, read_document], 
        model=model
    )

agent = load_agent()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# =====================================================================
# 📝 可收縮的側邊欄 (待辦清單與文件上傳)
# =====================================================================
with st.sidebar:
    st.header("📝 專案待辦清單")
    current_tasks = view_tasks()
    st.markdown(current_tasks)
    
    st.divider()
    
    st.header("📎 參考文件上傳")
    st.caption("支援 PDF 或 DOCX 格式。")
    uploaded_file = st.file_uploader("點擊或拖曳文件至此", type=["pdf", "docx"])
    
    if uploaded_file is not None:
        file_path = uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"✅ 上傳成功：{file_path}")


# =====================================================================
# 💬 主畫面置中對話區
# =====================================================================
st.markdown('<div class="hero-title">專屬您的 AI 執行秘書</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">只需<span class="hero-highlight">一句指令</span>，自動為您拆解專案、發送郵件與閱讀文件。</div>', unsafe_allow_html=True)

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
if prompt := st.chat_input("老闆，有什麼計畫需要幫您處理？"):
    st.chat_message("user").markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    
    with st.chat_message("assistant"):
        with st.spinner("秘書正在思考與處理中..."):
            secretary_instruction = f"""你是一位嚴謹、專業且能力強的執行秘書。
請根據老闆的要求，自行判斷需要呼叫哪些工具來完成任務（例如需要查日期就呼叫 get_current_date、需要讀檔就呼叫 read_document、需要記待辦就呼叫 add_tasks、需要寄信就呼叫 send_email）。

老闆的要求是：{prompt}

完成後，請向老闆簡要回報您執行了哪些動作。"""
            
            response = agent.run(secretary_instruction)
            st.markdown(response)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            
    st.rerun()