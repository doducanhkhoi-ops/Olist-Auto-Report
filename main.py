import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mysql.connector
from google import genai
from google.genai import types
import traceback
import sys
# ĐÂY LÀ CÔNG CỤ (TOOL) MÀ AI SẼ TỰ ĐỘNG GỌI ĐỂ TÌM KIẾM DỮ LIỆU
def execute_sql(query: str) -> str:
    print(f"Agent đang chạy lệnh SQL: {query}", flush=True)
    try:
        conn = mysql.connector.connect(
            host=os.environ['DB_HOST'],
            port=18064,
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASS'],
            database="defaultdb"
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        data = cursor.fetchall()
        conn.close()
        # Giới hạn số lượng ký tự trả về để AI không bị ngộp dữ liệu
        return str(data)[:4000]
    except Exception as e:
        return f"Lỗi truy vấn SQL: {e}"
def generate_report():
    print("Khởi động AI Agent tự hành...", flush=True)
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    
    # KỊCH BẢN DÀNH CHO AI AGENT
    system_instruction = """
    Bạn là một Chuyên gia Phân tích Dữ liệu độc lập.
    Bạn có công cụ `execute_sql` để tự do truy vấn database MySQL (các bảng: customers, geolocation, order_items, orders, payments, products, reviews, sellers, category_translation).
    
    Quy trình của bạn bắt buộc phải trải qua các bước sau:
    1. Nghĩ ra một chủ đề phân tích ngẫu nhiên thú vị (VD: Top 5 sản phẩm bán chạy nhất bị đánh giá tệ, Phân tích doanh thu theo năm, Phí vận chuyển của các khu vực...).
    2. Chạy ít nhất 1 lệnh SQL để lấy cái nhìn tổng quan (BẮT BUỘC dùng công cụ execute_sql).
    3. Từ dữ liệu tổng quan đó, tìm một điểm bất thường hoặc thú vị.
    4. Chạy thêm 1 lệnh SQL nữa để "đào sâu" tìm nguyên nhân của điểm bất thường đó.
    5. Sau khi thu thập đủ dữ liệu 2 vòng, viết báo cáo cuối cùng.
    
    YÊU CẦU BÁO CÁO:
    - Trình bày hoàn toàn bằng mã HTML tuyệt đẹp, chuyên nghiệp.
    - Dùng CSS inline: Bảng (table) phải có đường viền (border), đổ màu nền xen kẽ (striped), in đậm tiêu đề.
    - Bắt buộc phải chia các phần: "Chủ đề phân tích", "Dữ liệu tổng quan (chèn bảng)", "Phát hiện bất thường", "Phân tích sâu nguyên nhân (chèn bảng)", "Kết luận".
    - KHÔNG dùng thẻ markdown ```html. Chỉ trả về HTML thuần túy để dán thẳng vào Email.
    """
    
    # Kích hoạt tính năng Automatic Function Calling để AI tự động đàm thoại với công cụ
    chat = client.chats.create(
        model='gemini-3.5-flash-lite'
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[execute_sql],
            temperature=0.7,
        )
    )
    
    print("Agent đang suy nghĩ và truy vấn Database...", flush=True)
    # Kích hoạt Agent
    response = chat.send_message("Hãy thực hiện nhiệm vụ phân tích của bạn cho ngày hôm nay và trả về HTML báo cáo cuối cùng.")
    
    return response.text
def send_email(html_content):
    print("Đang đóng gói Email...", flush=True)
    msg = MIMEMultipart()
    msg['From'] = os.environ['EMAIL_USER']
    msg['To'] = os.environ['EMAIL_USER']
    msg['Subject'] = "🚀 [AI Agent] Báo Cáo Phân Tích Database Tự Động"
    
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
    try:
        report = generate_report()
        send_email(report)
        print("Done!", flush=True)
    except Exception as e:
        print("CRITICAL ERROR ENCOUNTERED:", flush=True)
        traceback.print_exc()
        sys.exit(1)
