import gradio as gr
import os
import shutil
import datetime
import sqlite3
import PyPDF2
import docx
import spaces  # 👈 新增引入 spaces，應付 ZeroGPU 檢查
from smolagents import CodeAgent, InferenceClientModel, tool

# =====================================================================
# 💾 SQLite 資料庫初始化 
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

init_db()

# 為了讓 UI 與 Agent 都能共用，獨立抽出一個讀取任務的函數
def get_all_tasks_str():
    conn = sqlite3.connect('secretary.db')
    c = conn.cursor()
    c.execute("SELECT id, task_name, status FROM tasks")
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "報告：目前清單是空的，您沒有任何待辦事項。"
    return "\n".join([f"{row[0]}. [{row[2]}] {row[1]}" for row in rows])

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
    return get_all_tasks_str()

@tool
def send_email(subject: str, content: str, recipient_email: str) -> str:
    """發送電子郵件給指定對象
    
    Args:
        subject: 郵件主旨
        content: 郵件內文
        recipient_email: 收件者的 Email 信箱地址
    """
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
            
        if len(text_content) > 5000:
            text_content = text_content[:5000] + "...(內容過長已截斷)"
            
        return f"【{file_path} 的內容擷取如下】：\n{text_content}"
    except Exception as e:
        return f"讀取檔案失敗：{str(e)}"

# =====================================================================
# 🧠 初始化 AI 大腦與裝備工具
# =====================================================================
# 改用 7B 模型避免觸發免費額度的 Rate Limit
model = InferenceClientModel(model_id="Qwen/Qwen2.5-Coder-7B-Instruct")
agent = CodeAgent(
    tools=[get_current_date, add_tasks, view_tasks, send_email, read_document], 
    model=model
)

# =====================================================================
# 🎨 Gradio 網頁介面設計與邏輯
# =====================================================================

# 處理對話邏輯
@spaces.GPU  # 👈 新增這行，讓 Hugging Face 放行
def chat_with_secretary(user_input, history):
    # 秘書的隱藏提示詞
    secretary_instruction = f"""你是一位嚴謹、專業且能力強的執行秘書。
請根據老闆的要求，自行判斷需要呼叫哪些工具來完成任務。
老闆的要求是：{user_input}
完成後，請向老闆簡要回報您執行了哪些動作。"""

    try:
        # 呼叫 Agent 執行任務
        response = agent.run(secretary_instruction)
    except Exception as e:
        response = f"⚠️ 秘書系統發生錯誤：{str(e)}"
    
    # 回傳：(空字串清空輸入框), (更新後的對話紀錄), (更新後的待辦清單)
    history.append((user_input, response))
    return "", history, get_all_tasks_str()

# 處理檔案上傳邏輯
def handle_upload(filepath):
    if not filepath:
        return "未選擇檔案"
    # 從暫存路徑中提取原始檔名，並複製到當前目錄供 Agent 讀取
    filename = os.path.basename(filepath)
    target_path = os.path.join(os.getcwd(), filename)
    shutil.copy(filepath, target_path)
    return f"✅ 檔案已就緒：{filename} (AI 秘書已經可以讀取了)"

# 建立 Gradio UI 佈局 (清空 Blocks 參數)
with gr.Blocks() as demo:
    gr.Markdown("<h1 style='text-align: center; color: #5C0612;'>💼 專屬您的 AI 執行秘書</h1>")
    gr.Markdown("<p style='text-align: center; color: #4B5563;'>只需一句指令，自動為您拆解專案、發送郵件與閱讀文件。</p>")
    
    with gr.Row():
        # 左側邊欄：待辦清單與檔案上傳
        with gr.Column(scale=1):
            gr.Markdown("### 📝 專案待辦清單")
            task_display = gr.Textbox(
                label="目前待辦", 
                value=get_all_tasks_str(), 
                interactive=False, 
                lines=10
            )
            refresh_btn = gr.Button("🔄 手動更新清單", size="sm")
            
            gr.Markdown("---")
            gr.Markdown("### 📎 參考文件上傳")
            file_upload = gr.File(label="上傳 PDF 或 DOCX", file_types=[".pdf", ".docx"], type="filepath")
            upload_status = gr.Textbox(label="上傳狀態", interactive=False)
            
        # 右側邊欄：聊天介面
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="秘書對話記錄", height=550)
            user_input = gr.Textbox(
                label="發送指令", 
                placeholder="老闆，有什麼計畫需要幫您處理？ (輸入完請按 Enter)", 
                lines=2
            )
            clear_btn = gr.ClearButton([user_input, chatbot], value="🗑️ 清除對話紀錄")

    # 綁定事件邏輯
    # 1. 使用者送出訊息：觸發對話並同時更新待辦清單
    user_input.submit(
        chat_with_secretary, 
        inputs=[user_input, chatbot], 
        outputs=[user_input, chatbot, task_display]
    )
    # 2. 檔案上傳完成：將檔案複製到正確位置並更新狀態提示
    file_upload.upload(
        handle_upload, 
        inputs=[file_upload], 
        outputs=[upload_status]
    )
    # 3. 手動更新待辦按鈕
    refresh_btn.click(
        get_all_tasks_str, 
        inputs=None, 
        outputs=[task_display]
    )

# 啟動伺服器 (將 theme 設定移至此處，解決 Gradio 6.0 的警告)
if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(primary_hue="red"))
