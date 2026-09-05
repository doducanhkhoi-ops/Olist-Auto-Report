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
    Bạn có công cụ `execute_sql` để truy vấn database MySQL. Các bảng: customers, geolocation, order_items, orders, payments, products, reviews, sellers, category_translation.
    
    THÔNG TIN TỪ LẦN PHÂN TÍCH TRƯỚC (Dùng để kết nối/lead-in):
    "{last_memory}"
    
    QUY TRÌNH PHÂN TÍCH BẮT BUỘC:
    1. TẬP TRUNG SÂU: MỖI báo cáo CHỈ CHỌN 1 ĐẾN 2 VẤN ĐỀ để phân tích thật sâu. Không lan man nhiều bảng rời rạc.
    2. TÍNH LIÊN KẾT: Thông tin và dữ liệu giữa các câu query phải có sự liên hệ logic (Ví dụ: Query 1 tìm ra nhóm SP lỗi -> Query 2 phải phân tích chi tiết vào nhóm SP đó).
    
    YÊU CẦU TRÌNH BÀY HTML (CỰC KỲ QUAN TRỌNG):
    - Lead-in: Luôn mở đầu bằng cách nhắc lại 1-2 câu về báo cáo trước để tạo sự liền mạch.
    - TRÌNH TỰ BẮT BUỘC KHI XUẤT DỮ LIỆU (Với mỗi lần query):
        + BƯỚC A: In ra câu lệnh SQL bạn đã dùng (trong thẻ <pre style="background:#eee; padding:10px; border-radius:5px;">).
        + BƯỚC B: BẮT BUỘC hiển thị BẢNG DỮ LIỆU GỐC (Dùng thẻ <table>, có kẻ viền rõ ràng). Bảng này phải giống hệt như khi chạy thực tế trên MySQL.
        + BƯỚC C: Phân tích bảng đó. CHỈ NẾU THỰC SỰ CẦN THIẾT thì mới vẽ THÊM 1 biểu đồ thanh ngang (bằng thẻ <div>). KHÔNG lạm dụng vẽ quá nhiều biểu đồ hay hiệu ứng animation rườm rà. Tính chính xác và bảng số liệu thực tế là ưu tiên số 1.
    
    BẮT BUỘC KÈM THEO MEMORY:
    Ở DƯỚI CÙNG của báo cáo, viết một tóm tắt kết luận ngắn (2-3 câu) về những gì vừa tìm được, đặt trong thẻ <ai_memory>...</ai_memory> để làm vốn cho lần chạy sau.
    """
    
    chat = client.chats.create(
        model='gemini-3.7-flash',
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
            break
        except Exception as e:
            print(f"CRITICAL ERROR ENCOUNTERED: {e}", flush=True)
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str or "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                print(f"Google đang giới hạn tốc độ. Nghỉ 30 giây rồi thử lại (Lần {attempt+1}/{max_retries})...", flush=True)
                time.sleep(30)
            else:
                traceback.print_exc()
                sys.exit(1)
