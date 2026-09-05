import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mysql.connector
from google import genai
from google.genai import types
import traceback
import sys
import re

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ['DB_HOST'],
        port=18064,
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'],
        database="defaultdb"
    )

def execute_sql(query: str) -> str:
    print(f"Agent đang chạy lệnh SQL:\n{query}\n", flush=True)
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        data = cursor.fetchall()
        conn.commit()
        conn.close()
        return str(data)[:5000]
    except Exception as e:
        return f"Lỗi truy vấn SQL: {e}"

def get_and_update_memory(new_memory=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_memory (
                id INT AUTO_INCREMENT PRIMARY KEY, 
                memory_text TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        if new_memory:
            cursor.execute("INSERT INTO ai_memory (memory_text) VALUES (%s)", (new_memory,))
            conn.commit()
            conn.close()
            return True
            
        cursor.execute("SELECT memory_text FROM ai_memory ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row['memory_text'] if row else "Đây là báo cáo đầu tiên. Hãy phân tích tổng quan."
    except Exception as e:
        print(f"Lỗi memory: {e}")
        return "Không thể đọc memory."

def generate_report():
    print("Khởi động AI Agent PRO...", flush=True)
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    
    last_memory = get_and_update_memory()
    print(f"Trí nhớ lần trước: {last_memory}", flush=True)
    
    system_instruction = f"""
    Bạn là một Chuyên gia Phân tích Dữ liệu Siêu cấp.
    Bạn có công cụ `execute_sql` để tự do truy vấn database MySQL. Các bảng: customers, geolocation, order_items, orders, payments, products, reviews, sellers, category_translation.
    
    THÔNG TIN TỪ LẦN PHÂN TÍCH TRƯỚC (Dùng để kết nối/lead-in):
    "{last_memory}"
    
    QUY TRÌNH PHÂN TÍCH BẮT BUỘC:
    1. TẬP TRUNG SÂU: Chọn 1-2 vấn đề quan trọng để phân tích.
    2. TÍNH LIÊN KẾT: Gọi `execute_sql` nhiều lần để đào sâu từ tổng quan đến chi tiết.
    
    YÊU CẦU TRÌNH BÀY HTML (RẤT QUAN TRỌNG - PHẢI ĐẸP NHƯ DASHBOARD):
    Bạn PHẢI BỌC TOÀN BỘ BÁO CÁO TRONG KHUNG GIAO DIỆN SAU ĐỂ EMAIL HIỂN THỊ ĐẸP:
    
    <div style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f3f4f6; padding: 20px;">
       <div style="max-width: 850px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); overflow: hidden;">
           <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center;">
               <h1 style="margin:0; font-size: 28px; letter-spacing: 1px;">🚀 AI DATA DASHBOARD</h1>
               <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 16px;">Tự động phân tích & Trực quan hóa dữ liệu</p>
           </div>
           <div style="padding: 30px; line-height: 1.6; color: #333;">
               <!-- PHẦN LEAD-IN Ở ĐÂY -->
               
               <!-- VỚI MỖI TRUY VẤN, LÀM ĐÚNG TRÌNH TỰ: -->
               <!-- 1. CODE SQL -->
               <div style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 13px; overflow-x: auto; margin-bottom: 20px;">
                   [CHÈN CÂU LỆNH SQL VÀO ĐÂY]
               </div>
               
               <!-- 2. BẢNG DỮ LIỆU -->
               <table style="width: 100%; border-collapse: collapse; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                   <thead>
                       <tr style="background-color: #f8fafc; color: #475569; text-align: left; border-bottom: 2px solid #e2e8f0;">
                           <th style="padding: 12px 15px;">[TIÊU ĐỀ CỘT]</th>
                       </tr>
                   </thead>
                   <tbody>
                       <tr style="border-bottom: 1px solid #e2e8f0;">
                           <td style="padding: 12px 15px;">[DỮ LIỆU]</td>
                       </tr>
                   </tbody>
               </table>
               
               <!-- 3. BIỂU ĐỒ TRỰC QUAN (CSS BAR CHART) -->
               <div style="margin-bottom: 30px; padding: 15px; border-left: 4px solid #764ba2; background: #f8fafc;">
                   <h3 style="margin-top: 0; color: #475569;">📊 Trực quan hóa</h3>
                   <!-- Vẽ Bar Chart bằng CSS, ví dụ: -->
                   <div style="margin-bottom: 10px;">
                       <div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-weight: bold; font-size: 14px;">
                           <span>Sản phẩm A</span><span>80%</span>
                       </div>
                       <div style="width: 100%; background-color: #e2e8f0; border-radius: 10px; height: 12px; overflow: hidden;">
                           <div style="width: 80%; background: linear-gradient(90deg, #667eea, #764ba2); height: 100%; border-radius: 10px;"></div>
                       </div>
                   </div>
               </div>
               
               <!-- 4. LỜI PHÂN TÍCH -->
               <p style="font-size: 15px; color: #475569;">[CHÈN LỜI GIẢI THÍCH Ở ĐÂY]</p>
               <hr style="border: 0; border-top: 1px dashed #cbd5e1; margin: 30px 0;">
           </div>
       </div>
    </div>
    
    BẮT BUỘC KÈM THEO MEMORY:
    Ở DƯỚI CÙNG của báo cáo (nằm ngoài giao diện Dashboard), viết một tóm tắt ngắn (2-3 câu) đặt trong thẻ <ai_memory>...</ai_memory>.
    """
    
    chat = client.chats.create(
        model='gemini-3.5-flash-lite',
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[execute_sql],
            temperature=0.5,
        )
    )
    
    response = chat.send_message("Hãy thực hiện nhiệm vụ phân tích sâu của bạn, xuất HTML báo cáo và kèm theo <ai_memory>.")
    text = response.text
    
    memory_match = re.search(r'<ai_memory>(.*?)</ai_memory>', text, re.DOTALL)
    if memory_match:
        new_memory = memory_match.group(1).strip()
        print(f"Lưu trí nhớ mới: {new_memory}", flush=True)
        get_and_update_memory(new_memory)
        text = re.sub(r'<ai_memory>.*?</ai_memory>', '', text, flags=re.DOTALL)
        
    return text.strip()

def send_email(html_content):
    print("Đang đóng gói Email...", flush=True)
    msg = MIMEMultipart()
    msg['From'] = os.environ['EMAIL_USER']
    msg['To'] = os.environ['EMAIL_USER']
    msg['Subject'] = "📊 [AI Agent PRO] Báo Cáo Phân Tích Chuyên Sâu"
    
    if html_content.startswith("```html"):
        html_content = html_content[7:]
    if html_content.endswith("```"):
        html_content = html_content[:-3]

    msg.attach(MIMEText(html_content, 'html'))
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(os.environ['EMAIL_USER'], os.environ['EMAIL_PASS'])
    server.send_message(msg)
    server.quit()
    print("Email sent successfully!", flush=True)

if __name__ == "__main__":
    import time
    max_retries = 5
    for attempt in range(max_retries):
        try:
            report = generate_report()
            send_email(report)
            print("Done!", flush=True)
            sys.exit(0)
        except Exception as e:
            print(f"CRITICAL ERROR ENCOUNTERED: {e}", flush=True)
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str or "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt < max_retries - 1:
                    print(f"Google đang giới hạn tốc độ. Nghỉ 60 giây rồi thử lại (Lần {attempt+1}/{max_retries})...", flush=True)
                    time.sleep(60)
                else:
                    print("Đã thử 5 lần nhưng vẫn bị quá tải.", flush=True)
                    sys.exit(1)
            else:
                traceback.print_exc()
                sys.exit(1)
