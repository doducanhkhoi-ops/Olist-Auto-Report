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
    
    # Đọc trí nhớ từ lần chạy trước
    last_memory = get_and_update_memory()
    print(f"Trí nhớ lần trước: {last_memory}", flush=True)
    
    system_instruction = f"""
    Bạn là một Chuyên gia Phân tích Dữ liệu Siêu cấp.
    Bạn có công cụ `execute_sql` để tự do truy vấn database MySQL. Các bảng: customers, geolocation, order_items, orders, payments, products, reviews, sellers, category_translation.
    
    THÔNG TIN TỪ LẦN PHÂN TÍCH TRƯỚC (Dùng để kết nối/lead-in):
    "{last_memory}"
    
    QUY TRÌNH PHÂN TÍCH BẮT BUỘC:
    1. Chủ đề: Chọn một chủ đề SÂU (kế thừa từ báo cáo trước hoặc tìm hướng mới lạ).
    2. Truy vấn: Bắt buộc gọi `execute_sql` nhiều lần để lấy số liệu, đào sâu (drill-down) tìm nguyên nhân rễ.
    3. Báo cáo: Viết báo cáo HTML chuyên nghiệp gửi Giám đốc.
    
    YÊU CẦU TRÌNH BÀY HTML:
    - Lead-in: Mở đầu bằng việc nhắc lại tóm tắt báo cáo lần trước và dẫn dắt lý do chọn chủ đề lần này.
    - Công khai SQL: Ngay phía trên MỖI bảng dữ liệu/biểu đồ, BẮT BUỘC in ra nguyên văn câu lệnh SQL bạn đã dùng (đặt trong thẻ <pre style="background:#eee; padding:10px; border-radius:5px;">) để sếp có thể tự copy test.
    - Biểu đồ Trực quan (RẤT QUAN TRỌNG): Vì email chặn Javascript, HÃY VẼ BIỂU ĐỒ THANH NGANG BẰNG HTML/CSS. 
      Ví dụ vẽ biểu đồ Bar Chart bằng thẻ <div>:
      <div style="margin-bottom: 5px;">
        <div>Sản phẩm A (80%)</div>
        <div style="width: 80%; background-color: #4CAF50; height: 20px;"></div>
      </div>
    - CSS: Dùng CSS inline lộng lẫy, màu sắc chuyên nghiệp.
    
    BẮT BUỘC KÈM THEO MEMORY:
    Ở DƯỚI CÙNG của báo cáo, bạn PHẢI viết một tóm tắt kết luận ngắn (2-3 câu) về những gì vừa tìm được, đặt trong thẻ <ai_memory>...</ai_memory>.
    Ví dụ: <ai_memory>Đã phân tích phí ship của SP A. Lần tới nên xem xét khu vực có phí ship cao nhất.</ai_memory>
    Hệ thống sẽ cắt thẻ này ra và lưu lại cho bạn vào lần chạy sau.
    """
    
    chat = client.chats.create(
        model='gemini-3.7-flash',
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[execute_sql],
            temperature=0.6,
        )
    )
    
    response = chat.send_message("Hãy thực hiện nhiệm vụ phân tích sâu của bạn, xuất HTML báo cáo và kèm theo <ai_memory>.")
    text = response.text
    
    # Cắt thẻ memory để lưu lại
    memory_match = re.search(r'<ai_memory>(.*?)</ai_memory>', text, re.DOTALL)
    if memory_match:
        new_memory = memory_match.group(1).strip()
        print(f"Lưu trí nhớ mới: {new_memory}", flush=True)
        get_and_update_memory(new_memory)
        # Xóa thẻ memory khỏi HTML gửi đi
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
            break
        except Exception as e:
            print(f"CRITICAL ERROR ENCOUNTERED: {e}", flush=True)
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"Máy chủ Google đang bận. Đợi 15 giây rồi thử lại (Lần {attempt+1}/{max_retries})...", flush=True)
                time.sleep(15)
            else:
                traceback.print_exc()
                sys.exit(1)
